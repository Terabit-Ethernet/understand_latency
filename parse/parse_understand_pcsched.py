#!/usr/bin/env python3
"""Per-connection view of the pcsched run: how many packets each client thread
and its server peer processed in softIRQ context.

pcsched does not charge the packet processing to a CFS virtual runtime, so the
vruntime side of parse_understand_default.py has nothing to report here; the
softIRQ packet counts of modules/softirq_packets.c are the whole measurement.

The netperf, server and client logs are still parsed, but only for what the
report is keyed on: the port of each connection, the pids the softIRQ counters
are indexed by, and the cores the two threads ran on.
"""
import os

from parse_understand_default import (
    parse_client_log,
    parse_netfilter,
    parse_netperf_logs,
    parse_server_log,
)


def report(threads_info):
    """Print the per-port tail latency and softIRQ packet counts of both sides."""
    header = (f"{'port':>6}  {'cli_core':>8}  {'srv_core':>8}  {'p999_lat':>9}  "
              f"{'cli_#pkts':>10}  {'srv_#pkts':>10}")
    print(header)
    print("-" * len(header))
    for thread in threads_info:
        print(f"{thread.port:>6}  {thread.client_core:>8}  {thread.server_core:>8}  "
              f"{thread.latency:>9.1f}  "
              f"{thread.client_softirq_packets:>10}  {thread.server_softirq_packets:>10}")


if __name__ == "__main__":
    result_dir = "/data/projects/latency/"
    experiment = "single_core_understand_pcsched/36_64_1_1_1_1_1_0"
    n_thread = 36

    experiment_dir = os.path.join(result_dir, experiment)
    threads_info = parse_netperf_logs(experiment_dir, n_thread)
    threads_info = parse_server_log(threads_info, experiment_dir)
    threads_info = parse_client_log(threads_info, experiment_dir)
    threads_info = parse_netfilter(threads_info, experiment_dir)
    threads_info.sort(key=lambda thread: thread.port)

    report(threads_info)
