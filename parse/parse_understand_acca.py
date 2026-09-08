#!/usr/bin/env python3
"""Per-connection view of Figure 5: the virtual runtime each thread actually
consumed, the packets it processed in softIRQ context, and the virtual runtime
the latency breakdown model says it should have consumed.

The two measured quantities (vruntime sampled by modules/vruntime_probe.c and
the softIRQ packet counts of modules/softirq_packets.c) are parsed by
parse_understand_default.py and reused here.

The model reconstructs how long a thread is on the CPU per request from the
per-stage timestamps of the kernel trace (latencies-<N>.log):

    modelled runtime = packets * (on-CPU cost of one request)

The on-CPU cost is the sum of the stages below. Together they cover the whole
request except rx_ready -> rx_wakeup, the runqueue wait, which is the one gap
the thread is not on the CPU for:

    app_hidden      last_xmit_finish -> rx_read    application work that is
                                                   hidden behind the previous
                                                   transmission
    app_hidden_2    rx_read -> rx_data_copy        entering read(), minus the
                                                   runqueue wait when the thread
                                                   did go to sleep
    rx_data_copy    rx_data_copy -> rx_return
    app             rx_return -> tx_write
    tx_data_copy    tx_write -> tx_tcp
    tx_tcp          tx_tcp -> tx_ip
    tx_ip           tx_ip -> tx_queue
    tx_queue        tx_queue -> tx_xmit
    tx_xmit         tx_xmit -> tx_finish

CFS does not charge runtime but virtual runtime, which is the runtime scaled by
NICE_0_LOAD / task weight, so the modelled runtime is scaled the same way before
it is put next to the sampled vruntime.

The packets processed in softIRQ are *not* part of the model: they are the work
the kernel charges to whichever thread happens to be running, and reporting them
next to the two vruntimes is what makes the gap between them readable.
"""
import os
import re

from parse_understand_default import (
    parse_client_log,
    parse_netfilter,
    parse_netperf_logs,
    parse_server_log,
    parse_vruntime,
)

# The first packets of a connection carry zeroed timestamps and may still be
# migrated between cores, so they are not representative.
SKIP_PACKETS_PER_PORT = 2

# Bit index of every stage in the "valid" bitmask of a trace line. A set bit
# means the kernel saw interference it could not account for, so that stage of
# that record has to be dropped.
STAGE_BITS = {
    "app_hidden": 0,
    "sleep_prepare": 1,
    "sleep_wake_up": 2,
    "rx_data_copy": 3,
    "app": 4,
    "tx_data_copy": 5,
    "tx_tcp": 6,
    "tx_ip": 7,
    "tx_queue": 8,
    "tx_xmit": 9,
}

# The fields of a trace line, in the order the kernel prints them.
TIMESTAMP_FIELDS = [
    "source_port", "destination_port",
    "rx_hw", "rx_alloc", "rx_irq", "rx_napi", "rx_gro", "rx_ip", "rx_tcp",
    "rx_read", "rx_sleep", "rx_ready", "rx_wakeup", "rx_data_copy", "rx_return",
    "tx_alloc", "tx_write", "tx_data_copy", "tx_tcp", "tx_ip", "tx_queue",
    "tx_xmit", "tx_finish",
    "last_xmit_finish", "valid",
    "app_hidden_loss", "sleep_prepare_loss", "sleep_wake_up_loss",
    "rx_data_copy_loss", "app_loss", "tx_data_copy_loss", "tx_tcp_loss",
    "tx_ip_loss", "tx_queue_loss", "tx_xmit_loss",
]

BREAKDOWN_PATTERN = re.compile(
    r".*source port: ([0-9]+) destination port: ([0-9]+) "
    r"-- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) "
    r"napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) "
    r"read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) "
    r"data copy: ([0-9]+) return: ([0-9]+) "
    r"-- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) "
    r"tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+) "
    r"-- last_xmit_finish: ([0-9]+) valid: ([0-9]+) "
    r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) 5: ([0-9]+) "
    r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+).*"
)

