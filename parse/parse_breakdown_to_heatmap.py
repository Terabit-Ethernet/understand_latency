#!/usr/bin/env python3
"""Build per-stage latency-breakdown heatmaps from the kernel trace logs.

For every experiment, the run directories are grouped by setting (the directory
name without its trailing run index, e.g. "1_64_1_0_1_1_1" for the runs
1_64_1_0_1_1_1_{0,1,2}). All runs of a setting are parsed and merged, the
tail samples are extracted, and one .npy heatmap is written per setting:

    <result_dir>/<experiment>/heatmap_<experiment>_<setting>.npy

The array has one row per pipeline stage (STAGES, in order) and one column per
tail sample, in microseconds.
"""
import argparse
import glob
import os
import re
import sys
from collections import defaultdict

import numpy as np

# Configuration:
result_dir = "/data/projects/latency"
# Experiments to parse. Leave empty to parse every experiment found in result_dir.
experiments = ["isolated_thread_default"]
# Setting prefixes to parse, e.g. "1_64_1_0_1_1_1_". Leave empty to parse every
# setting found in the experiment directory.
prefixes = ["1_64_1_0_1_1_1_"]

# Fraction of the (sorted) end-to-end latencies kept as the tail.
TAIL_FRACTION = 0.002
# The first packets of a connection carry incomplete timestamps.
SKIP_PACKETS_PER_PORT = 2

# The trace fields, in the order the kernel prints them.
TIMESTAMP_FIELDS = [
    "source_port", "destination_port",
    "rx_hw", "rx_alloc", "rx_irq", "rx_napi", "rx_gro", "rx_ip", "rx_tcp",
    "rx_read", "rx_sleep", "rx_ready", "rx_wakeup", "rx_data_copy", "rx_return",
    "tx_alloc", "tx_write", "tx_data_copy", "tx_tcp", "tx_ip", "tx_queue",
    "tx_xmit", "tx_finish",
]

BREAKDOWN_BODY = (
    r"source port: ([0-9]+) destination port: ([0-9]+)"
    r" -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+)"
    r" gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+)"
    r" ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+)"
    r" -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+)"
    r" tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+)"
)

# A trace line is only taken into account when it was emitted by the process we
# expect on that side; the trace buffer also holds unrelated tasks.
CLIENT_APP = "latency_client"
SERVER_APP = "latency_server"


def breakdown_pattern(app_name):
    return re.compile(r".*" + re.escape(app_name) + r".*" + BREAKDOWN_BODY + r".*")


# The stages of one end-to-end round trip, in pipeline order. This is also the
# row order of the generated heatmap.
STAGES = [
    "client_rx_irq", "client_rx_napi", "client_rx_ip", "client_rx_tcp",
    "client_rx_sched", "client_rx_data_copy",
    "client_app",
    "client_tx_data_copy", "client_tx_tcp", "client_tx_ip", "client_tx_queue",
    "client_tx_xmit",
    "server_rx_irq", "server_rx_napi", "server_rx_ip", "server_rx_tcp",
    "server_rx_sched", "server_rx_data_copy",
    "server_app",
    "server_tx_data_copy", "server_tx_tcp", "server_tx_ip", "server_tx_queue",
    "server_tx_xmit",
]
# Stages taken from the packet the client sent (sender 1), the packet the server
# turned around (receiver 1), and the reply the client received (sender 2).
CLIENT_TX_STAGES = ["app", "tx_data_copy", "tx_tcp", "tx_ip", "tx_queue", "tx_xmit"]
CLIENT_RX_STAGES = ["rx_irq", "rx_napi", "rx_ip", "rx_tcp", "rx_sched", "rx_data_copy"]
SERVER_STAGES = CLIENT_RX_STAGES + ["app"] + CLIENT_TX_STAGES[1:]


def stage_latencies(ts):
    """Turn one record of absolute timestamps into per-stage durations (ns)."""
    return {
        "rx_hw": ts["rx_hw"],
        "rx_irq": ts["rx_alloc"] - ts["rx_hw"],
        "rx_napi": ts["rx_gro"] - ts["rx_alloc"],
        "rx_ip": ts["rx_tcp"] - ts["rx_gro"],
        "rx_tcp": ts["rx_ready"] - ts["rx_tcp"],
        "rx_sched": ts["rx_data_copy"] - ts["rx_ready"],
        "rx_data_copy": ts["rx_return"] - ts["rx_data_copy"],
        "app": ts["tx_write"] - ts["rx_return"],
        "tx_data_copy": ts["tx_tcp"] - ts["tx_write"],
        "tx_tcp": ts["tx_ip"] - ts["tx_tcp"],
        "tx_ip": ts["tx_queue"] - ts["tx_ip"],
        "tx_queue": ts["tx_xmit"] - ts["tx_queue"],
        "tx_xmit": ts["tx_finish"] - ts["tx_xmit"],
        # rx_hw .. rx_return: everything before the application is woken up.
        "phase_1": ts["rx_return"] - ts["rx_hw"],
        # rx_return .. tx_finish: the application and the whole tx path.
        "phase_2": ts["tx_finish"] - ts["rx_return"],
        "full": ts["tx_finish"] - ts["rx_hw"],
    }


