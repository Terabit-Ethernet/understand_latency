import os
import numpy as np


# The client threads of the single-core experiment are pinned to this core
# (see TASKSET in scripts/single_core_understand_default.sh).
CLIENT_CORE = 73

# netperf binds one port per thread, starting from this base port
BASE_PORT = 10000

# per-pid lines of client.log, formatted as "<label> <pid> <label> <value>"
PER_PID_CLIENT_LABELS = (
    "involuntary-context-switch-count:",
    "voluntary-context-switch-count:",
    "start-vruntime:",
    "final-vruntime:",
)


class ThreadData:
    """Per-connection (i.e. per-port) view of one client thread and its server peer."""

    def __init__(self):
        self.port = 0
        self.thpt = 0.0
        self.latency = 0.0
        self.packets = 0

        self.client_pid = 0
        self.client_core = -1
        self.client_softirq_packets = 0
        self.client_nivcsw = 0
        self.client_nvcsw = 0
        self.client_start_vruntime = 0
        self.client_final_vruntime = 0
        self.client_abs_vruntime = 0

        self.server_pid = 0
        self.server_core = -1
        self.server_softirq_packets = 0
        self.server_start_vruntime = 0
        self.server_vruntime = []
        self.server_abs_vruntime = 0

    def __str__(self):
        return (f"--port: {self.port}, thpt: {self.thpt}, lat: {self.latency}, pkts: {self.packets}, "
                f"\t| Client: cpu-{self.client_core}, "
                f"#pkts-{self.client_softirq_packets}, "
                f"nvcsw-{self.client_nvcsw}, nivcsw-{self.client_nivcsw}, "
                f"abs_vrun-{self.client_abs_vruntime} "
                f"\t| Server: cpu-{self.server_core}, "
                f"#pkts-{self.server_softirq_packets}, "
                f"abs_vrun-{self.server_abs_vruntime}")

    def __repr__(self):
        return (f"<ThreadData port={self.port} client_pid={self.client_pid} "
                f"thpt={self.thpt} latency={self.latency}>")


def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, "rb") as f:
        return np.fromfile(f, dtype=np.uint64, count=100000)


def parse_netperf_logs(experiment_dir, total_threads):
    """One ThreadData per netperf thread, filled with throughput, latency and packet count."""
    threads_info = []
    for i in range(total_threads):
        throughput_log_path = os.path.join(experiment_dir, f"netperf-{i}_thpt.log")
        with open(throughput_log_path, "r") as throughput_log:
            items = throughput_log.readline().split()

        thread = ThreadData()
        thread.client_pid = int(items[0])
        thread.port = int(items[1])
        thread.latency = float(items[4])
        thread.thpt = float(items[5])

        histo_log_path = os.path.join(experiment_dir, f"netperf-{thread.port - BASE_PORT}_hist.bin")
        thread.packets = int(np.sum(read_histogram(histo_log_path), dtype=np.uint64))

        threads_info.append(thread)
    return threads_info


def parse_server_log(threads_info, experiment_dir):
    """Attach server pid / core / start vruntime, matched by port then by server pid."""
    by_port = {thread.port: thread for thread in threads_info}
    by_server_pid = {}

    with open(os.path.join(experiment_dir, "server.log"), "r") as server_log:
        for line in server_log:
            items = line.split()
            if "core:" in line:
                core, pid, port = int(items[2]), int(items[4]), int(items[7])
                thread = by_port.get(port)
                if thread is not None:
                    thread.server_pid = pid
                    thread.server_core = core
                    by_server_pid[pid] = thread
            elif "start-vruntime:" in line:
                pid, start_vruntime = int(items[1]), int(items[3])
                thread = by_server_pid.get(pid)
                if thread is not None:
                    thread.server_start_vruntime = start_vruntime
    return threads_info


def parse_client_log(threads_info, experiment_dir):
    """Attach client core, context switch counts and the start/final vruntime of each client thread."""
    by_port = {thread.port: thread for thread in threads_info}
    by_client_pid = {thread.client_pid: thread for thread in threads_info}

    with open(os.path.join(experiment_dir, "client.log"), "r") as client_log:
        for line in client_log:
            items = line.split()
            if "cpu:" in line:
                core, port = int(items[2]), int(items[7])
                thread = by_port.get(port)
                if thread is not None:
                    thread.client_core = core
                continue

            # every remaining line of interest is "<label> <pid> <label> <value>"
            if not any(label in line for label in PER_PID_CLIENT_LABELS) or len(items) < 4:
                continue
            thread = by_client_pid.get(int(items[1]))
            if thread is None:
                continue

            if "involuntary-context-switch-count:" in line:
                thread.client_nivcsw = int(items[3])
            elif "voluntary-context-switch-count:" in line:
                thread.client_nvcsw = int(items[3])
            elif "start-vruntime:" in line:
                # keep the first sample only: it is the vruntime before the measurement starts
                if thread.client_start_vruntime == 0:
                    thread.client_start_vruntime = int(items[3])
            elif "final-vruntime:" in line:
                thread.client_final_vruntime = int(items[3])

    for thread in threads_info:
        if thread.client_start_vruntime and thread.client_final_vruntime:
            thread.client_abs_vruntime = thread.client_final_vruntime - thread.client_start_vruntime
    return threads_info


