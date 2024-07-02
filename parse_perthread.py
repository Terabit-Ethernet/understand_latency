import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
# Define parameters
hd="testing_perf"
our_patch="1"
c_state=1
num_apps = [56]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [12]
breakdown = False

# sys = "linux"
runtime_pattern = r'sched_stat_runtime.*comm=(netdriver_test_|pingpong_server) pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]'

cmap = plt.get_cmap('tab20')  # tab20 has 20 colors, use tab20b or tab20c for different shades, or a combination
colors = [cmap(i) for i in range(28)]

# Create a dictionary to store colors for each key
color_dict = {}

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

# Function to format the tick labels
def scientific_format(tick_val, pos):
    return "{:.0e}".format(tick_val)
    
def readFile(file):
    results = []
    f = open(file)
    lines = f.readlines()
    for line in lines:
        if "netdriver" in line or "pingpong_server" in line:
            results.append(line)
    return results


def checkDistribution2(results, flows, filename):

    vruntime_dict = {}
    wakingtime_dict = {}
    switch_dict = {}
    print_time = 0
    total_dict = {}
    total = 0
    pid2cpu = {}
    for line in results:
        params = line.split()
        if "Q:Reg" in line:
            continue
        if len(line.split()) < 4:
            continue
        try:
            time = float(line.split()[3][:-1])
        except:
            print(line)
        runtime_match = re.search(runtime_pattern, line)
        # if "sched:sched_waking:" == params[4]:
        #     pid = int(params[6].split("=")[1])
        #     if  (pid < 5000):
        #         continue
        #     wakingtime_dict[pid] = time 
        core = int(line.split()[2].strip('[]'))
        current_pid = int(line.split()[1])
        pid2cpu[current_pid] = core
        if runtime_match and core == 0:
            pid = int(runtime_match.group(2))
            runtime = int(runtime_match.group(3))
            vruntime =  float(runtime_match.group(4))
            vruntime_dict[pid] = vruntime
            if pid not in switch_dict:
                if vruntime >= 1e11:
                    print(pid, vruntime)
                    switch_dict[pid] = vruntime
            # if pid in wakingtime_dict and time - wakingtime_dict[pid] > 0.001:
            #     # print time, "pid,", pid, time - wakingtime_dict[pid]
            #     mini = -1
            #     for key in vruntime_dict:
            #         if mini == -1:
            #             mini = vruntime_dict[key]
            #         elif mini  > vruntime_dict[key]:
            #             mini = vruntime_dict[key]
            #     for key in vruntime_dict:
            #         # if vruntime_dict[key] - mini > 10000000:
            #         #     continue
            #         # print key, vruntime_dict[key] - mini
            #         if key not in total_dict:
            #             total_dict[key] = 0
            #         total_dict[key] += vruntime_dict[key] - mini
            #         total += 1.0
            if time - print_time > 1:
                mini = -1
                if len(vruntime_dict) != flows:
                    # print(vruntime_dict)
                    print_time = time
                    print("len", len(vruntime_dict))
                    if len(vruntime_dict) > flows:
                        vruntime_dict = {}
                   # vruntime_dict = {}
                    continue
                # if total < 3:
                #     total += 1.0
                #     print_time = time
                #     continue
                for key in vruntime_dict:
                    if mini == -1:
                        mini = vruntime_dict[key]
                    elif mini  > vruntime_dict[key]:
                        mini = vruntime_dict[key]
                # print time
                # vruntime_dict= sorted(vruntime_dict.items(), key=lambda x: x[1])
                # str = ""
                for key in vruntime_dict:
                    # str += " {}".format((element[1] - mini) * 88761 / 1024 / 1000)
                    if key not in total_dict:
                        total_dict[key] = []
                    total_dict[key].append(vruntime_dict[key] - mini)
                    # print(key, (vruntime_dict[key] - mini) * 88761 / 1024 / 1000)
                    # # print key, vruntime_dict[key] - mini
                # print (str)
                total += 1.0
                print_time = time
                # vruntime_dict = {}
                    # break
    # print (total)
    i = 0
    # skip the fist time
    total -= 1.0
    return_dict = total_dict
    print(filename)
    total_dict = sorted(total_dict.items(), key=lambda x: sum(x[1]))
    with open(filename, "w+") as file:
        for element in total_dict:
            if pid2cpu[element[0]] == 0:
                file.write("{} {} {} {}\n".format(i, sum(element[1]) / total * 88761 / 1024 / 1000, stdev(np.array(element[1]) * 88761 / 1024 / 1000), element[0]))
                i += 1
                # for key in vruntime_dict:
                #     if vruntime_dict[key] > 2e10:
                #         print key, vruntime_dict[key]
            #     del wakingtime_dict[pid]
    return return_dict

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