# Stages that are a plain "end timestamp - start timestamp - accounted loss",
# as (stage, start field, end field, loss field). The stage name is also the
# name of its validity bit.
LINEAR_STAGES = [
    ("rx_data_copy", "rx_data_copy", "rx_return", "rx_data_copy_loss"),
    ("app", "rx_return", "tx_write", "app_loss"),
    ("tx_data_copy", "tx_write", "tx_tcp", "tx_data_copy_loss"),
    ("tx_tcp", "tx_tcp", "tx_ip", "tx_tcp_loss"),
    ("tx_ip", "tx_ip", "tx_queue", "tx_ip_loss"),
    ("tx_queue", "tx_queue", "tx_xmit", "tx_queue_loss"),
    ("tx_xmit", "tx_xmit", "tx_finish", "tx_xmit_loss"),
]

# The test applications are started with `nice -n -20`
# (see scripts/single_core_understand_*.sh).
APP_NICE = -20
NICE_0_LOAD = 1024
# sched_prio_to_weight[] of kernel/sched/core.c, indexed by nice level -20..19.
PRIO_TO_WEIGHT = [
    88761, 71755, 56483, 46273, 36291,
    29154, 23254, 18705, 14949, 11916,
    9548, 7620, 6100, 4904, 3906,
    3121, 2501, 1991, 1586, 1277,
    1024, 820, 655, 526, 423,
    335, 272, 215, 172, 137,
    110, 87, 70, 56, 45,
    36, 29, 23, 18, 15,
]


def is_valid(valid_bitmask, stage):
    return (valid_bitmask & (1 << STAGE_BITS[stage])) == 0


def average(values):
    return sum(values) / len(values) if values else 0.0


def to_vruntime(runtime_ns, nice=APP_NICE):
    """Scale a runtime into the virtual runtime CFS would charge for it."""
    return runtime_ns * NICE_0_LOAD / PRIO_TO_WEIGHT[nice + 20]


def parse_breakdown_log(log_path, port_field):
    """Parse one trace log into {port: [record, ...]}, in log order.

    port_field selects which side of the connection identifies the thread:
    "destination_port" for the server log, "source_port" for the client log.
    """
    records = {}
    seen = {}
    with open(log_path, "r") as log:
        for line in log:
            match = BREAKDOWN_PATTERN.match(line)
            if match is None:
                continue
            record = dict(zip(TIMESTAMP_FIELDS, map(int, match.groups())))
            port = record[port_field]
            seen[port] = seen.get(port, 0) + 1
            if seen[port] > SKIP_PACKETS_PER_PORT:
                records.setdefault(port, []).append(record)
    return records


def collect_stages(port_records):
    """Group the valid, loss-corrected stage durations (ns) of one connection.

    A stage is only collected when its validity bit says the measurement was not
    disturbed; the interference the kernel did manage to account for is
    subtracted through the matching *_loss field. read() is split into the two
    cases the model distinguishes: the thread found data already queued
    ("insomnia") or it went to sleep (sleep_prepare plus the post-wake-up path).
    """
    stages = {"app_hidden": [], "insomnia": [], "sleep_prepare": [], "sleep_wake_up": []}
    stages.update({stage: [] for stage, _, _, _ in LINEAR_STAGES})
    slept = 0
    insomniac = 0

    for index, record in enumerate(port_records):
        # The application work hidden behind the previous transmission spans a
        # whole request on every other record only.
        if (index % 2 == 1
                and is_valid(record["valid"], "app_hidden")
                and record["rx_read"] >= record["last_xmit_finish"]):
            stages["app_hidden"].append(record["rx_read"] - record["last_xmit_finish"]
                                        - record["app_hidden_loss"])

        if record["rx_sleep"] == 0:
            insomniac += 1
            if is_valid(record["valid"], "sleep_wake_up"):
                stages["insomnia"].append(record["rx_data_copy"] - record["rx_read"]
                                          - record["sleep_wake_up_loss"])
        else:
            slept += 1
            if is_valid(record["valid"], "sleep_prepare"):
                stages["sleep_prepare"].append(record["rx_sleep"] - record["rx_read"]
                                               - record["sleep_prepare_loss"])
            if is_valid(record["valid"], "sleep_wake_up"):
                stages["sleep_wake_up"].append(record["rx_data_copy"] - record["rx_wakeup"]
                                               - record["sleep_wake_up_loss"])

        for stage, start, end, loss in LINEAR_STAGES:
            if is_valid(record["valid"], stage):
                stages[stage].append(record[end] - record[start] - record[loss])

    return stages, insomniac, slept


