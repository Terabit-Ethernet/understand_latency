import os
import re
import subprocess
from itertools import product

# Define parameters
hd=1000
our_patch=0
c_state=1
num_apps = [8]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [100]
cores = [1]
runs = [0,1,2,3,4]
breakdown = False

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

class thread_data:
    client_core = 0
    client_pid = 0
    client_port = 0
    server_core = 0
    server_pid = 0
    # server_port = 0
    thpt = 0
    latency = 0

categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit']

def netfilter_output(DIR):
    client_dict = {}
    server_dict = {}
    f = os.path.join(DIR, "filter_client.log")
    with open(f, "r") as file:
        lines = file.readlines()
        i = 0
        while i < len(lines):
            params = lines[i].split()
            start_index = 0
            while "Core:" not in params[start_index]:
                start_index += 1
            start_index += 1
            params_thread_id = lines[i].split()[start_index:]
            count_array = lines[i + 1].split()[start_index:]

            for k in range(len(params_thread_id)):
                client_dict[int(params_thread_id[k])] = int(count_array[k]);
            i += 2

    f = os.path.join(DIR, "filter_server.log")
    with open(f, "r") as file:
        lines = file.readlines()
        start_index = 8
        i = 0
        while i < len(lines):
            params = lines[i].split()
            start_index = 0
            while "Core:" not in params[start_index]:
                start_index += 1
            start_index += 1
            params_thread_id = lines[i].split()[start_index:]
            count_array = lines[i + 1].split()[start_index:]

            for k in range(len(params_thread_id)):
                server_dict[int(params_thread_id[k])] = int(count_array[k]);
            i += 2
    return client_dict, server_dict

def get_e2e_log(DIR):
    thread_dict = {}
    f = os.path.join(DIR, "client.log")
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            if "cpu" not in line:
                continue
            t = thread_data()
            params = line.split()
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
            t.server_core = int(params[2])
            t.server_pid = int(params[4])
            thread_dict[t.client_port] = t
    return thread_dict

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

def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(DIR)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run))

def main():
    # Generate all combinations
    mean_total = 0
    l999_total = 0
    thpt_total = 0
    irq_client_total = 0
    irq_server_total = 0
    rx_sched_client_total = 0
    rx_sched_server_total = 0
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)

    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        print(DIR)
        thread_dict = get_e2e_log(DIR)
        netfilter_client, netfilter_server = netfilter_output(DIR)
        for i in range(n):
            flow_log = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
            with open(flow_log, "r") as file:
                lines = file.readlines()
                for line in lines:
                    params = line.split()
                    port = int(params[1])
                    latency = float(params[4])
                    thpt = float(params[5])
                    t = thread_dict[port]
                    t.thpt = thpt
                    t.latency = latency
                    thread_dict[port] = t
        for key in thread_dict:
            t = thread_dict[key]
            print(t.latency, t.thpt, netfilter_client[t.client_pid] + netfilter_server[t.server_pid])

main()
