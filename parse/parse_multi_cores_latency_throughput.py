#!/usr/bin/env python3
"""Parse multi-core latency/throughput experiments.

Instead of hard-coding the parameter sweep, this script walks the result
directory of each experiment, groups the run directories by setting (every
field of the directory name except the trailing run index), merges the runs of
a setting together and prints one table row per setting.

Directory layout it expects (see experiment/run_fig12_acca.py):

    <result_dir>/<experiment>/<p0>_<p1>_..._<pn>_<run>/

e.g. /data/projects/latency/multi_cores_macro_acca/4_64_1_0_1_1_16_0
where the setting is "4_64_1_0_1_1_16" and the run index is "0".

Unlike the single-core experiments, a multi-core run is driven by one client
process per logical core (see scripts/multi_cores_macro_*.sh).  Every one of
those processes writes its own ../temp/overall_hist.bin, so the merged
histogram of a run is useless here -- they all clobber the same file -- and the
scripts never call parse_netperf.py, so there is no throughput.log either.
What the processes do write is one pair of files per application thread, with
globally unique thread ids (latency_client_cores.cc numbers them
core_offset * threads_per_core + k):

    netperf-<id>_hist.bin   latency histogram, total_bin uint64 bins of 1us
    netperf-<id>_thpt.log   "<pid> <port> <mean> <p99> <p999> <thpt ops/s>"

So a run is parsed by summing the histograms and the throughputs of all of its
threads; the runs of a setting are then merged the same way as before.

Per setting it reports the merged latency distribution, the average throughput
and -- for experiments whose runs contain /proc/interrupts snapshots -- the
average number of NIC interrupts taken on each side during a run.
"""
import argparse
import os
import re
import sys
from collections import defaultdict

import numpy as np

# Configuration:
result_dir = "/data/projects/latency"
# Experiments to parse. Leave empty to parse every experiment found in result_dir.
experiments = ["multi_cores_macro_acca"]

total_bin = 100000

# Column names for the fields of a setting (i.e. the directory name without the
# trailing run index), keyed by how many fields the setting has. Used only for
# the table header; the values always come from the directory name itself.
SETTING_SCHEMAS = {
    7: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "cores"],
    9: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "hrtick",
        "sched", "cores"],
}

# Per-thread output of latency_client_cores.cc, moved into the run directory at
# the end of the run. The thread id is the number in the file name.
HIST_FILE = "netperf-{}_hist.bin"
HIST_FILE_RE = re.compile(r"^netperf-(\d+)_hist\.bin$")
THROUGHPUT_FILE = "netperf-{}_thpt.log"
# Field of a netperf-<id>_thpt.log line holding the throughput in ops/s.
THROUGHPUT_FIELD = -1
# Setting fields whose product is the number of application threads a run is
# expected to have. Only used to warn about runs that lost threads: the threads
# actually parsed are the ones found on disk.
THREADS_FIELDS = ["num_apps", "cores"]

# /proc/interrupts snapshots the experiment scripts take around each run (see
# scripts/multi_cores_*.sh), keyed by the side they were taken on.
INTERRUPT_FILES = [
    ("client", "interrupt_before", "interrupt_after"),
    ("server", "interrupt_before_server", "interrupt_after_server"),
]
# Number of mlx5 completion queues to account for. The experiment traffic
# spreads over one queue per logical core in use (the TASKSET of
# scripts/multi_cores_*.sh has 32 of them), so the queues are ranked by the
# interrupts they took during the run and only the busiest ones are summed.
INTERRUPT_QUEUES = 32
# The summed interrupts are reported per physical core, i.e. divided by this
# setting field. Without the field the raw sum is reported instead.
INTERRUPT_PER_FIELD = "cores"


def read_histogram(file_path):
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=total_bin)
    assert len(data) == total_bin, f"Expected {total_bin} entries in {file_path}, got {len(data)}"
    return data


def combine_histograms(hist_list):
    combined_hist = np.zeros(total_bin, dtype=np.uint64)
    for hist in hist_list:
        combined_hist += hist
    return combined_hist


def parse_histogram(histogram):
    total_samples = np.sum(histogram, dtype=np.uint64)
    if total_samples == 0:
        return float('nan'), float('nan')
    cumulative = np.cumsum(histogram)
    p999_latency_us = float(np.searchsorted(cumulative, float(total_samples) * 0.999))
    bins = np.arange(total_bin, dtype=np.float64)
    mean_latency_us = float(np.dot(histogram.astype(np.float64), bins) / float(total_samples))
    return mean_latency_us, p999_latency_us


def thread_ids(run_dir):
    """Ids of the application threads that left a histogram in a run."""
    ids = []
    for entry in os.listdir(run_dir):
        match = HIST_FILE_RE.match(entry)
        if match:
            ids.append(int(match.group(1)))
    return sorted(ids)


def read_thread_throughput(run_dir, thread_id):
    """Throughput (ops/s) of one application thread of a run."""
    path = os.path.join(run_dir, THROUGHPUT_FILE.format(thread_id))
    with open(path, "r") as f:
        lines = [line for line in f.readlines() if line.strip()]
    if not lines:
        raise ValueError(f"{path} is empty")
    return float(lines[0].split()[THROUGHPUT_FIELD])