def draw_lins(total_dict, name):
    # Number of lines
    num_lines = len(total_dict)
    # Create a new figure
    fig, ax = plt.subplots(figsize=(10, 6))
    # plt.figure(figsize=(10, 6))
    # plt.ylim(top=10000000)
    ax.set_ylim((1, 10000000))

    plt.yscale("log") 
    for index, key in enumerate(sorted(total_dict.keys())):
        print(key)
        y_values = total_dict[key]
        x_values = []
        value = 0
        for i in y_values:
            x_values.append(value)
            value += 1
        # Assign a color from the generated colors
        color = colors[index % len(colors)]
        color_dict[key] = color
        
        plt.plot(np.array(x_values), np.array(y_values), label=f'{key}', color=color)
    # Generating 32 lines
    # for i in range(1, num_lines + 1):
    #     x = np.linspace(0, 10, 100)  # 100 linearly spaced numbers
    #     y = i * x  # y = i * x, where i is the slope of each line
    #     plt.plot(x, y, label=f'Line with slope {i}')

    # Add title and labels
    # plt.title('32 Lines with Different Slopes')
    ax.set_xlabel('Time(s)', fontsize=16)
    ax.set_ylabel('Relative Vruntime(ns)', fontsize=16)
    ax.tick_params(axis='x', labelsize=14)
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, linestyle='--', color='grey', alpha=0.7)
    for spine in ax.spines.values():
        spine.set_linewidth(2)
    # Add a legend
#    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    # plt.tick_params(axis='y', direction='in', labelleft=True, labelright=False)

    # Show the plot
    plt.tight_layout()
    yticks = [1e-2, 1, 1e2, 1e4, 1e6, 1e8]
    plt.yticks(yticks, ["0.01", "1", "10^2", "10^4", "10^6", "10^8"])
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.1)
    plt.gca().yaxis.set_major_formatter(FuncFormatter(scientific_format))
    plt.savefig(name)
    # plt.show()

def draw_scatter(thread_dict, name):
    x = []
    y = []
    # Create a new figure
    fig, ax = plt.subplots(figsize=(10, 6))
    # plt.figure(figsize=(10, 6))
    # plt.ylim(top=10000000)
    # ax.set_xlim(0, 10)
    # ax.set_ylim((0, 1500))

    # plt.yscale("log") 
    for key in thread_dict.keys():
        x_value = thread_dict[key].thpt / 1000.0
        y_value = thread_dict[key].latency
        x.append(x_value)
        y.append(y_value)
    plt.scatter(x, y)
    # Generating 32 lines
    # for i in range(1, num_lines + 1):
    #     x = np.linspace(0, 10, 100)  # 100 linearly spaced numbers
    #     y = i * x  # y = i * x, where i is the slope of each line
    #     plt.plot(x, y, label=f'Line with slope {i}')

    # Add title and labels
    # plt.title('32 Lines with Different Slopes')
    ax.set_xlabel('Throughput(kIOPS)', fontsize=16)
    ax.set_ylabel('P99.9 Latency (us)', fontsize=16)
    ax.tick_params(axis='x', labelsize=14)
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, linestyle='--', color='grey', alpha=0.7)
    for spine in ax.spines.values():
        spine.set_linewidth(2)
    # Add a legend
#    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    # plt.tick_params(axis='y', direction='in', labelleft=True, labelright=False)

    # Show the plot
    plt.tight_layout()
    # yticks = [1e-2, 1, 1e2, 1e4, 1e6, 1e8]
    # plt.yticks(yticks, ["0.01", "1", "10^2", "10^4", "10^6", "10^8"])
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.1)
    plt.gca().yaxis.set_major_formatter(FuncFormatter(scientific_format))
    plt.savefig(name)
    # plt.show()

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
        DIR2 = "outputs/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core)
        os.makedirs(DIR2, exist_ok=True)
        # print(DIR)
        # thread_dict = get_e2e_log(DIR)
        # netfilter_client, netfilter_server = netfilter_output(DIR)
        # for i in range(n * core):
        #     flow_log = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
        #     with open(flow_log, "r") as file:
        #         lines = file.readlines()
        #         for line in lines:
        #             params = line.split()
        #             port = int(params[1])
        #             latency = float(params[4])
        #             thpt = float(params[5])
        #             t = thread_dict[port]
        #             t.thpt = thpt
        #             t.latency = latency
        #             thread_dict[port] = t
        # f = open("{}/runtime_diff_{}".format(DIR2, run + 1), 'w+')
        # be_file = '{}/per_thread_behavior_{}'.format(DIR2, run + 1)
        # with open(be_file, 'w') as file:
        #     for key in thread_dict:
        #         t = thread_dict[key]
        #         print("{} {} {}\n".format(t.latency, t.thpt, netfilter_client[t.client_pid] + netfilter_server[t.server_pid]))
        #         file.write("{} {} {}\n".format(t.latency, t.thpt, netfilter_client[t.client_pid] + netfilter_server[t.server_pid]))
        # # get virtual runtime results
        results = readFile(DIR + "/server_perf.log")
        total_dict = checkDistribution2(results, n / 2, DIR2 + "/runtime_diff_{}".format(run + 1))
        draw_lins(total_dict, DIR2 + "/perf_runtime_{}.png".format(run + 1))
        # get per-thread behavior
        # thread_dict = get_e2e_log(DIR)
        # for i in range(n * core):
        #     flow_log = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
        #     with open(flow_log, "r") as file:
        #         lines = file.readlines()
        #         for line in lines:
        #             params = line.split()
        #             port = int(params[1])
        #             latency = float(params[4])
        #             thpt = float(params[5])
        #             t = thread_dict[port]
        #             t.thpt = thpt
        #             t.latency = latency
        #             thread_dict[port] = t
        # draw_scatter(thread_dict, DIR2 + "/perthread_{}.png".format(run + 1))
main()

