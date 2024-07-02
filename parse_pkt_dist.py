import os
import re
import subprocess
import numpy as np
from itertools import product

# Define parameters
hd="testing"
our_patch=1
c_state=1
num_apps = [8]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [32, 64, 128]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]
breakdown = False
rx_sched_only = False

# sys = "linux"

# Define the configuration data
config_data = """[settings]
hd= {}
our_patch= {}
c_state = {}
num_apps = {}
flowsize = {}
iodepth = {}
dim = {}
pin = {}
permute = {}
hrtick = {}
sched = {}
cores = {}
runs = {}
"""

def extract_values_after_bracket(line):
    bracket_pos = line.find(']')
    if bracket_pos != -1:
        # Extract everything after ']'
        return line[bracket_pos + 1:].strip().split()[1:]
    return None

def pkt_dist_output(DIR):
    client_dict = []
    server_dict = []
    f = os.path.join(DIR, "pkt_dist_client.log")
    with open(f, "r") as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            result = []
            if("size:" in lines[i] or "buffer: " in lines[i] or "perf:" in lines[i] or "Hardware Error" in lines[i]):
                i += 1
                continue

            params = extract_values_after_bracket(lines[i])
            start_index = 1
            for p in params:
                try:
                    result.append(float(p))
                except:
                    i += 1
                    continue
            i += 1
            client_dict.append(result)

    f = os.path.join(DIR, "pkt_dist_server.log")
    with open(f, "r") as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            result = []
            if("size:" in lines[i] or "buffer: " in lines[i] or "perf:" in lines[i]  or "Hardware Error" in lines[i]):
                i += 1
                continue
            params = extract_values_after_bracket(lines[i])
            start_index = 1
            for p in params:
                try:
                    result.append(float(p))
                except:
                    i += 1
                    continue
            i += 1
            server_dict.append(result)


    client_dict = np.mean(np.array(client_dict), axis=0)
    server_dict = np.mean(np.array(server_dict), axis=0)
    client_sum = np.sum(np.array(client_dict))
    server_sum = np.sum(np.array(server_dict)) 
    return client_dict / client_sum, server_dict / server_sum

def get_latency_thpt_num(DIR):
    latency_file_name = DIR + "/latency.log"
    thpt_file_name = DIR + "/linux_latency"
    with open(latency_file_name, 'r') as file:
        line = file.readlines()[0]
        mean = float(line.split()[0])
        l_999 = float(line.split()[2])
    with open(thpt_file_name, 'r') as file:
        thpt = float(file.readlines()[1].split()[0])
    return mean, l_999, thpt

def get_average_size(DIR):
    client_dict = {}
    server_dict = {}
    f = os.path.join(DIR, "pkt_dist_client.log")
    with open(f, "r") as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            result = []
            if("size:"  not in lines[i] and "rx buffer" not in lines[i]):
                i += 1
                continue
            params = extract_values_after_bracket(lines[i])
            if "size" in lines[i]:
                client_dict['size'] = float(params[1])
            if "rx buffer" in lines[i]:
                client_dict['rx_buffer'] = float(params[1][:-1])
                client_dict['tx_buffer'] = float(params[3])
                client_dict['tail'] = float(params[6])
            i += 1

    f = os.path.join(DIR, "pkt_dist_server.log")
    with open(f, "r") as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            result = []
            if("size:"  not in lines[i] and "rx buffer" not in lines[i]):
                i += 1
                continue
            params = extract_values_after_bracket(lines[i])
            if "size" in lines[i]:
                server_dict['size'] = float(params[1])
            if "rx buffer" in lines[i]:
                server_dict['rx_buffer'] = float(params[1][:-1])
                server_dict['tx_buffer'] = float(params[3])
                server_dict['tail'] = float(params[6])

            i += 1
    return client_dict, server_dict

def get_average_overrun(key, arr):
    total = 0.0
    for value in arr:
        total += value[key]
    return total / len(arr)

def main():
    # Generate all combinations
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    result_server = []
    result_client = []
    result_client_dict = {}
    result_server_dict = {}
    result_meta_client = []
    result_meta_server = []
    thpt_total = 0
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        # print(DIR)
        # pkt_dist_client, pkt_dist_server = pkt_dist_output(DIR)
        meta_client, meta_server = get_average_size(DIR)
        # result_server.append(pkt_dist_server)
        # result_client.append(pkt_dist_client)
        result_meta_client.append(meta_client)
        result_meta_server.append(meta_server)
        mean,l_999, thpt = get_latency_thpt_num(DIR)
        thpt_total += thpt
        if run == len(runs) - 1:
            result_server = np.mean(np.array(result_server), axis=0)
            result_client = np.mean(np.array(result_client), axis=0)
            str_client = ""
            str_server = ""
            # for element in result_client:
            #     str_client += " {:.2f}".format(element)
            # for element in result_server:
            #     str_server += " {:.2f}".format(element)
            
            # print(n, "client", str_client)
            # print(n, "server", str_server)
            # result_client_dict[n] = result_client
            # result_server_dict[n] = result_server 
            # get average value over runs
            ret_str = ""
            ret_str += " {} {} {} {} {} {} {} {}".format(get_average_overrun("size", result_meta_client),
                get_average_overrun("rx_buffer", result_meta_client) / cores[0] / 2, 
                get_average_overrun("tx_buffer", result_meta_client) / cores[0] / 2,
                get_average_overrun("tail", result_meta_client) / cores[0] / 2,
                get_average_overrun("size", result_meta_server),
                get_average_overrun("rx_buffer", result_meta_server) / cores[0] / 2, 
                get_average_overrun("tx_buffer", result_meta_server) / cores[0] / 2,
                get_average_overrun("tail", result_meta_server) / cores[0] / 2)
            print("{} {} {}".format(i, ret_str, thpt_total / len(runs)))
            result_meta_server = []
            result_meta_client = []
            result_server = []
            result_client = []
            thpt_total = 0
    # get packet distribution
    # keys = sorted(result_server_dict.keys())
    # # print(result_client_dict)
    # for i in range(0, 32):
    #     print_str = "{}".format(i + 1)
    #     for key in keys:
    #         print_str +=  " {:.2f}".format(result_client_dict[key][i])
    #     print(print_str)
    # for i in range(0, 32):
    #     print_str = "{}".format(i + 1)
    #     for key in keys:
    #         print_str +=  " {:.2f}".format(result_server_dict[key][i])
    #     print(print_str)
main()