def read_run(run_dir):
    """Merge the per-thread files of one run.

    Returns (combined histogram, throughput in ops/s, number of threads), or
    None if the run has no usable thread.
    """
    ids = thread_ids(run_dir)
    if not ids:
        print(f"[warn] skipping {run_dir}: no {HIST_FILE.format('<id>')}", file=sys.stderr)
        return None

    latency_bins = []
    throughput = 0.0
    for thread_id in ids:
        try:
            throughput += read_thread_throughput(run_dir, thread_id)
        except (FileNotFoundError, ValueError, IndexError) as e:
            print(f"[warn] {run_dir}: thread {thread_id} has no throughput ({e}), "
                  f"dropping the thread", file=sys.stderr)
            continue
        latency_bins.append(read_histogram(
            os.path.join(run_dir, HIST_FILE.format(thread_id))))

    if not latency_bins:
        print(f"[warn] skipping {run_dir}: no thread with both a histogram and "
              f"a throughput", file=sys.stderr)
        return None
    return combine_histograms(latency_bins), throughput, len(latency_bins)


def read_interrupt_counts(file_path):
    """Per-queue mlx5 completion interrupt counts of one /proc/interrupts dump.

    Each mlx5_comp line is "<irq>: <count per cpu>... <controller> <name>", so
    the per-CPU columns are summed until the first non-numeric field.
    """
    counts = []
    with open(file_path, "r") as f:
        for line in f:
            if "mlx5_comp" not in line:
                continue
            total = 0
            for element in line.split()[1:]:
                try:
                    total += int(element)
                except ValueError:
                    break
            counts.append(total)
    return counts


def read_interrupts(run_dir, before_name, after_name):
    """Interrupts taken by one side during a run, or None if not recorded."""
    before_path = os.path.join(run_dir, before_name)
    after_path = os.path.join(run_dir, after_name)
    if not (os.path.exists(before_path) and os.path.exists(after_path)):
        return None
    before = read_interrupt_counts(before_path)
    after = read_interrupt_counts(after_path)
    if not before or len(before) != len(after):
        print(f"[warn] {run_dir}: {before_name}/{after_name} list "
              f"{len(before)}/{len(after)} mlx5_comp queues, ignoring",
              file=sys.stderr)
        return None
    diff = sorted((a - b for a, b in zip(after, before)), reverse=True)
    return float(sum(diff[:INTERRUPT_QUEUES]))


def sort_key(setting):
    """Sort settings numerically field by field, falling back to string order."""
    key = []
    for field in setting:
        try:
            key.append((0, float(field), ""))
        except ValueError:
            key.append((1, 0.0, field))
    return key


def collect_runs(experiment_dir):
    """Group the run directories of an experiment by setting.

    Returns {setting_tuple: [(run_index, run_dir), ...]}.
    """
    runs_by_setting = defaultdict(list)
    for entry in sorted(os.listdir(experiment_dir)):
        run_dir = os.path.join(experiment_dir, entry)
        if not os.path.isdir(run_dir):
            continue
        fields = entry.split("_")
        if len(fields) < 2:
            print(f"[warn] skipping {run_dir}: unexpected directory name", file=sys.stderr)
            continue
        setting, run = tuple(fields[:-1]), fields[-1]
        runs_by_setting[setting].append((run, run_dir))
    return runs_by_setting


def setting_columns(experiment_dir, num_fields):
    """Column names for the setting fields.

    Prefer the key order recorded in a run's config.txt, fall back to the
    built-in schemas, then to generic names.
    """
    for root, _, files in os.walk(experiment_dir):
        if "config.txt" not in files:
            continue
        keys = []
        with open(os.path.join(root, "config.txt")) as f:
            for line in f:
                if "=" not in line or line.strip().startswith("["):
                    continue
                key = line.split("=", 1)[0].strip()
                if key != "experiment_name":
                    keys.append(key)
        if len(keys) == num_fields:
            return keys
        break
    if num_fields in SETTING_SCHEMAS:
        return SETTING_SCHEMAS[num_fields]
    return [f"p{i}" for i in range(num_fields)]


def setting_field(columns, setting, name):
    """Integer value of one setting field, or None if it is not there."""
    fields = dict(zip(columns, setting))
    if name not in fields:
        return None
    try:
        return int(fields[name])
    except ValueError:
        return None


def expected_threads(columns, setting):
    """Threads a run of this setting should have, or None if not derivable.

    The directory name carries the number of applications *per core* (see
    experiment/run_fig12_acca.py, which passes num_apps * cores to the script),
    so the thread count is the product of the fields in THREADS_FIELDS.
    """
    total = 1
    for name in THREADS_FIELDS:
        value = setting_field(columns, setting, name)
        if value is None:
            return None
        total *= value
    return total


