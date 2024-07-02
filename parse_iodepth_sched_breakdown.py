
import re
import sys
import os
import subprocess
from statistics import mean
from itertools import product

hd="no_sep_irq"
our_patch=1
c_state=1
num_apps = [32]
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [10]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [100]
cores = [1]
runs = [0]

def read_perf_file(file):
    results = []
    f = open(file)
    lines = f.readlines()
    for line in lines:
        if "netdriver" in line or "pingpong_server" in line:
            results.append(line)
    return results

def parse_log(lines):
    perf_result = {}
    # Regular expressions to extract relevant information
    runtime_pattern = re.compile(r'sched:sched_stat_runtime:.*pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]')
    switch_pattern = re.compile(r'sched:sched_switch:.*prev_pid=(\d+).*next_pid=(\d+)')
    runtime_arr = 0
    # Initialize variables
    thread_runtimes = 0
    current_thread = -1
    sched_times = 0
    sum_temp = 0
    i = 0
    # Parse the log
    for line in lines:
        runtime_match = runtime_pattern.search(line)
        switch_match = switch_pattern.search(line)

        if runtime_match:
            thread_pid = int(runtime_match.group(1))
            runtime = float(runtime_match.group(2))
            timestamp = float(line.split()[3][:-1])
            cpu = int(line.split()[2][1:-1])
            if cpu not in perf_result:
                perf_result[cpu] = []
            perf_result[cpu].append({
                "timestamp": timestamp,
                "thread_pid": thread_pid,
                "runtime": runtime,
                "start": timestamp - runtime / 1000000000,
                "end": timestamp})
    #         if cpu == 0:
    #             if perf_result[0][len(perf_result[0]) - 1]["timestamp"] >= 19981.147081567 and perf_result[0][len(perf_result[0]) - 1]["timestamp"] <= 19981.147435135:
    #                 sum_temp += perf_result[0][len(perf_result[0]) - 1]["runtime"]
    # print(sum_temp)
                
    return perf_result

def convert_to_port_dict(samples):
    port_samples_dict = {}
    for cpu_samples in samples.values():
        for sample in cpu_samples:
            port = sample['port']
            if port not in port_samples_dict:
                port_samples_dict[port] = []
            port_samples_dict[port].append(sample)
    return port_samples_dict

def get_latency_breakdown_e2e(client_sample, server_sample):
    e2e_sample = []
    for p in client_sample:
        client_p = client_sample[p]
        server_p = server_sample[p]
        assert(len(client_p) == len(server_p))
        i = 0
        while i < len(client_p):
            client = client_p[i]
            server = server_p[i]
            if "skip" not in client and "skip" not in server:
                if "app" not in client:
                    client['app'] = 0
                if "app" not in server:
                    server['app'] = 0
                result = {
                    "rx_sched": client['rx_sched'] + server['rx_sched'],
                    'app': client['app'] + server['app']
                }
                e2e_sample.append(result)
            i = i + 1
    return e2e_sample

def parse_rx_sched_log(fileName, is_client):
    samples = {}
    timestamp_pattern = re.compile(r'timestamp: (\d+)')
    rx_sched_pattern = re.compile(r'rx_sched: (\d+)')
    pid_pattern = re.compile(r'netdriver_test_-(\d+)')
    pid_pattern_2 = re.compile(r'pingpong_server-(\d+)')
    source_port_pattern = re.compile(r'source port: (\d+)')
    dest_port_pattern = re.compile(r'destination port: (\d+)')
    f = open(fileName)
    lines = f.readlines()
    for line in lines:
        timestamp_match = timestamp_pattern.search(line)
        rx_sched_match = rx_sched_pattern.search(line)
        pid_match = pid_pattern.search(line)
        pid_match_2 = pid_pattern_2.search(line)
        source_port_match = source_port_pattern.search(line)
        dest_port_match = dest_port_pattern.search(line)
        if timestamp_match and rx_sched_match:
            source_port = int(source_port_match.group(1))
            dest_port = int(dest_port_match.group(1))
            timestamp = float(timestamp_match.group(1))
            rx_sched = int(rx_sched_match.group(1))
            cpu = int(line.split()[1][1:-1])
            if pid_match:
                pid = int(pid_match.group(1))
            else:
                pid = int(pid_match_2.group(1))
            if is_client:
                port = source_port
            else:
                port = dest_port
            if cpu not in samples:
                samples[cpu] = []
            samples[cpu].append({
                'cpu': cpu,
                'timestamp': timestamp / 1000000000,
                "rx_sched": rx_sched / 1000000000,
                "pid": pid,
                'port': port,
                "start": timestamp / 1000000000 - rx_sched / 1000000000,
                "end": timestamp / 1000000000,
            })
    for cpu, cpu_samples in samples.items():
        sorted_cpu_samples = sorted(cpu_samples, key=lambda x: x['start'])

        # Update the original list with the sorted samples
        samples[cpu] = sorted_cpu_samples
    return samples