def request_cost(port_records):
    """On-CPU cost (ns) of one request, as the sum of the modelled stages."""
    stages, insomniac, slept = collect_stages(port_records)

    # read(): the two cases weighted by how often each of them happened.
    entries = insomniac + slept
    app_hidden_2 = 0.0
    if entries:
        slept_cost = average(stages["sleep_prepare"]) + average(stages["sleep_wake_up"])
        app_hidden_2 = (average(stages["insomnia"]) * insomniac
                        + slept_cost * slept) / entries

    return (average(stages["app_hidden"])
            + app_hidden_2
            + sum(average(stages[stage]) for stage, _, _, _ in LINEAR_STAGES))


def parse_model(threads_info, experiment_dir, n_thread):
    """Attach the modelled virtual runtime of both sides to every connection."""
    sides = [
        ("client", f"latencies-{n_thread}.log", "source_port"),
        ("server", f"latencies-{n_thread}-server.log", "destination_port"),
    ]

    for side, log_name, port_field in sides:
        records = parse_breakdown_log(os.path.join(experiment_dir, log_name), port_field)
        cost = {port: request_cost(port_records) for port, port_records in records.items()}
        for thread in threads_info:
            setattr(thread, f"{side}_model_vruntime",
                    to_vruntime(thread.packets * cost.get(thread.port, 0.0)))

    return threads_info


def report(threads_info):
    """Print tail latency, measured vruntime, softIRQ packets and modelled vruntime per port."""
    columns = [
        ("port", lambda thread: f"{thread.port}"),
        ("cli_core", lambda thread: f"{thread.client_core}"),
        ("srv_core", lambda thread: f"{thread.server_core}"),
        ("p999_lat", lambda thread: f"{thread.latency:.1f}"),
        ("cli_absvrun", lambda thread: f"{thread.client_abs_vruntime}"),
        ("srv_absvrun", lambda thread: f"{thread.server_abs_vruntime}"),
        ("cli_sirq_pkts", lambda thread: f"{thread.client_softirq_packets}"),
        ("srv_sirq_pkts", lambda thread: f"{thread.server_softirq_packets}"),
        ("cli_modelvrun", lambda thread: f"{thread.client_model_vruntime:.0f}"),
        ("srv_modelvrun", lambda thread: f"{thread.server_model_vruntime:.0f}"),
    ]

    rows = [[cell(thread) for _, cell in columns] for thread in threads_info]
    widths = [max([len(name)] + [len(row[index]) for row in rows])
              for index, (name, _) in enumerate(columns)]

    def line(cells):
        return "  ".join(cell.rjust(width) for cell, width in zip(cells, widths))

    header = line([name for name, _ in columns])
    print(header)
    print("-" * len(header))
    for row in rows:
        print(line(row))


if __name__ == "__main__":
    result_dir = "/data/projects/latency/"
    experiment = "single_core_understand_acca/36_64_1_1_1_1_1_2"
    n_thread = 36

    experiment_dir = os.path.join(result_dir, experiment)
    threads_info = parse_netperf_logs(experiment_dir, n_thread)
    threads_info = parse_server_log(threads_info, experiment_dir)
    threads_info = parse_client_log(threads_info, experiment_dir)
    threads_info = parse_netfilter(threads_info, experiment_dir)
    threads_info = parse_vruntime(threads_info, experiment_dir)
    threads_info = parse_model(threads_info, experiment_dir, n_thread)
    threads_info.sort(key=lambda thread: thread.port)

    report(threads_info)
