#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from copy import deepcopy
# Regular expressions to match the required patterns
waking_pattern = r'sched_waking:.*comm=(\w+).*pid=(\d+).*'
runtime_pattern = r'sched_stat_runtime.*comm=(\w+).*?pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]'
switch_pattern = r'sched:sched_switch:.*?prev_pid=(\d+).*?next_pid=(\d+)'

# Dictionary to store waking timestamps and runtime sums for each PID
server_pid_data = {}

thread_dict = {}
client_dict = {}
server_dict = {}

class thread_data:
    start_client_time = 0
    start_server_time = 0
    client_core = 0
    client_pid = 0
    client_port = 0
    server_core = 0
    server_pid = 0
    # server_port = 0
    thpt = 0
    latency = 0
    client_rx_sched = 0
    server_rx_sched = 0

def get_latency_breakdown(f, is_client):
    # Read the latencies file
    lines = []
    with open(f, "r") as file:
        lines = file.readlines()

    # Patterm
    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*")

    # Create a dict for samples
    samples = {}

    # Parse each line
    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 23:
                # port = 0
                if is_client:
                    port = timestamps[0]
                else:
                    port = timestamps[1]
                rx_hw = timestamps[2]
                rx_alloc = timestamps[3]
                rx_irq = timestamps[4]
                rx_napi = timestamps[5]
                rx_gro = timestamps[6]
                rx_ip = timestamps[7]
                rx_tcp = timestamps[8]
                rx_read = timestamps[9]
                rx_sleep = timestamps[10]
                rx_ready = timestamps[11]
                rx_wake_up = timestamps[12]
                rx_data_copy = timestamps[13]
                rx_return = timestamps[14]
                tx_alloc = timestamps[15]
                tx_write = timestamps[16]
                tx_data_copy = timestamps[17]
                tx_tcp = timestamps[18]
                tx_ip = timestamps[19]
                tx_queue = timestamps[20]
                tx_xmit = timestamps[21]
                tx_finish = timestamps[22]

                if port not in samples:
                    samples[port] = []

                samples[port].append({
                    'rx_hw': rx_hw,
                    'rx_alloc': rx_alloc,
                    'rx_irq': rx_irq,
                    'rx_napi': rx_napi,
                    'rx_gro': rx_gro,
                    'rx_ip': rx_ip,
                    'rx_tcp': rx_tcp,
                    'rx_read': rx_read,
                    'rx_sleep': rx_sleep,
                    'rx_ready': rx_ready,
                    'rx_wake_up': rx_wake_up,
                    'rx_data_copy': rx_data_copy,
                    'rx_return': rx_return,
                    'tx_alloc': tx_alloc,
                    'tx_write': tx_write,
                    'tx_data_copy': tx_data_copy,
                    'tx_tcp': tx_tcp,
                    'tx_ip': tx_ip,
                    'tx_queue': tx_queue,
                    'tx_xmit': tx_xmit,
                    'tx_finish': tx_finish
                })
                # if rx_data_copy - rx_ready > 800000:
                #     sys.stderr.write(line + "\n")

    # Calculate latencies
    latencies = {}
    for port, ss in samples.items():
        latencies[port] = []
        for ts in ss:
            if ts['rx_ready'] > ts['rx_wake_up']:
                ts['rx_wake_up'] = ts['rx_ready']

            latencies[port].append({
                #'rx_irq': ts['rx_napi'] - ts['rx_irq'],
                #'rx_napi': ts['rx_gro'] - ts['rx_napi'],
                'rx_irq': ts['rx_alloc'] - ts['rx_hw'],
                'rx_napi': ts['rx_gro'] - ts['rx_alloc'],
                #'rx_gro': ts['rx_ip'] - ts['rx_gro'],
                'rx_ip': ts['rx_tcp'] - ts['rx_gro'],
                'rx_tcp': ts['rx_ready'] - ts['rx_tcp'],
                'rx_sched': ts['rx_data_copy'] - ts['rx_ready'],
                'rx_data_copy': ts['rx_return'] - ts['rx_data_copy'],
                'app': ts['tx_write'] - ts['rx_return'],
                'tx_data_copy': ts['tx_tcp'] - ts['tx_write'],
                'tx_tcp': ts['tx_ip'] - ts['tx_tcp'],
                'tx_ip': ts['tx_queue'] - ts['tx_ip'],
                'tx_queue': ts['tx_xmit'] - ts['tx_queue'],
                'tx_xmit': ts['tx_finish'] - ts['tx_xmit'],
                #'full': ts['tx_finish'] - ts['rx_irq'],
                'full': ts['tx_finish'] - ts['rx_hw'],
            })
    for port in latencies.keys():
        latencies[port].sort(key = lambda x: x['full'])
    # Average and tail atencies
    sum = {}
    num = {}
    avg = {}
    tails = {}
    tail = {}
    tail999 = {}
    for port, ls in latencies.items():
        sum[port] = {}
        num[port] = {}
        for ts in ls:
            for k, v in ts.items():
                if k not in sum[port]:
                    sum[port][k] = 0
                    num[port][k] = 0
                sum[port][k] += v
                num[port][k] += 1
    for port, ts in sum.items():
        avg[port] = {}
        for k, v in ts.items():
            avg[port][k] = round(v / num[port][k], 3)
    for port, ls in latencies.items():
        tails[port] = {}
        for ts in ls:
            for k, v in ts.items():
                if k not in tails[port]:
                    tails[port][k] = []
                tails[port][k].append(v)
    for port, ts in tails.items():
        tail[port] = {}
        for k, v in ts.items():
            # v.sort()
            tail[port][k] = (v)[round(0.99 * len(v)) - 1]
    for port, ts in tails.items():
        tail999[port] = {}
        for k, v in ts.items():
            v.sort()
            tail999[port][k] = (v)[round(0.999 * len(v)) - 1]

    # Print latency breakdown
    # categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit', 'full']
    return tail999

