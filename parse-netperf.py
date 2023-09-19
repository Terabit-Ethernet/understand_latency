#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
# Parse args
if len(sys.argv) < 3:
    print("usage: parse-netperf.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])

# Parse netperf files
results = []
total_thpt = 0

def sched_latency():
    client_dict = {}
    server_dict = {}
    client_temp_dict = {}
    server_temp_dict = {}
    client_tick_dict = {}
    server_tick_dict = {}
    f = os.path.join(DIR, "client_sched_latency.log")
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            if "sched:sched_waking:" not in line:
                continue
            params = line.split()
            app = params[0]
            thread_id = int(params[1])
            comm = params[5]
            pid = params[6]
            if "pingpong_server" not in app and "netdriver_test_" not in app:
                continue
            if "pingpong_server" not in comm and "netdriver_test_" not in comm:
                continue 
            if thread_id not in client_dict:
                client_dict[thread_id] = 1
                client_temp_dict[thread_id] = {}
            else:
                client_dict[thread_id] += 1
            client_temp_dict[thread_id][pid] = 1

    f = os.path.join(DIR, "server_sched_latency.log")
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            if "sched:sched_waking:" not in line:
                continue
            if "Reg" in line:
                continue
            params = line.split()
            app = params[0]
            thread_id = int(params[1])
            comm = params[5]
            pid = params[6]
            if "pingpong_server" not in app and "netdriver_test_" not in app:
                continue
            if "pingpong_server" not in comm and "netdriver_test_" not in comm:
                continue 
            if thread_id not in server_dict:
                server_dict[thread_id] = 1
                server_temp_dict[thread_id] = {}
                server_tick_dict[thread_id] = 0
            else:
                server_dict[thread_id] += 1
            server_temp_dict[thread_id][pid] = 1
        
        # print per-second info
        tick = 0
        for line in lines:
            if "sched:sched_waking:" not in line:
                continue
            if "Reg" in line:
                continue
            params = line.split()
            app = params[0]
            thread_id = int(params[1])
            time = float(params[3][:-1])
            comm = params[5]
            pid = params[6]
            if "pingpong_server" not in app and "netdriver_test_" not in app:
                continue
            if "pingpong_server" not in comm and "netdriver_test_" not in comm:
                continue 
            if thread_id not in server_dict:
                server_tick_dict[thread_id] = 1
            else:
                server_tick_dict[thread_id] += 1
            if time > tick + 0.1:
                output_str = ""
                for thread_id in sorted(server_tick_dict):
                    output_str += "{} ".format(server_tick_dict[thread_id])
                    server_tick_dict[thread_id] = 0
                sys.stderr.write(output_str + "\n")
                tick = time

    # for thread_id in client_temp_dict:
    #     output_str = "{}".format(thread_id)
    #     for key in client_temp_dict[thread_id]:
    #         output_str += " " + key
    #     print(output_str)

    # for thread_id in server_temp_dict:
    #     output_str = "{}".format(thread_id)
    #     for key in server_temp_dict[thread_id]:
    #         output_str += " " + key
    #     print(output_str)
    return client_dict, server_dict

def netfilter_output():
    client_dict = {}
    server_dict = {}
    f = os.path.join(DIR, "client_netfilter.log")
    with open(f, "r") as file:
        lines = file.readlines()
        start_index = 7
        for line in lines:
            thread_id = 0
            params = line.split()
            for i in range(len(params) - start_index):
                if (i) not in client_dict:
                    client_dict[i] = []
                client_dict[i].append(int(params[i + start_index]))

    f = os.path.join(DIR, "server_netfilter.log")
    with open(f, "r") as file:
        lines = file.readlines()
        start_index = 7
        for line in lines:
            thread_id = 0
            params = line.split()
            for i in range(len(params) - start_index):
                if (i) not in server_dict:
                    server_dict[i] = []
                server_dict[i].append(int(params[i + start_index]))
    return client_dict, server_dict

def netfilter_output_2():
    client_dict = {}
    server_dict = {}
    f = os.path.join(DIR, "client_netfilter.log")
    with open(f, "r") as file:
        lines = file.readlines()
        start_index = 7
        i = 0
        while i < len(lines):
            params_thread_id = lines[i].split()[start_index:]
            count_array = lines[i + 1].split()[start_index:]

            for k in range(len(params_thread_id)):
                client_dict[int(params_thread_id[k])] = int(count_array[k]);
            i += 2

    f = os.path.join(DIR, "server_netfilter.log")
    with open(f, "r") as file:
        lines = file.readlines()
        start_index = 7
        i = 0
        while i < len(lines):
            params_thread_id = lines[i].split()[start_index:]
            count_array = lines[i + 1].split()[start_index:]

            for k in range(len(params_thread_id)):
                server_dict[int(params_thread_id[k])] = int(count_array[k]);
            i += 2
    return client_dict, server_dict

def get_e2e_netfilter(thread_dict, client_dict, server_dict):
    e2e_dict = {}
    client_e2e_dict = {}
    server_e2e_dict = {}
    f = os.path.join("netfilter.log")

    rows = 0
    for key in sorted(thread_dict.keys()):
        t = thread_dict[key]
        e2e_dict[key] = []
        client_e2e_dict[key] = []
        server_e2e_dict[key] = []
        client_index = t.client_pid % len(thread_dict)
        server_index = t.server_pid % len(thread_dict)
        rows = len(client_dict[client_index])
        for i in range(len(client_dict[client_index])):
            e2e_dict[key].append(client_dict[client_index][i] + server_dict[server_index][i])
            client_e2e_dict[key].append(client_dict[client_index][i])
            server_e2e_dict[key].append(server_dict[server_index][i])
    with open(f, "w") as file:
        for i in range(rows):
            output_str = ""
            for key in sorted(e2e_dict.keys()):
                output_str += "{} ,".format(e2e_dict[key][i])
            file.write("{}\n".format(output_str))

    f = os.path.join("client_netfilter.log")     
    with open(f, "w") as file:
        for i in range(rows):
            output_str = ""
            for key in sorted(client_e2e_dict.keys()):
                output_str += "{} ,".format(client_e2e_dict[key][i])
            file.write("{}\n".format(output_str))  

    f = os.path.join("server_netfilter.log")     
    with open(f, "w") as file:
        for i in range(rows):
            output_str = ""
            for key in sorted(server_e2e_dict.keys()):
                output_str += "{} ,".format(server_e2e_dict[key][i])
            file.write("{}\n".format(output_str))  

    return e2e_dict
class thread_data:
    client_core = 0
    client_pid = 0
    client_port = 0
    server_core = 0
    server_pid = 0
    # server_port = 0
    thpt = 0
    latency = 0

# client_sched_dict, server_sched_dict = sched_latency()

thread_dict = {}
f = os.path.join(DIR, "client.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "cpu" not in line:
            continue
        t = thread_data()
        params = line.split()
        t.client_core = int(params[1])
        t.client_pid = int(params[3])
        t.client_port = int(params[6])
        thread_dict[t.client_port] = t

f = os.path.join(DIR, "server.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "core" not in line:
            continue
        params = line.split()
        t = thread_dict[int(params[6])]
        t.server_core = int(params[1])
        t.server_pid = int(params[3])
        thread_dict[t.client_port] = t

# client_netperf_dict, server_netperf_dict = netfilter_output()
# e2e_netfilter_dict = get_e2e_netfilter(thread_dict, client_netperf_dict, server_netperf_dict)

# client_netfilter2_dict, server_netfilter2_dict = netfilter_output_2()
# print ('''port, client_core, server_core, client_pid, server_pid, thpt, latency, total_netfilter_pkt''')
for i in range(0, N ):
    f = os.path.join(DIR, "netperf-{}.log".format(i))
    lines = []
    with open(f, "r") as file:
        lines = file.readlines()
        num = 0
        temp_result = []
        for line in lines:
            params = line.split()
            time = float(params[2])
            if num > 10000000:
                break
            results.append(time)
            temp_result.append(time)
            num += 1
    f = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
    temp_result.sort()
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            params = line.split()
            port = int(params[1])
            thpt = float(params[5])
            # latency = np.percentile(temp_result, 99.9)
            total_thpt += thpt
            t = thread_dict[port]
            t.thpt = thpt
            # t.latency = latency
            thread_dict[port] = t

# for key in sorted(thread_dict.keys()):
#     t = thread_dict[key]
#     # total_netfilter_pkt = sum(e2e_netfilter_dict[key])
#     # total_netfilter_pkt = client_netfilter2_dict[t.client_pid] + server_netfilter2_dict[t.server_pid]
#     total_netfilter_pkt = 0
#     f = os.path.join("results/our_mc_64_32_1_0/", "linux_latency_breakdown_c")
#     with open(f, "r") as file:
#         lines = file.readlines()
#         times = 0
#         for line in lines:
#             params = line.split()
#             if "port" in line:
#                 continue
#             port = int(params[0])
#             if port == t.client_port:
#                 if times == 0:
#                     client_irq = float(params[1])
#                     client_rx_sched = float(params[5]) 
#                     client_latency = float(params[13])
#                 if times == 2:
#                     client_irq_999 = float(params[1])
#                     client_rx_sched_999 = float(params[5]) 
#                     client_latency_999 = float(params[13])
#                 times += 1
#     f = os.path.join("results/our_mc_64_32_1_0/", "linux_latency_breakdown_s")
#     with open(f, "r") as file:
#         lines = file.readlines()
#         times = 0
#         for line in lines:
#             params = line.split()
#             if "port" in line:
#                 continue
#             port = int(params[0])
#             if port == t.client_port:
#                 if times == 0:
#                     server_irq = float(params[1])
#                     server_rx_sched = float(params[5]) 
#                     server_latency = float(params[13])
#                 if times == 2:
#                     server_irq_999 = float(params[1])
#                     server_rx_sched_999 = float(params[5]) 
#                     server_latency_999 = float(params[13])
#                 times += 1
    # if t.client_pid in client_sched_dict:
    #     client_interrupt = client_sched_dict[t.client_pid]
    # else:
    #     client_interrupt = 0
    # if t.server_pid in server_sched_dict:
    #     server_interrupt = server_sched_dict[t.server_pid]
    # else:
    #     server_interrupt = 0
    # print ('''port:, {}, client_core:, {}, server_core:, {}, client_pid:, {}, server_pid:, {}, thpt:, {}, latency:, {}, client_irq_mean:, {}, client_rx_sched_mean:, {}, client_latency_mean:, {}, client_irq_999:, {}, client_rx_sched_999:, {}, client_latency_999:, {}, server_irq_mean:, {}, server_rx_sched_mean:, {}, server_latency_mean:, {}, server_irq_999:, {}, server_rx_sched_999:, {}, server_latency_999:, {}, client_interrupt:, {}, server_interrupt:, {}, total_interrupt:, {},'''
    #     .format(t.client_port, t.client_core, t.server_core, t.client_pid, t.server_pid, t.thpt, t.latency,
    #     client_irq, client_rx_sched, client_latency, client_irq_999, client_rx_sched_999, client_latency_999,
    #     server_irq, server_rx_sched, server_latency, server_irq_999, server_rx_sched_999, server_latency_999,
    #     client_interrupt, server_interrupt, client_interrupt + server_interrupt))
    # print ('''{}, {}, {}, {}, {}, {}, {}, {}'''
    # .format(t.client_port, t.client_core, t.server_core, t.client_pid, t.server_pid, t.thpt, t.latency, total_netfilter_pkt))
results.sort()
# Print the netperf latencies
categories = ['m_lat', 'p99_lat', 'p999_lat']
print("{}\t{}\t{}".format('m_lat','p99_lat',  'p999_lat', "thpt"))

print("{}\t".format(total_thpt))

