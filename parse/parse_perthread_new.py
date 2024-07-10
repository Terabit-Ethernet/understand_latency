import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.ticker import ScalarFormatter
# Define parameters
hd="1"
our_patch="1"
c_state=1
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56]
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
runs = [0, 1, 2, 3, 4]
breakdown = False


# sys = "linux"
runtime_pattern = r'sched_stat_runtime.*comm=(netdriver_test_|pingpong_server) pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]'

cmap = plt.get_cmap('tab20c')  # tab20 has 20 colors, use tab20b or tab20c for different shades, or a combination
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
    rx_sched_server = 0
    vruntime = 0

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

def get_samples(f, is_client):
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

    return latencies
    
# Function to format the tick labels
def scientific_format(tick_val, pos):
    return "{:.0e}".format(tick_val)

def extract_numbers(log_entry):
    # Finding the part of the log entry after the ']'
    numbers_part = log_entry.split(']')[1] if ']' in log_entry else ''
    
    # Using regex to find all numbers in that part
    numbers = [float(num) for num in re.findall(r'\d+', numbers_part)]
    return numbers

def readFile(file):
    results = []
    f = open(file)
    firstline = True
    lines = f.readlines()
    for line in lines:
        if firstline and "start module" not in line:
            continue
        if "perf" in line:
            continue
        firstline = False
        if "start module" in line:
            continue
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
    thread_id_regex = re.compile(r'thread IDs: (.+)')
    k = 0
    skip_line = 0
    while k + 1 < len(results):
        thread_ids = []
        threadIDline = results[k]
        match = thread_id_regex.search(threadIDline)
        if match == None:
            k += 1
            continue
        thread_ids.extend(map(int, match.group(1).split()))
        line = results[k + 1]
        params = extract_numbers(line)
        min_vruntime = -1
        if int(flows) > len(params):
            k += 2
            continue
        for i in range(len(params) - int(flows), len(params)):
            if min_vruntime == -1:
                min_vruntime = params[i]
            elif min_vruntime > params[i]:
                min_vruntime = params[i]
        for i in range(len(params) - int(flows), len(params)):
            if thread_ids[i] not in total_dict:
                total_dict[thread_ids[i]] = []
            total_dict[thread_ids[i]].append(params[i] - min_vruntime)
        k += 2
    k = 0
    while k < skip_line:
        for t in total_dict:
            total_dict[t].insert(0, 0)
        k += 1
    # print (total)
    i = 0
    # skip the fist time
    total -= 1.0
    return_dict = total_dict
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
    # ax.set_ylim((1, 10000000))

    plt.yscale("log") 
    for index, key in enumerate(sorted(total_dict.keys())):
        y_values = total_dict[key]
        x_values = []
        value = 0
        for i in y_values:
            x_values.append(value)
            value += 1
        # Assign a color from the generated colors
        color = colors[index % len(colors)]
        color_dict[key] = color
        plt.plot(np.array(x_values), np.array(y_values), label=f'{key}')
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
def draw_scatter(x, y, name):
    # x = []
    # y = []
    # # Create a new figure
    fig, ax = plt.subplots(figsize=(10, 6))
    # plt.figure(figsize=(10, 6))
    # # plt.ylim(top=10000000)
    ax.set_xlim(0, 100000)
    ax.set_ylim((0, 4000))

    # # plt.yscale("log") 
    # for key in thread_dict.keys():
    #     x_value = thread_dict[key].thpt / 1000.0
    #     y_value = thread_dict[key].client_core
    #     x.append(x_value)
    #     y.append(y_value)
    plt.scatter(x, y)
    # Generating 32 lines
    # for i in range(1, num_lines + 1):
    #     x = np.linspace(0, 10, 100)  # 100 linearly spaced numbers
    #     y = i * x  # y = i * x, where i is the slope of each line
    #     plt.plot(x, y, label=f'Line with slope {i}')

    # Add title and labels
    # plt.title('32 Lines with Different Slopes')
    ax.set_xlabel('vruntime diff(ns)', fontsize=16)
    ax.set_ylabel('P99.9 RX_SCHED (us)', fontsize=16)
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
    yticks = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000]
    plt.yticks(yticks)
    ax.yaxis.set_major_formatter(ScalarFormatter())
    ax.ticklabel_format(style='plain')
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.1)
    # plt.gca().yaxis.set_major_formatter(FuncFormatter(scientific_format))
    # plt.show()
    plt.savefig(name)

def combine(thread_dict, server_total_dict, client_total_dict):
    total_dict = {}
    for key, t in thread_dict.items():
        if t.client_core != 0:
            continue
        total_dict[t.client_port] = []
        for i in range(0, min(len(server_total_dict[t.server_pid]), len(client_total_dict[t.client_pid]))):
            total_dict[t.client_port].append(server_total_dict[t.server_pid][i] + client_total_dict[t.client_pid][i])
    return total_dict

