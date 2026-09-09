#!/usr/bin/env python3

import argparse
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

# Configuration:
result_dir = "/data/projects/latency"
# Experiments to parse. Leave empty to parse every experiment found in result_dir.
experiments = ["single_core_iodepth_acca"]

# The first packets of a connection are still warming up (cold caches, threads
# not yet settled on a core), so they are not representative of the run.
SKIP_PACKETS_PER_PORT = 100

# The sides of the experiment, as (side, trace suffix, port field index). Both
# sides name the client port, the client trace as the source port and the
# server trace as the destination port, so the two join on it.
SIDES = [
    ("client", ".log", 0),
    ("server", "-server.log", 1),
]

# Column names for the fields of a setting (i.e. the directory name without the
# trailing run index), keyed by how many fields the setting has. Used only for
# the table header; the values always come from the directory name itself.
SETTING_SCHEMAS = {
    7: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "cores"],
    9: ["num_apps", "flowsize", "iodepth", "dim", "pin", "permute", "hrtick",
        "sched", "cores"],
}

BREAKDOWN_PATTERN = re.compile(
    r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+).*")


def breakdown_parser(breakdown_log_path, port_index):
    """Parse one trace into {client port: [rx_sched, ...]}.

    port_index selects which port of the connection identifies the thread: 0
    (the source port) in the client trace, 1 (the destination port) in the
    server one.
    """
    rx_sched = defaultdict(list)
    count = defaultdict(int)

    with open(breakdown_log_path, "r") as log:
        for line in log:
            match = BREAKDOWN_PATTERN.match(line)
            if match is None:
                continue
            fields = list(map(int, match.groups()))
            port, rx_sched_value = fields[port_index], fields[2]
            if count[port] >= SKIP_PACKETS_PER_PORT:
                rx_sched[port].append(rx_sched_value)
            count[port] += 1

    return rx_sched


def rx_sched_join(client_rx_sched, server_rx_sched):
    """Keep the samples of the connections both traces saw, joined on the port.

    Returns the client and the server samples of those connections, so that the
    two sides describe the same set of requests.
    """
    clients, servers = [], []
    for port, client_samples in client_rx_sched.items():
        server_samples = server_rx_sched.get(port)
        if not server_samples:
            continue
        clients.extend(client_samples)
        servers.extend(server_samples)
    return clients, servers


def find_trace(run_dir, suffix):
    """Path of one side's trace in a run directory, or None if it is missing.

    The trace is named after the number of application threads
    (latencies-<num_apps>.log), which is the first field of the setting, but it
    is looked up rather than derived so that the directory name stays opaque.
    """
    candidates = [entry for entry in os.listdir(run_dir)
                  if entry.startswith("latencies-") and entry.endswith(suffix)]
    # "latencies-<N>.log" also ends with the server suffix' ".log", so the
    # client trace is the one that is not the server trace.
    if suffix == ".log":
        candidates = [entry for entry in candidates if not entry.endswith("-server.log")]
    if len(candidates) != 1:
        return None
    return os.path.join(run_dir, candidates[0])


def parse_run(run_dir):
    """Read the two traces of one run. Returns (clients, servers)."""
    traces = {}
    for side, suffix, port_index in SIDES:
        path = find_trace(run_dir, suffix)
        if path is None:
            print(f"[warn] skipping {run_dir}: no {side} latencies-*{suffix}",
                  file=sys.stderr)
            return None
        traces[side] = breakdown_parser(path, port_index)

    clients, servers = rx_sched_join(traces["client"], traces["server"])
    if not clients:
        print(f"[warn] skipping {run_dir}: no rx_sched samples shared by both sides",
              file=sys.stderr)
        return None
    return clients, servers


def p999(samples):
    """99.9th percentile of a sample list."""
    if not samples:
        return float("nan")
    values = np.sort(np.asarray(samples, dtype=np.float64))
    return float(values[max(int(len(values) * 0.999) - 1, 0)])


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


def parse_setting(runs, pool):
    """Merge every run of one setting. Returns a result dict, or None."""
    clients, servers = [], []
    parsed_runs = 0
    for run_result in pool.map(parse_run, [run_dir for _, run_dir in runs]):
        if run_result is None:
            continue
        clients_run, servers_run = run_result
        clients.extend(clients_run)
        servers.extend(servers_run)
        parsed_runs += 1

    if not clients:
        return None

    return {
        "runs": parsed_runs,
        "client_samples": len(clients),
        "server_samples": len(servers),
        "client_p999": p999(clients),
        "server_p999": p999(servers),
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


def parse_experiment(experiment_name, pool, csv=False, save_name=None):
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
    for setting in sorted(runs_by_setting, key=sort_key):
        runs = sorted(runs_by_setting[setting], key=lambda r: sort_key((r[0],)))
        if len(setting) != num_fields:
            print(f"[warn] skipping setting {'_'.join(setting)}: "
                  f"expected {num_fields} fields, got {len(setting)}", file=sys.stderr)
            continue
        result = parse_setting(runs, pool)
        if result is None:
            print(f"[warn] no usable runs for setting {'_'.join(setting)}", file=sys.stderr)
            continue
        results.append((setting, result))

    header = list(columns) + ["runs", "client_samples", "server_samples",
                              "client_p999", "server_p999"]
    rows = []
    for setting, result in results:
        rows.append(list(setting) + [
            str(result["runs"]),
            str(result["client_samples"]),
            str(result["server_samples"]),
            f"{result['client_p999']:.0f}",
            f"{result['server_p999']:.0f}",
        ])

    print(f"# {experiment_name}")
    if csv:
        print(",".join(header))
        for row in rows:
            print(",".join(row))
    else:
        print(format_table(header, rows))
    print()

    if save_name:
        results_path = os.path.join(experiment_dir, save_name)
        with open(results_path, "w") as f:
            f.write(",".join(header) + "\n")
            for row in rows:
                f.write(",".join(row) + "\n")
        print(f"wrote {results_path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", default=None,
                        help="experiments to parse (defaults to the list in this file)")
    parser.add_argument("--result-dir", default=result_dir)
    parser.add_argument("--csv", action="store_true", help="print comma-separated rows")
    parser.add_argument("--save", metavar="NAME", default=None,
                        help="also write the rows to <experiment>/NAME")
    args = parser.parse_args()

    result_dir = args.result_dir
    names = args.names or experiments
    if not names:
        names = sorted(d for d in os.listdir(result_dir)
                       if os.path.isdir(os.path.join(result_dir, d)))

    # The traces of one setting are large and read one line at a time, so the
    # runs of a setting are parsed in parallel.
    max_workers = min(64, (os.cpu_count() or 1) + 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for experiment_name in names:
            parse_experiment(experiment_name, pool, csv=args.csv, save_name=args.save)