def get_metadata(DIR):
    f = os.path.join(DIR, "client.log")
    f_client = os.path.join(DIR, "latencies-{}.log".format(8))
    f_server = os.path.join(DIR, "latencies-{}-server.log".format(8))
    client_latency_breakdown = get_latency_breakdown(f_client, True)
    server_latency_breakdown = get_latency_breakdown(f_server, False)
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            if "cpu" not in line:
                continue
            t = thread_data()
            params = line.split()
            t.start_client_time = float(params[0])
            t.client_core = int(params[2])
            t.client_pid = int(params[4])
            t.client_port = int(params[7])
            thread_dict[t.client_port] = t

    f = os.path.join(DIR, "server.log")
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            if "core" not in line:
                continue
            params = line.split()
            t = thread_dict[int(params[7])]
            t.start_server_time = float(params[0])
            t.server_core = int(params[2])
            t.server_pid = int(params[4])
            thread_dict[t.client_port] = t
    for key in thread_dict:
        t = thread_dict[key]
        num = str(int(key) - 10000)
        f = os.path.join(DIR, "netperf-{}_thpt.log".format(num))
        with open(f, "r") as file:
            lines = file.readlines()
            params = lines[0].split()
            t.latency = params[4]
            t.thpt = params[5]
        t.client_rx_sched = client_latency_breakdown[int(key)]['rx_sched'] / 1000.0
        t.server_rx_sched = server_latency_breakdown[int(key)]['rx_sched'] / 1000.0
        # print (t.client_rx_sched, t.server_rx_sched)

def get_runtime(filename, result):
    # Sample input lines
    with open(filename, 'r') as file:
        # Read the lines of the file
        lines = file.readlines()
        current_pid = None
        runtime_sum = 0
        pid_data = {}
        init_runtime = {}
        total_runtime = {}
        result_init_runtime = {}
        # Parse the lines and store data in the dictionary
        for line in lines:
            if "Q:Reg" in line:
                continue
            waking_match = re.search(waking_pattern, line)
            runtime_match = re.search(runtime_pattern, line)
            switch_match = re.search(switch_pattern, line)
            pid = int(line.split()[1])
            core = int(line.split()[2].strip('[]'))
            timestamp = float(line.split()[3][:-1])
            if waking_match:
                command = waking_match.group(1)
                current_pid = int(waking_match.group(2))
                waking_timestamp = float(line.split()[3][:-1])
                if current_pid not in pid_data:
                    pid_data.setdefault(current_pid, {'waking_timestamp': waking_timestamp, 'first_run_timestamp': 0, 'total_runtime': 0 ,
                        'runtime_sum': 0, 'after_queue_delay': 0, 'core_id': core, 'wait_time': 0, 'model_wait_time': 0, 'name': 0})
                    result[current_pid] = []
                # get the timestamp data 
                # if pid_data[current_pid]['queue_delay'] >= 200:
                #     print (current_pid, pid_data[current_pid]['waking_timestamp'],pid_data[current_pid]['queue_delay'] )
                result[current_pid].append([
                    pid_data[current_pid]['waking_timestamp'], 
                    pid_data[current_pid]['runtime_sum'], 
                    pid_data[current_pid]['after_queue_delay'],
                    pid_data[current_pid]['wait_time'], 
                    pid_data[current_pid]['first_run_timestamp'], 
                    pid_data[current_pid]['total_runtime']])
                # reintialize 
                pid_data[current_pid]['waking_timestamp'] = waking_timestamp
                pid_data[current_pid]['runtime_sum'] = 0
                pid_data[current_pid]['after_queue_delay'] = 0
                pid_data[current_pid]['wait_time'] = 0
                pid_data[current_pid]['first_run_timestamp'] = 0
                pid_data[current_pid]['core_id'] = core
                pid_data[current_pid]['model_wait_time'] = 0
                pid_data[current_pid]['name'] = command
                pid_data[current_pid]['total_runtime'] = total_runtime[core]
                for key in pid_data.keys():
                    if pid_data[key]['runtime_sum'] == 0 and key != current_pid and core == pid_data[key]['core_id']:
                        pid_data[key]['after_queue_delay'] += 1
            if switch_match:
                next_pid = int(switch_match.group(2))
                if next_pid in pid_data:
                    if pid_data[next_pid]['runtime_sum'] == 0:
                        pid_data[next_pid]['first_run_timestamp'] = timestamp
                        pid_data[next_pid]['wait_time'] = timestamp - pid_data[next_pid]['waking_timestamp']
                        pid_data[next_pid]['total_runtime'] = total_runtime[core] - pid_data[next_pid]['total_runtime']
            if runtime_match:
                # if float(line.split()[3][:-1]) <= 14357.926627 and  float(line.split()[3][:-1]) >= 14357.925395 and core == 0:
                #     print (line)
                command = runtime_match.group(1)
                current_pid = int(runtime_match.group(2))
                runtime = int(runtime_match.group(3))
                vruntime =  float(runtime_match.group(4))
                if core not in total_runtime:
                    total_runtime[core] = 0
                total_runtime[core] += runtime
                if current_pid in pid_data:
                    # if timestamp >= 51292.938210 and timestamp <= 51292.939174 and core == 0:
                    #     print(pid, runtime)
                    # if pid_data[current_pid]['runtime_sum'] == 0:
                        # figure out 
                    pid_data[current_pid]['runtime_sum'] += runtime
                if core not in init_runtime:
                    init_runtime[core] = {}
                if current_pid == pid and ("netdriver" in command or "pingpong" in command):
                    if current_pid not in init_runtime[core]:
                        init_runtime[core][current_pid] = vruntime * 88761 / 1024
                        result_init_runtime[core] = {}
                        result_init_runtime[core] = deepcopy(init_runtime[core])
                    else:
                        init_runtime[core][current_pid] = vruntime * 88761 / 1024
   # * 88761 / 1024
            # if switch_match:
    for core in result_init_runtime:
        smallest = min(result_init_runtime[core].values())
        for pid in result_init_runtime[core]:
            result_init_runtime[core][pid] -= smallest 
    return result, result_init_runtime