def get_relative_dict(d):
    # Convert dictionary values to a 2D NumPy array
    data = np.array(list(d.values()))

    # Calculate the minimum of each column
    col_min = np.min(data, axis=0)

    # Subtract the minimum from each column of each array
    minimized_data = data - col_min

    # Update the dictionary with minimized data
    for key, value in zip(d.keys(), minimized_data):
        d[key] = value.tolist()
    return d
def main():
    # Generate all combinations
    mean_total = 0
    l999_total = 0
    thpt_total = 0
    irq_client_total = 0
    irq_server_total = 0
    rx_sched_client_total = 0
    rx_sched_server_total = 0
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs, timeout, pkt_threshold)

    for n, f, i, d, p, perm, h, s, core, run, t, pkt_t in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, t, pkt_t, run)
        DIR2 = "outputs/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, t, pkt_t, core)
        print(DIR)
        os.makedirs(DIR2, exist_ok=True)
        f_server = os.path.join(DIR, "latencies-{}-server.log".format(n * core))
        server_samples = get_samples(f_server, False)

        p99_9_latencies = {}

        for port, data in server_samples.items():
            rx_sched_times = [entry['rx_sched'] for entry in data]
            p99_9 = np.percentile(rx_sched_times, 99.9)
            p99_9_latencies[port] = p99_9
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
        results = readFile(DIR + "/iter_thread_server.log")
        # idresults = readthreadIdFile(DIR + "/iter_thread_server.log")
        server_total_dict = checkDistribution2(results, n / 2, DIR2 + "/runtime_diff_{}".format(run + 1))
        draw_lins(server_total_dict, DIR2 + "/server_runtime_{}.png".format(run + 1))
        results = readFile(DIR + "/iter_thread_client.log")
        client_total_dict = checkDistribution2(results, n / 2, DIR2 + "/client_runtime_diff_{}".format(run + 1))
        draw_lins(client_total_dict, DIR2 + "/client_runtime_{}.png".format(run + 1))
        # get per-thread behavior
        thread_dict = get_e2e_log(DIR)
        # e2e_total_dict = combine(thread_dict, server_total_dict, client_total_dict)
        # draw_lins(e2e_total_dict, DIR2 + "/total_runtime_{}.png".format(run + 1))

        for i in range(n * core):
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
                    t.rx_sched_server = p99_9_latencies[t.client_port]
                    if t.server_pid in server_total_dict:
                        t.vruntime = np.mean(server_total_dict[t.server_pid])
                    thread_dict[port] = t
        both_side_dict = {}
        for key in thread_dict:
            client_pid = thread_dict[key].client_pid
            server_pid = thread_dict[key].server_pid
            if thread_dict[key].client_core != 0 or  thread_dict[key].server_core != 0:
                continue
            both_side_dict[client_pid] = [x + y for x, y in zip(server_total_dict[thread_dict[key].server_pid], 
                client_total_dict[thread_dict[key].client_pid])]
        
        both_side_dict = get_relative_dict(both_side_dict)
        print(both_side_dict)
        draw_lins(both_side_dict, DIR2 + "/bothside_runtime_{}.png".format(run + 1))
        # x = []
        # y = []
        # for key in thread_dict.keys():
        #     x_value = thread_dict[key].thpt / 1000.0
        #     y_value = thread_dict[key].latency
        #     x.append(x_value)
        #     y.append(y_value)
        # draw_scatter(x, y, DIR2 + "/perthread_{}.png".format(run + 1))
        # x = []
        # y = []
        # for key in thread_dict.keys():
        #     x_value = thread_dict[key].thpt / 1000.0
        #     y_value = thread_dict[key].latency
        #     if thread_dict[key].client_core == 0:
        #         x.append(x_value)
        #         y.append(y_value)
        # draw_scatter(x, y, DIR2 + "/perthread_{}_0.png".format(run + 1))
        # x = []
        # y = []
        # for key in thread_dict.keys():
        #     x_value = thread_dict[key].thpt / 1000.0
        #     y_value = thread_dict[key].latency
        #     if thread_dict[key].client_core == 32:
        #         x.append(x_value)
        #         y.append(y_value)
        # draw_scatter(x, y, DIR2 + "/perthread_{}_32.png".format(run + 1))


        x = []
        y = []
        for key in thread_dict.keys():
            x_value = thread_dict[key].vruntime
            y_value = thread_dict[key].rx_sched_server / 1000.0
            if thread_dict[key].server_core == 0:
                x.append(x_value)
                y.append(y_value)
                print(thread_dict[key].server_core, y_value)
        draw_scatter(x, y, DIR2 + "/perthread_{}_0_runtime_rx_sched.png".format(run + 1))
main()

