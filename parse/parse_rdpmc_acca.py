#!/usr/bin/env python3
"""Per-connection processing time and memory stalls of the rdpmc experiment.

scripts/single_core_rdpmc_acca.sh runs the latency benchmark with
net.core.latency_perstage_rdpmc_on=1, so the kernel appends six performance
counters to every latency breakdown line: a stall-cycle and an L1d-stall-cycle
counter for each of the three stages a thread is on the CPU for,

    rxc     rx_data_copy -> rx_return   copying the request out of the socket
    app     rx_return    -> tx_write    the application itself
    txc     tx_write     -> tx_tcp      copying the response into the socket

A trace holds the records of every process on the machine, so a record only
belongs to the benchmark when its line also names the benchmark process:
latency_client in the client trace, latency_server in the server trace.

Both traces are read directly, without any intermediate file, and for every
connection the script reports the three stages together on each side:

    time        total processing time of one request (ns)
    stall       stall cycles of one request
    stall_l1d   L1d stall cycles of one request

The two sides are joined on the client port: the client trace identifies a
connection by its source port, the server trace by its destination port.
"""
import os
import re

# The first packets of a connection carry zeroed timestamps and may still be
# migrated between cores, and the last ones are truncated by the end of the
# run, so neither end of a trace is representative.
SKIP_PACKETS_PER_PORT = 1000
TRIM_TAIL_PACKETS = 10

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

# The fields of a trace line, in the order the kernel prints them. The last six
# are the rdpmc counters, one stall / L1d stall pair per measured stage.
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
    "rxc_stall", "rxc_stall_l1d",
    "app_stall", "app_stall_l1d",
    "txc_stall", "txc_stall_l1d",
]

# The measured stages, as (stage, validity bit, start field, end field, loss
# field). The stage name is the prefix of its two rdpmc counters.
STAGES = [
    ("rxc", "rx_data_copy", "rx_data_copy", "rx_return", "rx_data_copy_loss"),
    ("app", "app", "rx_return", "tx_write", "app_loss"),
    ("txc", "tx_data_copy", "tx_write", "tx_tcp", "tx_data_copy_loss"),
]

# The sides of the experiment, as (side, trace name, process name, port field).
SIDES = [
    ("client", "latencies-{n_thread}.log", "latency_client", "source_port"),
    ("server", "latencies-{n_thread}-server.log", "latency_server", "destination_port"),
]

# Column prefix of each side in the report.
SIDE_PREFIX = {"client": "cli", "server": "srv"}


def breakdown_pattern(comm):
    """Match a latency breakdown line printed for the process `comm`."""
    return re.compile(
        rf".*{re.escape(comm)}.*source port: ([0-9]+) destination port: ([0-9]+) "
        r"-- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) "
        r"napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) "
        r"read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) "
        r"data copy: ([0-9]+) return: ([0-9]+) "
        r"-- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) "
        r"tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+) "
        r"-- last_xmit_finish: ([0-9]+) valid: ([0-9]+) "
        r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) 5: ([0-9]+) "
        r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+) "
        r"p0: ([0-9]+) p1: ([0-9]+) p2: ([0-9]+) p3: ([0-9]+) "
        r"p4: ([0-9]+) p5: ([0-9]+).*"
    )


def is_valid(valid_bitmask, stage):
    return (valid_bitmask & (1 << STAGE_BITS[stage])) == 0


def average(values):
    return sum(values) / len(values) if values else 0.0


class ThreadData:
    """What one connection cost on one side of the experiment."""

    def __init__(self, port):
        self.port = port
        self.total_time = 0.0
        self.average_stall = 0.0
        self.average_stall_l1d = 0.0


def parse_breakdown_log(log_path, comm, port_field):
    """Parse the records of `comm` in one trace into {port: [record, ...]}.

    port_field selects which side of the connection identifies the thread:
    "source_port" for the client trace, "destination_port" for the server one.
    Both name the client port, so the two sides join on it.
    """
    pattern = breakdown_pattern(comm)
    records = {}
    seen = {}

    with open(log_path, "r") as log:
        for line in log:
            match = pattern.match(line)
            if match is None:
                continue
            record = dict(zip(TIMESTAMP_FIELDS, map(int, match.groups())))
            port = record[port_field]
            seen[port] = seen.get(port, 0) + 1
            if seen[port] > SKIP_PACKETS_PER_PORT:
                records.setdefault(port, []).append(record)

    return records


def summarize(port, port_records):
    """Sum the per-request time and stalls of the three stages of one connection.

    A stage only contributes the records whose validity bit says the measurement
    was not disturbed; the interference the kernel did account for is subtracted
    through the matching *_loss field. A connection without a single valid
    record for one of its stages has no processing time to report, so it is
    dropped (None).
    """
    thread = ThreadData(port)

    for stage, bit, start, end, loss in STAGES:
        samples = [record for record in port_records
                   if is_valid(record["valid"], bit)]
        if not samples:
            return None
        thread.total_time += average([record[end] - record[start] - record[loss]
                                      for record in samples])
        thread.average_stall += average([record[f"{stage}_stall"]
                                         for record in samples])
        thread.average_stall_l1d += average([record[f"{stage}_stall_l1d"]
                                             for record in samples])

    return thread


def parse_side(experiment_dir, log_name, comm, port_field):
    """Summarize every connection of one trace into {port: ThreadData}."""
    records = parse_breakdown_log(os.path.join(experiment_dir, log_name),
                                  comm, port_field)

    threads = {}
    for port, port_records in records.items():
        thread = summarize(port, port_records[:-TRIM_TAIL_PACKETS])
        if thread is not None:
            threads[port] = thread

    return threads


def report(threads_per_side):
    """Print processing time and stalls of every connection, both sides per line."""
    sides = [side for side, _, _, _ in SIDES]
    columns = ["port"] + [f"{SIDE_PREFIX[side]}_{name}"
                          for side in sides
                          for name in ("time", "stall", "stall_l1d")]

    def cells(thread):
        if thread is None:
            return ["-", "-", "-"]
        return [f"{thread.total_time:.1f}",
                f"{thread.average_stall:.1f}",
                f"{thread.average_stall_l1d:.1f}"]

    ports = sorted(set().union(*[set(threads_per_side[side]) for side in sides]))
    rows = [[str(port)] + [cell
                           for side in sides
                           for cell in cells(threads_per_side[side].get(port))]
            for port in ports]

    widths = [max([len(name)] + [len(row[index]) for row in rows])
              for index, name in enumerate(columns)]

    def line(cells):
        return "  ".join(cell.rjust(width) for cell, width in zip(cells, widths))

    header = line(columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print(line(row))

    # The spread of the total processing time is what the experiment is after:
    # how differently the threads of one side are treated.
    for side in sides:
        times = [thread.total_time for thread in threads_per_side[side].values()]
        if times:
            print(f"[STATS] {side}: {len(times)} threads, processing time "
                  f"{min(times):.1f} .. {max(times):.1f} ns, "
                  f"gap {max(times) - min(times):.1f} ns")


if __name__ == "__main__":
    result_dir = "/data/projects/latency/"
    experiment = "single_core_rdpmc_acca/36_64_1_1_1_1_1_0"
    n_thread = 36

    experiment_dir = os.path.join(result_dir, experiment)
    threads_per_side = {
        side: parse_side(experiment_dir, log_name.format(n_thread=n_thread),
                         comm, port_field)
        for side, log_name, comm, port_field in SIDES
    }

    report(threads_per_side)