def get_e2e_runtime(runtime, client_pid, server_pid, client_starttime, server_starttime, client_init, server_init, client_core, server_core):
    result = []
    i = 0
    j = 0
    client_runtime = runtime[client_pid]
    server_runtime = runtime[server_pid]
    for i in range(len(client_runtime)):
        if client_runtime[i][0] > client_starttime:
            break
    i += 1
    for j in range(len(server_runtime)):
        if server_runtime[j][0] > server_starttime:
            break
    while i < len(client_runtime) and j  < len(server_runtime):
        result.append([
            client_init / 1000.0, server_init / 1000.0, client_core, server_core,
            (client_runtime[i][3] + server_runtime[j][3]) * 1000000.0,  # rx_sched
            client_runtime[i][3] * 1000000.0, server_runtime[j][3] * 1000000.0, # client rx_sched, server rx_sched
            client_runtime[i][5]/ 1000.0, client_runtime[i][3] * 1000000.0 - client_runtime[i][5] / 1000.0, # client threads'runtime in rxsched, client irq time,
            server_runtime[j][5] / 1000.0, server_runtime[j][3] * 1000000.0 - server_runtime[j][5] / 1000.0, # server threads' runtime in rx_sched, server irq time
            client_runtime[i][2], server_runtime[j][2],  # client queuing delay, server queuing delay
            client_runtime[i][1] + server_runtime[j][1], # runtime-sum
            client_runtime[i][4], server_runtime[j][4] # client firstrun timestamp, server firstrun timestamp
        ])
        # result.append(client_runtime[i][2] + server_runtime[j + 1][2])
        i += 1
        j += 1
    return result
    

def print_value(client_pid, server_pid, latency, client_rx_sched, server_rx_sched, result):
    first_column = [row[4] for row in result if len(row) > 0]  # Protect against empty rows
    column_mean = sum(first_column) / len(first_column)
    sort_array = sorted(result, key=lambda row: row[4])
    p999_value = sort_array[int(0.999 * len(sort_array))]
    print (client_pid, server_pid, latency, client_rx_sched, server_rx_sched, " ".join(map(str, p999_value)))

def main():
    DIR = sys.argv[1]
    runtime = {}
    get_metadata(DIR)
    runtime, client_init = get_runtime(DIR + "client_perf.log", runtime)
    runtime, server_init = get_runtime(DIR + "server_perf.log", runtime)
    total = []
    for port in thread_dict.keys():
        thread = thread_dict[port]
        # if thread.client_core == thread.server_core:
        #     print(thread.client_core, thread.server_core, thread.latency)
        
        result = get_e2e_runtime(runtime, thread.client_pid, thread.server_pid, thread.start_client_time, thread.start_server_time,
            client_init[thread.client_core][thread.client_pid], server_init[thread.server_core][thread.server_pid], thread.client_core, thread.server_core)
        # total += result
        print_value(thread.client_pid, thread.server_pid, thread.latency, thread.client_rx_sched, thread.server_rx_sched, result)
    # print_value(0,0, total)
    # for port in thread_dict.keys():
    #     thread = thread_dict[port]
    #     if thread.client_core != thread.server_core:
    #         print(thread.client_core, thread.server_core, thread.latency)
main()