def parse_setting(runs, threads=None, interrupt_divisor=None):
    """Merge every run of one setting. Returns a result dict, or None."""
    latency_bins = []
    throughputs = []
    thread_counts = []
    interrupts = {side: [] for side, _, _ in INTERRUPT_FILES}
    for _, run_dir in runs:
        run = read_run(run_dir)
        if run is None:
            continue
        histogram, throughput, num_threads = run
        if threads is not None and num_threads != threads:
            print(f"[warn] {run_dir}: parsed {num_threads} threads, "
                  f"expected {threads}", file=sys.stderr)
        latency_bins.append(histogram)
        throughputs.append(throughput)
        thread_counts.append(num_threads)
        for side, before_name, after_name in INTERRUPT_FILES:
            count = read_interrupts(run_dir, before_name, after_name)
            if count is not None:
                interrupts[side].append(count)

    if not latency_bins:
        return None

    mean_latency, latency999 = parse_histogram(combine_histograms(latency_bins))
    result = {
        "runs": len(latency_bins),
        # Threads parsed per run, averaged over the runs.
        "threads": float(np.mean(thread_counts)),
        "mean_latency_us": mean_latency,
        "p999_latency_us": latency999,
        # Average throughput across runs, in MIOPS.
        "throughput_miops": float(np.mean(throughputs)) / 1e6,
    }
    # Average interrupt count across the runs that recorded one, reported per
    # physical core. Runs without the /proc/interrupts dumps only drop out of
    # this average, they still count towards the latency and throughput above.
    for side, counts in interrupts.items():
        result[f"{side}_interrupts"] = (
            float(np.mean(counts)) / (interrupt_divisor or 1) if counts else None)
        result[f"{side}_interrupt_runs"] = len(counts)
    return result


def format_table(columns, rows):
    widths = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(c.rjust(w) for c, w in zip(columns, widths)),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(cell.rjust(w) for cell, w in zip(row, widths)) for row in rows]
    return "\n".join(lines)


def parse_experiment(experiment_name, csv=False):
    experiment_dir = os.path.join(result_dir, experiment_name)
    if not os.path.isdir(experiment_dir):
        print(f"[warn] experiment {experiment_dir} does not exist", file=sys.stderr)
        return

    runs_by_setting = collect_runs(experiment_dir)
    if not runs_by_setting:
        print(f"[warn] no run directories in {experiment_dir}", file=sys.stderr)
        return

    num_fields = max(len(s) for s in runs_by_setting)
    columns = setting_columns(experiment_dir, num_fields)

    results = []
    # Whether every setting could report its interrupts per physical core; only
    # used to label the column.
    interrupt_divisors = set()
    for setting in sorted(runs_by_setting, key=sort_key):
        runs = sorted(runs_by_setting[setting], key=lambda r: sort_key((r[0],)))
        if len(setting) != num_fields:
            print(f"[warn] skipping setting {'_'.join(setting)}: "
                  f"expected {num_fields} fields, got {len(setting)}", file=sys.stderr)
            continue
        interrupt_divisor = setting_field(columns, setting, INTERRUPT_PER_FIELD)
        interrupt_divisors.add(interrupt_divisor)
        result = parse_setting(runs, expected_threads(columns, setting),
                               interrupt_divisor)
        if result is None:
            print(f"[warn] no usable runs for setting {'_'.join(setting)}", file=sys.stderr)
            continue
        results.append((setting, result))

    # Only show the interrupt columns for experiments that recorded them.
    sides = [side for side, _, _ in INTERRUPT_FILES
             if any(r[f"{side}_interrupts"] is not None for _, r in results)]
    header = list(columns) + ["runs", "threads", "mean_lat_us", "p999_lat_us",
                              "thpt_mIOPS"]
    intr_suffix = "_intr" if None in interrupt_divisors else "_intr/core"
    header += [f"{side}{intr_suffix}" for side in sides]

    rows = []
    for setting, result in results:
        row = list(setting) + [
            str(result["runs"]),
            f"{result['threads']:.0f}",
            f"{result['mean_latency_us']:.3f}",
            f"{result['p999_latency_us']:.3f}",
            f"{result['throughput_miops']:.5f}",
        ]
        for side in sides:
            interrupts = result[f"{side}_interrupts"]
            row.append("" if interrupts is None else f"{interrupts:.0f}")
            interrupt_runs = result[f"{side}_interrupt_runs"]
            if interrupt_runs != result["runs"]:
                print(f"[warn] setting {'_'.join(setting)}: {side} interrupts "
                      f"averaged over {interrupt_runs} of {result['runs']} runs",
                      file=sys.stderr)
        rows.append(row)

    print(f"# {experiment_name}")
    if csv:
        print(",".join(header))
        for row in rows:
            print(",".join(row))
    else:
        print(format_table(header, rows))
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", default=None,
                        help="experiments to parse (defaults to the list in this file)")
    parser.add_argument("--result-dir", default=result_dir)
    parser.add_argument("--csv", action="store_true", help="print comma-separated rows")
    args = parser.parse_args()

    result_dir = args.result_dir
    names = args.names or experiments
    if not names:
        names = sorted(d for d in os.listdir(result_dir)
                       if os.path.isdir(os.path.join(result_dir, d)))

    for experiment_name in names:
        parse_experiment(experiment_name, csv=args.csv)