def get_contribution(rx_sched_log, perf_log):

    # trim unnecessary data:
    for core in perf_log:
        timestamp = perf_log[core][0]['start']
        i = 0
        while True:
            if rx_sched_log[core][i]["start"] < timestamp:
                rx_sched_log[core][i]['skip'] = True
                i += 1
            else:
                break
    print("finish passing")
    for core in perf_log:
        j = 0
        i = 0
        while True:
            if 'skip' in rx_sched_log[core][i]:
                i += 1
            else:
                break
        while True:
            if i >= len(rx_sched_log[core]):
                break
            while j < len(perf_log[core]) and perf_log[core][j]["end"] < rx_sched_log[core][i]["start"]:
                j += 1
            if j >= len(perf_log[core]):
                break
            k = j
            while True:
                if k >= len(perf_log[core]):
                    break
                rx_sched = rx_sched_log[core][i]
                perf = perf_log[core][k]
                if  rx_sched["end"] < perf["start"]:
                    i += 1
                    break
                if "app" not in rx_sched:
                    rx_sched["app"] = 0
                if  perf["start"] >= rx_sched["start"] and perf["end"] <= rx_sched["end"]:
                    rx_sched["app"] +=  perf["end"] - perf["start"]
                elif perf["start"] <= rx_sched["start"] and perf["end"] <= rx_sched["end"]:
                    rx_sched["app"] += perf["end"] - rx_sched["start"]
                elif perf["start"] >= rx_sched["start"] and perf["end"] >= rx_sched["end"]:
                    rx_sched["app"] += rx_sched["end"] - perf["start"]
                elif perf["start"] <= rx_sched["start"] and perf["end"] >= rx_sched["end"]:
                    rx_sched["app"] += rx_sched["end"] - rx_sched["start"]
                k += 1


def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        f_client = os.path.join(DIR, "latencies-{}.log".format(n))
        f_server = os.path.join(DIR, "latencies-{}-server.log".format(n))
        f_server_perf =  os.path.join(DIR, "server_perf.log")
        f_client_perf =  os.path.join(DIR, "client_perf.log")
        # get server
        # rx_sched_server = parse_rx_sched_log(f_server, False)
        # server_perf = read_perf_file(f_server_perf)
        # perf_server = parse_log(server_perf)
        # get_contribution(rx_sched_server, perf_server)
        # rx_sched_server = convert_to_port_dict(rx_sched_server)
        # get client
        rx_sched_client = parse_rx_sched_log(f_client, True)
        client_perf = read_perf_file(f_client_perf)
        perf_client = parse_log(client_perf)
        get_contribution(rx_sched_client, perf_client)
        rx_sched_client =  convert_to_port_dict(rx_sched_client)

        # e2e_results = get_latency_breakdown_e2e(rx_sched_client, rx_sched_server)
        all_samples = []
        for cpu_samples in rx_sched_client.values():
            all_samples.extend(cpu_samples)
        sorted_all_samples = sorted(all_samples, key=lambda x: x['rx_sched'])
        start_index = int(len(sorted_all_samples) * 0.999)
        while start_index < len(sorted_all_samples):
            if 'skip' not in sorted_all_samples[start_index]:
                print(sorted_all_samples[start_index])
                print(sorted_all_samples[start_index]['app'], sorted_all_samples[start_index]['rx_sched'])
            start_index += 1


main()




