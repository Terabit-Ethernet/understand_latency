#!/usr/bin/env python3
"""Build packet-size distribution CDFs from the packet_dist kernel module logs.

For every experiment, the run directories are grouped by setting (the directory
name without its trailing run index, e.g. "2_64_96_1_1_1_0_0_1" for the runs
2_64_96_1_1_1_0_0_1_{0,1,2}). All runs of a setting are parsed and their
histograms merged, and the resulting client-side and server-side CDFs are
printed as "size count" pairs.
"""
import argparse
import os
import sys
from collections import defaultdict

import numpy as np

# Configuration:
result_dir = "/data/projects/latency"
# Experiments to parse. Leave empty to parse every experiment found in result_dir.
experiments = ["single_core_iodepth_acca"]
# Setting prefixes to parse, e.g. "2_64_96_1_1_1_0_0_1_". Leave empty to parse
# every setting found in the experiment directory.
prefixes = ["2_64_32_1_1_1_1_"]

total_bin = 96

# The histogram logs of the two sides, as written by the packet_dist module.
CLIENT_LOG = "pkt_dist_client.log"
SERVER_LOG = "pkt_dist_server.log"


def parse_histogram(histogram):
    assert len(histogram) == total_bin, f"Expected {total_bin} entries, got {len(histogram)}"
    total_samples = np.sum(histogram, dtype=np.uint64)
    cumulative = np.cumsum(histogram)
    p999_latency_us = np.searchsorted(cumulative, total_samples * 0.999)
    bins = np.arange(total_bin, dtype=np.float64)
    mean_latency_us = float(np.dot(histogram.astype(np.float64), bins) / float(total_samples))
    return mean_latency_us, p999_latency_us


def parse_histogram_log(log_path):
    """Sum every histogram line of one log into a single histogram.

    Only the lines after the last module load are taken into account; earlier
    lines belong to a previous run that shared the same log file.
    """
    histogram = np.zeros(total_bin, dtype=np.uint64)

    with open(log_path, "r") as f:
        lines = f.readlines()

    # find the last line that has "Loading filter module", and read from the next line
    start_index = 0
    for i, line in enumerate(lines):
        if "Loading filter module" in line:
            start_index = i + 1

    for line in lines[start_index:]:
        if "Histogram:" not in line:
            continue
        parts = line.strip().split()
        bin_start_index = parts.index("Histogram:") + 1
        counts = parts[bin_start_index:bin_start_index + total_bin]
        for i, count in enumerate(counts):
            histogram[i] += int(count)

    return histogram


def collect_settings(experiment_dir, wanted_prefixes):
    """Group run directories by setting (the name without the run index)."""
    settings = defaultdict(list)
    for entry in sorted(os.listdir(experiment_dir)):
        run_dir = os.path.join(experiment_dir, entry)
        if not os.path.isdir(run_dir):
            continue
        setting, _, run = entry.rpartition("_")
        if not setting or not run:
            continue
        if wanted_prefixes and not any(entry.startswith(p) for p in wanted_prefixes):
            continue
        settings[setting].append(run_dir)
    return settings


def setting_histograms(run_dirs):
    """Parse and merge every run of one setting into client/server histograms."""
    hist_client = np.zeros(total_bin, dtype=np.uint64)
    hist_server = np.zeros(total_bin, dtype=np.uint64)
    parsed_runs = 0

    for run_dir in run_dirs:
        client_log = os.path.join(run_dir, CLIENT_LOG)
        server_log = os.path.join(run_dir, SERVER_LOG)
        if not os.path.exists(client_log) or not os.path.exists(server_log):
            print(f"[warn] skipping {run_dir}: no {CLIENT_LOG}/{SERVER_LOG} pair",
                  file=sys.stderr)
            continue
        hist_client += parse_histogram_log(client_log)
        hist_server += parse_histogram_log(server_log)
        parsed_runs += 1

    if parsed_runs == 0:
        return None
    return hist_client, hist_server, parsed_runs


def print_cdf(label, histogram):
    total_samples = np.sum(histogram, dtype=np.uint64)
    if total_samples == 0:
        print(f"[warn] {label}: empty histogram", file=sys.stderr)
        return
    mean_latency_us, p999_latency_us = parse_histogram(histogram)
    print(f"# {label}: {total_samples} samples")
    cdf = np.cumsum(histogram) / total_samples
    for size, count in enumerate(cdf):
        print(f"{size} {count}")


def parse_experiment(experiment, wanted_prefixes):
    experiment_dir = os.path.join(result_dir, experiment)
    if not os.path.isdir(experiment_dir):
        print(f"[warn] experiment {experiment_dir} does not exist", file=sys.stderr)
        return

    settings = collect_settings(experiment_dir, wanted_prefixes)
    if not settings:
        print(f"[warn] no matching run directories in {experiment_dir}", file=sys.stderr)
        return

    for setting, run_dirs in sorted(settings.items()):
        histograms = setting_histograms(run_dirs)
        if histograms is None:
            print(f"[warn] no usable runs for {experiment}/{setting}", file=sys.stderr)
            continue
        hist_client, hist_server, parsed_runs = histograms
        print(f"## {experiment}/{setting} ({parsed_runs} run(s))")
        print_cdf("client", hist_client)
        print_cdf("server", hist_server)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*",
                        help="experiments to parse (defaults to the list in this file)")
    parser.add_argument("--result-dir", default=result_dir)
    parser.add_argument("--prefix", action="append", default=None,
                        help="only parse settings whose run directories start with "
                             "this prefix (repeatable)")
    args = parser.parse_args()

    result_dir = args.result_dir
    names = args.names or experiments
    if not names:
        names = sorted(d for d in os.listdir(result_dir)
                       if os.path.isdir(os.path.join(result_dir, d)))

    for experiment in names:
        parse_experiment(experiment, args.prefix or prefixes)
