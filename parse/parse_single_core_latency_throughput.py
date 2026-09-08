#!/usr/bin/env python3
"""Parse single-core latency/throughput experiments.

Instead of hard-coding the parameter sweep, this script walks the result
directory of each experiment, groups the run directories by setting (every
field of the directory name except the trailing run index), merges the runs of
a setting together and prints one table row per setting.

Directory layout it expects (see experiment/run_fig2_default.py):

    <result_dir>/<experiment>/<p0>_<p1>_..._<pn>_<run>/

e.g. /data/projects/latency/isolated_thread_default/1_64_1_0_1_1_1_0
where the setting is "1_64_1_0_1_1_1" and the run index is "0".
"""
import argparse
import os
import sys
from collections import defaultdict

import numpy as np

# Configuration:
result_dir = "/data/projects/latency"
# Experiments to parse. Leave empty to parse every experiment found in result_dir.
experiments = ["single_core_understand_acca"]

total_bin = 100000

# Column names for the fields of a setting (i.e. the directory name without the
# trailing run index), keyed by how many fields the setting has. Used only for
# the table header; the values always come from the directory name itself.
SETTING_SCHEMAS = {
    7: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "cores"],
    9: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "hrtick",
        "sched", "cores"],
}

HIST_FILE = "overall_hist.bin"
# Throughput is written by parse_netperf.py into throughput.log (single value on
# the first line). Older results kept it on the second line of linux_latency.
THROUGHPUT_FILES = [("throughput.log", 0), ("linux_latency", 1)]


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


def read_throughput(run_dir):
    """Return the aggregate throughput (ops/s) of a single run."""
    for name, line_index in THROUGHPUT_FILES:
        path = os.path.join(run_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, "r") as f:
            lines = [line for line in f.readlines() if line.strip()]
        if len(lines) <= line_index:
            continue
        return float(lines[line_index].split()[0])
    raise FileNotFoundError(
        "no throughput log ({}) in {}".format(
            " or ".join(name for name, _ in THROUGHPUT_FILES), run_dir))


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


def parse_setting(runs):
    """Merge every run of one setting. Returns a result dict, or None."""
    latency_bins = []
    throughputs = []
    for _, run_dir in runs:
        hist_path = os.path.join(run_dir, HIST_FILE)
        if not os.path.exists(hist_path):
            print(f"[warn] skipping {run_dir}: no {HIST_FILE}", file=sys.stderr)
            continue
        try:
            throughput = read_throughput(run_dir)
        except (FileNotFoundError, ValueError, IndexError) as e:
            print(f"[warn] skipping {run_dir}: {e}", file=sys.stderr)
            continue
        latency_bins.append(read_histogram(hist_path))
        throughputs.append(throughput)

    if not latency_bins:
        return None

    mean_latency, latency999 = parse_histogram(combine_histograms(latency_bins))
    return {
        "runs": len(latency_bins),
        "mean_latency_us": mean_latency,
        "p999_latency_us": latency999,
        # Average throughput across runs, in MIOPS.
        "throughput_miops": float(np.mean(throughputs)) / 1e6,
    }


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
    header = list(columns) + ["runs", "mean_lat_us", "p999_lat_us", "thpt_mIOPS"]

    rows = []
    for setting in sorted(runs_by_setting, key=sort_key):
        runs = sorted(runs_by_setting[setting], key=lambda r: sort_key((r[0],)))
        if len(setting) != num_fields:
            print(f"[warn] skipping setting {'_'.join(setting)}: "
                  f"expected {num_fields} fields, got {len(setting)}", file=sys.stderr)
            continue
        result = parse_setting(runs)
        if result is None:
            print(f"[warn] no usable runs for setting {'_'.join(setting)}", file=sys.stderr)
            continue
        rows.append(list(setting) + [
            str(result["runs"]),
            f"{result['mean_latency_us']:.3f}",
            f"{result['p999_latency_us']:.3f}",
            f"{result['throughput_miops']:.5f}",
        ])

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