def parse_softirq_packets(log_path):
    """Sum the per-pid softIRQ packet counts dumped by modules/softirq_packets.c.

    Each dump is a pair of lines per output core:
        Core:<c> PIDs: <pid> <pid> ...
        Core:<c> Counts: <count> <count> ...
    The counters are reset by the module after every dump, so all dumps that follow
    "Loading filter module" are accumulated.
    """
    packets_by_pid = {}
    with open(log_path, "r") as log:
        lines = log.readlines()

    line_index = 0
    while line_index < len(lines) and "Loading filter module" not in lines[line_index]:
        line_index += 1

    while line_index + 1 < len(lines):
        line = lines[line_index]
        if "Core:" not in line or "PIDs:" not in line:
            line_index += 1
            continue

        pid_items = line.split()
        pids = [int(item) for item in pid_items[pid_items.index("PIDs:") + 1:]]
        count_items = lines[line_index + 1].split()
        counts = [int(item) for item in count_items[count_items.index("Counts:") + 1:]]
        for pid, count in zip(pids, counts):
            packets_by_pid[pid] = packets_by_pid.get(pid, 0) + count
        line_index += 2

    return packets_by_pid


def parse_netfilter(threads_info, experiment_dir):
    """Attach the number of packets each client/server thread handled in softIRQ context."""
    client_packets = parse_softirq_packets(os.path.join(experiment_dir, "iter_thread_client.log"))
    server_packets = parse_softirq_packets(os.path.join(experiment_dir, "iter_thread_server.log"))
    for thread in threads_info:
        thread.client_softirq_packets = client_packets.get(thread.client_pid, 0)
        thread.server_softirq_packets = server_packets.get(thread.server_pid, 0)
    return threads_info


def parse_vruntime_samples(log_path):
    """Collect the vruntime samples dumped by modules/vruntime_probe.c, keyed by pid.

    Each sample is a pair of lines:
        All-thread IDs: <pid> <pid> ...
        All-thread vruntime: <vruntime> <vruntime> ...
    A thread that is missing from a sample gets a 0 placeholder so that all lists
    stay aligned on the sample index.
    """
    samples = []
    with open(log_path, "r") as log:
        lines = log.readlines()

    line_index = 0
    while line_index < len(lines) and "iterate_cfs_rq:" not in lines[line_index]:
        line_index += 1

    while line_index + 1 < len(lines):
        items = lines[line_index].split()
        if "All-thread IDs:" not in lines[line_index] or len(items) <= 7:
            line_index += 1
            continue

        pids = [int(item) for item in items[items.index("IDs:") + 1:]]
        vruntime_items = lines[line_index + 1].split()
        vruntimes = [int(item) for item in vruntime_items[vruntime_items.index("vruntime:") + 1:]]
        samples.append(dict(zip(pids, vruntimes)))
        line_index += 2

    vruntime_by_pid = {}
    for sample in samples:
        for pid in sample:
            vruntime_by_pid.setdefault(pid, [])
    for sample in samples:
        for pid, series in vruntime_by_pid.items():
            series.append(sample.get(pid, 0))
    return vruntime_by_pid


def parse_vruntime(threads_info, experiment_dir):
    """Attach the server-side vruntime samples and the vruntime consumed over the run."""
    vruntime_by_pid = parse_vruntime_samples(os.path.join(experiment_dir, "iter_thread_server.log"))

    for thread in threads_info:
        thread.server_vruntime = vruntime_by_pid.get(thread.server_pid, [])
        # skip the placeholder zeros of the samples taken before the thread was created,
        # and the first live sample, which is taken before the run reaches steady state
        live_samples = [v for v in thread.server_vruntime if v > 0]
        thread.server_abs_vruntime = live_samples[-1] - live_samples[3] if len(live_samples) >= 2 else 0
    return threads_info


def report(threads_info):
    """Print the per-port tail latency, softIRQ packet counts and consumed vruntime of both sides."""
    header = (f"{'port':>6}  {'cli_core':>8}  {'srv_core':>8}  {'p999_lat':>9}  "
              f"{'cli_#pkts':>10}  {'srv_#pkts':>10}  "
              f"{'cli_absvruntime':>16}  {'srv_absvruntime':>16}")
    print(header)
    print("-" * len(header))
    for thread in threads_info:
        print(f"{thread.port:>6}  {thread.client_core:>8}  {thread.server_core:>8}  "
              f"{thread.latency:>9.1f}  "
              f"{thread.client_softirq_packets:>10}  {thread.server_softirq_packets:>10}  "
              f"{thread.client_abs_vruntime:>16}  {thread.server_abs_vruntime:>16}")


if __name__ == "__main__":
    result_dir = "/data/projects/latency/"
    experiment = "single_core_understand_default/36_64_1_1_1_1_1_0"
    n_thread = 36

    experiment_dir = os.path.join(result_dir, experiment)
    threads_info = parse_netperf_logs(experiment_dir, n_thread)
    threads_info = parse_server_log(threads_info, experiment_dir)
    threads_info = parse_client_log(threads_info, experiment_dir)
    threads_info = parse_netfilter(threads_info, experiment_dir)
    threads_info = parse_vruntime(threads_info, experiment_dir)
    threads_info.sort(key=lambda thread: thread.port)

    report(threads_info)