def parse_breakdown_log(log_path, app_name, port_field):
    """Parse one trace log into {port: [per-stage latencies, in log order]}.

    Only lines emitted by `app_name` are considered. `port_field` selects which
    of the two ports in the record identifies the connection on this side.
    """
    pattern = breakdown_pattern(app_name)
    latencies = defaultdict(list)
    seen = defaultdict(int)

    with open(log_path, "r") as f:
        for line in f:
            match = pattern.match(line)
            if match is None:
                continue
            ts = dict(zip(TIMESTAMP_FIELDS, map(int, match.groups())))
            port = ts[port_field]
            seen[port] += 1
            if seen[port] <= SKIP_PACKETS_PER_PORT:
                continue
            latencies[port].append(stage_latencies(ts))

    return latencies


def combine_breakdown_e2e(client_latencies, server_latencies):
    """Stitch client and server records into end-to-end round trips (in us).

    NOTE: We are trying an end-to-end matching here:
          Sender 1 {app, ..., tx_xmit} --> Receiver 1 {rx_hw, ..., tx_xmit} --> Sender 2 {rx_hw, ..., rx_data_copy}
          If we need to attribute app to another part, we can change the
          attribution of phase_1 and phase_2 in stage_latencies later.
    """
    combined = []
    for port, client_samples in client_latencies.items():
        server_samples = server_latencies.get(port)
        if not server_samples:
            continue
        # Every round trip consumes two client records (the request it sends and
        # the reply it receives) and one server record.
        for i in range(min(len(client_samples), len(server_samples)) // 2):
            sender_1 = client_samples[i * 2]
            sender_2 = client_samples[i * 2 + 1]
            receiver_1 = server_samples[i * 2]

            sample = {f"client_{s}": sender_1[s] / 1e3 for s in CLIENT_TX_STAGES}
            sample.update({f"client_{s}": sender_2[s] / 1e3 for s in CLIENT_RX_STAGES})
            sample.update({f"server_{s}": receiver_1[s] / 1e3 for s in SERVER_STAGES})
            sample["total_full"] = (sender_1["phase_2"] + receiver_1["full"]
                                    + sender_2["phase_1"]) / 1e3
            combined.append(sample)

    return combined


def tail_heatmap(latencies):
    """Rows = STAGES, columns = the slowest TAIL_FRACTION of the round trips."""
    latencies.sort(key=lambda sample: sample["total_full"])
    tail = latencies[int(len(latencies) * (1 - TAIL_FRACTION)):]
    return np.array([[sample[stage] for stage in STAGES] for sample in tail]).T


def find_trace_logs(run_dir):
    """Locate the client-side and server-side trace logs of one run."""
    server_logs = glob.glob(os.path.join(run_dir, "latencies-*-server.log"))
    client_logs = [p for p in glob.glob(os.path.join(run_dir, "latencies-*.log"))
                   if not p.endswith("-server.log")]
    if not client_logs or not server_logs:
        return None
    return client_logs[0], server_logs[0]


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


def breakdown_heatmap(run_dirs):
    """Parse and merge every run of one setting into a single heatmap."""
    combined = []
    for run_dir in run_dirs:
        logs = find_trace_logs(run_dir)
        if logs is None:
            print(f"[warn] skipping {run_dir}: no latencies-*.log pair", file=sys.stderr)
            continue
        client_log, server_log = logs
        client_latencies = parse_breakdown_log(client_log, CLIENT_APP, "source_port")
        server_latencies = parse_breakdown_log(server_log, SERVER_APP, "destination_port")
        combined.extend(combine_breakdown_e2e(client_latencies, server_latencies))

    if not combined:
        return None
    return tail_heatmap(combined)


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
        heatmap = breakdown_heatmap(run_dirs)
        if heatmap is None:
            print(f"[warn] no usable samples for {experiment}/{setting}", file=sys.stderr)
            continue
        heatmap_path = os.path.join(experiment_dir, f"heatmap_{experiment}_{setting}.npy")
        np.save(heatmap_path, heatmap)
        print(f"Generated {heatmap_path} from {len(run_dirs)} run(s): "
              f"{heatmap.shape[0]} stages x {heatmap.shape[1]} tail samples.")


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
