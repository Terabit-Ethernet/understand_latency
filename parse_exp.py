import os
import re
import subprocess
import numpy as np
from itertools import product
import matplotlib.pyplot as plt
import seaborn as sns
# Define parameters
hd="test_perf_dim_disable"
our_patch="1"
c_state=1
num_apps = [56]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [0]
pin = [1]
permute = [1]
hrtick = [0]
sched = [100]
cores = [1]
runs = [12, 13, 14]
timeout = [90]
pkt_threshold = [28]
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

categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit']

def get_breakdown_rx_sched(file_path):
        
    # Read the file and extract the required values
    with open(file_path, 'r') as file:
        lines = file.readlines()

        # Extract the second value from the second and sixth rows
        # Assuming the file format is consistent with your example and that rows are 0-indexed
        mean = float(lines[1].split()[1])
        p999 = float(lines[5].split()[1])
    return mean, p999
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

def get_latency_breakdown_e2e(client_sample, server_sample):
    e2e_sample = []
    for p in client_sample:
        client_p = client_sample[p]
        server_p = server_sample[p]
        assert(len(client_p) == len(server_p))
        i = 0
        while i + 1 < len(client_p):
            if i == 0:
                i += 2
                continue
            e2e_lat = client_p[i]['app'] + client_p[i]['tx_data_copy'] + client_p[i]['tx_tcp'] + client_p[i]['tx_ip'] + client_p[i]['tx_queue'] +  client_p[i]['tx_xmit']
            e2e_lat += server_p[i]['full']
            e2e_lat += client_p[i + 1]['rx_irq'] + client_p[i + 1]['rx_napi'] + client_p[i + 1]['rx_ip'] + client_p[i + 1]['rx_tcp'] + client_p[i + 1]['rx_sched'] +  client_p[i + 1]['rx_data_copy']
            client = {
                'rx_irq': client_p[i + 1]['rx_irq'],
                'rx_napi': client_p[i + 1]['rx_napi'],
                #'rx_gro': ts['rx_ip'] - ts['rx_gro'],
                'rx_ip': client_p[i + 1]['rx_ip'],
                'rx_tcp': client_p[i + 1]['rx_tcp'],
                'rx_sched':  client_p[i + 1]['rx_sched'],
                'rx_data_copy': client_p[i + 1]['rx_data_copy'],
                'app': client_p[i]['app'],
                'tx_data_copy': client_p[i]['tx_data_copy'],
                'tx_tcp':  client_p[i]['tx_tcp'],
                'tx_ip': client_p[i]['tx_ip'],
                'tx_queue': client_p[i]['tx_queue'],
                'tx_xmit': client_p[i]['tx_xmit'],
                #'full': ts['tx_finish'] - ts['rx_irq'],
                # 'full': ts['tx_finish'] - ts['rx_hw'],
            }
            e2e_sample.append({
                'client':client,
                "server": server_p[i],
                'e2e_lat': e2e_lat,
            })
            i = i + 2
    mean_sample = {
        'client': {},
        'server': {},
        'e2e_lat': 0,
    }
    p999_per_attribute = {
        'client': {},
        'server': {},
        'e2e_lat': 0,
    }
    for i in categories:
        mean_sample['client'][i] = 0
        mean_sample['server'][i] = 0
    for sample in e2e_sample:
        for i in categories:
            mean_sample['client'][i] += sample['client'][i]
            mean_sample['server'][i] += sample['server'][i]
        mean_sample['e2e_lat'] += sample['e2e_lat']
    for i in categories:
        mean_sample['client'][i] /= len(e2e_sample)
        mean_sample['server'][i] /= len(e2e_sample)
    for i in categories:
        e2e_sample.sort(key = lambda x: x['client'][i])   
        p999_per_attribute['client'][i] = e2e_sample[round(len(e2e_sample) * 0.999) - 1]['client'][i]
        e2e_sample.sort(key = lambda x: x['server'][i])   
        p999_per_attribute['server'][i] = e2e_sample[round(len(e2e_sample) * 0.999) - 1]['server'][i]     
    
    # print(mean_sample)
    e2e_sample.sort(key = lambda x: x['e2e_lat'])
    total = 0
    i = round(len(e2e_sample) * 0.999) - 1
    while i < len(e2e_sample):
        if e2e_sample[i]['client']['rx_irq'] + e2e_sample[i]['server']['rx_irq'] > 300000:
            total += 1
        i += 1
    return mean_sample, e2e_sample[round(len(e2e_sample) * 0.999) - 1], p999_per_attribute, total, len(e2e_sample) * 0.001, e2e_sample

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
        print (port, len(latencies[port]))
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
            # v.sort()
            tail999[port][k] = (v)[round(0.999 * len(v)) - 1]
    # Print latency breakdown
    # categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit', 'full']
    # print(tail999)
    return avg, tail999

def get_latency_thpt_num(DIR):
    latency_file_name = DIR + "/latency.log"
    thpt_file_name = DIR + "/linux_latency"
    with open(latency_file_name, 'r') as file:
        line = file.readlines()[0]
        mean = float(line.split()[0])
        l_99 = float(line.split()[1])
        l_999 = float(line.split()[2])
    with open(thpt_file_name, 'r') as file:
        thpt = float(file.readlines()[1].split()[0])
    return mean, l_99, l_999, thpt

def extract_idle_usage(lines, cpu_number):
    i = 0
    while i < len(lines):
        if "Average:" not in lines[i]: 
            i += 1
        else:
            break
    header = lines[i].split()
    cpu_index = header.index(f"%idle")
    for line in lines[1 + i:]:
        fields = line.split()
        if fields[1] == str(cpu_number):
            return float(fields[cpu_index])

def read_cpu_files(file_path):
        
    # Read the file and extract the required values
    with open(file_path, 'r') as file:
        lines = file.readlines()
        # Extract the second value from the second and sixth rows
        # Assuming the file format is consistent with your example and that rows are 0-indexed
        app_cpu =(100 * 2 - extract_idle_usage(lines, 0) - extract_idle_usage(lines, 32)) / 2
    return app_cpu

def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(DIR)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run))

def write_breakdown(dir_name, mean_breakdown, p999_breakdown, p999_per_attribute):

    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    # The path to the file where the config will be written
    file_name = '{}/linux_latency_breakdown_mean_999_overall'.format(dir_name)

    # Write the config data to the file
    with open(file_name, 'w') as file:
        for key in categories:
            file.write("{} {} {} {} {}\n".format(key.replace("_","\\\\\_"), mean_breakdown['client'][key] / 1000.0 , p999_breakdown['client'][key] / 1000.0, p999_per_attribute['client'][key] / 1000.0, 1))
        for key in categories:
            file.write("{} {} {} {} {}\n".format(key.replace("_","\\\\\_"), mean_breakdown['server'][key] / 1000.0, p999_breakdown['server'][key] / 1000.0, p999_per_attribute['server'][key] / 1000.0, 2))

    file.close()

def write_breakdown_overall(dir_name, runs, mean_breakdown_c, mean_breakdown_s, p999_breakdown_c, p999_breakdown_s, p999_per_attribute_c, p999_per_attribute_s):

    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    # The path to the file where the config will be written
    file_name = '{}/linux_latency_breakdown_mean_999_overall'.format(dir_name)

    # Write the config data to the file
    with open(file_name, 'w') as file:
        for key in categories:
            file.write("{} {} {} {} {}\n".format(key.replace("_","\\\\\_"), mean_breakdown_c[key] / runs , p999_breakdown_c[key] / runs, p999_per_attribute_c[key] / runs, 1))
        for key in categories:
            file.write("{} {} {} {} {}\n".format(key.replace("_","\\\\\_"), mean_breakdown_s[key] / runs, p999_breakdown_s[key] / runs, p999_per_attribute_s[key] / runs, 2))

    file.close()

def convert_dict_to_arr(dictionary):
    result = []
    for i in categories:
        result.append(dictionary['client'][i])
    for i in categories:
        result.append(dictionary['server'][i])
    return result

def generate_heatmap(dir_name, n, run, e2e_sample):
    data = []
    plt.rcParams['xtick.labelsize'] = 12
    plt.rcParams['ytick.labelsize'] = 12
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    # Generating random data for illustration
    num_samples = int(len(e2e_sample) * 0.002)
    index = len(e2e_sample) - num_samples
    for i in range(0, num_samples):
        data.append(convert_dict_to_arr(e2e_sample[index + i]))
    data = np.array(data) / 1000.0
    data = data.T
    # data = np.concatenate((e2e_sample['client'], e2e_sample['server']), axis=1)
    # Categories for the y-axis
    # Create the heatmap
    plt.figure(figsize=(10, 8))
    ax = sns.heatmap(data, vmin = 0, vmax = 1500, yticklabels=categories + categories, cmap="Reds", cbar_kws={'label': 'Latency range(us)'})
    # Define the tick positions and labels
    tick_positions = np.linspace(0, data.shape[1] - 1, 11, dtype=int)  # Positions from 0 to 999, 10 evenly spaced
    tick_labels = ['99.8', '99.82', '99.84', '99.86', '99.88', '99.9', '99.92', '99.94', '99.96', '99.98', '100.0']  # Labels scaled from 0 to 90

    # Set the ticks on the x-axis
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    # plt.yticks(rotation=30)

    plt.axhline(11.75, color='k', linestyle='--', linewidth=2)
    ax.text(len(data[0]) / 2, 11, 'Client',  ha='center', va='center', fontsize='large', color='black', zorder=5, weight='bold')
    ax.text(len(data[0]) / 2, 23, 'Server', ha='center', va='center', fontsize='large', color='black', zorder=5, weight='bold')
    plt.xlabel("Percentile", fontsize=12)
    # plt.ylabel("Latency Breakdown Categories", fontsize=12)

    # plt.show()
    plt.savefig('{}/heatmap_{}_{}.png'.format(dir_name, n, run), dpi=300)  # Replace 'your_plot.png' with your desired file name and format
    plt.close()

def main():
    # Generate all combinations
    mean_total = []
    l99_total = []
    l999_total = []
    thpt_total = 0
    irq_client_total = 0
    irq_server_total = 0
    rx_sched_client_total = 0
    rx_sched_server_total = 0
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, timeout, pkt_threshold, runs)
    mean_breakdown_c = {}
    mean_breakdown_s = {}
    p999_breakdown_c = {}
    p999_breakdown_s = {}
    p999_per_attribute_c = {}
    p999_per_attribute_s = {}
    mean_rx_sched_c = []
    mean_rx_sched_s = []
    p999_rx_sched_c = []
    p999_rx_sched_s = []
    for key in categories:
        mean_breakdown_c[key] = 0
        mean_breakdown_s[key] = 0
        p999_breakdown_c[key] = 0
        p999_breakdown_s[key] = 0
        p999_per_attribute_c[key] = 0
        p999_per_attribute_s[key] = 0
    total_irq = 0
    total_run = 0
    total_client_cpu = 0
    total_server_cpu = 0
    for n, f, i, d, p, perm, h, s, core, t, pkt_t, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, t, pkt_t, run)
        # print(DIR)
        f_client = os.path.join(DIR, "latencies-{}.log".format(n * core))
        f_server = os.path.join(DIR, "latencies-{}-server.log".format(n * core))
        # mean_client, p999_client = get_latency_breakdown(f_client, True)
        # mean_server, p999_server = get_latency_breakdown(f_server, False)
        if breakdown:
            client_samples = get_samples(f_client, True)
            server_samples = get_samples(f_server, False)
            mean_breakdown, p999_breakdown, p999_per_attribute, irq_per_run, total_per_run, e2e_sample = get_latency_breakdown_e2e(client_samples, server_samples)
        # print(DIR)
            total_irq += irq_per_run
            total_run += total_per_run
            # print(p999_breakdown['client']['rx_sched'], p999_breakdown['server']['rx_sched'])
            dir_name = "breakdown/{}_{}_{}/our_mc_64_{}_1/{}".format(hd, our_patch, c_state, n, run)
            generate_heatmap(dir_name, n, run, e2e_sample)
            write_breakdown(dir_name, mean_breakdown, p999_breakdown, p999_per_attribute)
        mean, l_99, l_999, thpt = get_latency_thpt_num(DIR)
        mean_total.append(mean)
        l99_total.append(l_99)
        l999_total.append(l_999)
        thpt_total += thpt
        cpu_file = "{}/{}".format(DIR, "cpu-server-{}.log".format(n * core))
        app_cpu = read_cpu_files(cpu_file)
        cpu_file = "{}/{}".format(DIR, "cpu-{}.log".format(n * core))
        client_app_cpu = read_cpu_files(cpu_file)
        total_client_cpu += client_app_cpu
        total_server_cpu += app_cpu
        if rx_sched_only:
                mean_rx_sched_c.append(get_breakdown_rx_sched(DIR + "/linux_latency_breakdown_rx_sched_c")[0])
                mean_rx_sched_s.append(get_breakdown_rx_sched(DIR + "/linux_latency_breakdown_rx_sched_s")[0])
                p999_rx_sched_c.append(get_breakdown_rx_sched(DIR + "/linux_latency_breakdown_rx_sched_c")[1])
                p999_rx_sched_s.append(get_breakdown_rx_sched(DIR + "/linux_latency_breakdown_rx_sched_s")[1])
        for key in categories:
            if breakdown:
                mean_breakdown_c[key] += mean_breakdown['client'][key] / 1000.0
                mean_breakdown_s[key] += mean_breakdown['server'][key] / 1000.0
                p999_breakdown_c[key] += p999_breakdown['client'][key] / 1000.0
                p999_breakdown_s[key] += p999_breakdown['server'][key] / 1000.0
                p999_per_attribute_c[key] += p999_per_attribute['client'][key] / 1000.0
                p999_per_attribute_s[key] += p999_per_attribute['server'][key] / 1000.0
        # irq_client_total += client_latency_breakdown[0]['rx_irq'] / 1000.0
        # irq_server_total += server_latency_breakdown[0]['rx_irq'] / 1000.0
        # rx_sched_client_total += client_latency_breakdown[0]['rx_sched'] / 1000.0
        # rx_sched_server_total += server_latency_breakdown[0]['rx_sched'] / 1000.0
        # print(p999_breakdown['client']['rx_sched'] / 1000.0, p999_breakdown['server']['rx_sched'] / 1000.0)
        if run == runs[len(runs) - 1]:
            if not breakdown and not rx_sched_only:
                print(n, np.mean(mean_total), np.mean(l999_total), thpt_total / len(runs), 
                    total_client_cpu / len(runs), total_server_cpu / len(runs), np.min(mean_total), np.max(mean_total), np.min(l99_total), np.max(l99_total), np.min(l999_total), np.max(l999_total), )
            # print(n, irq_client_total / len(runs), irq_server_total / len(runs), 
            #     rx_sched_client_total / len(runs), rx_sched_server_total / len(runs))
            if breakdown:
                for key in categories:
                    print("{} {} {} {} {}".format(key.replace("_","\\\\\_"), mean_breakdown_c[key] / len(runs) , p999_breakdown_c[key] / len(runs), p999_per_attribute_c[key] /len(runs), 1))
                for key in categories:
                    print("{} {} {} {} {}".format(key.replace("_","\\\\\_"), mean_breakdown_s[key] / len(runs), p999_breakdown_s[key] / len(runs), p999_per_attribute_s[key] /len(runs), 2))
                dir_name = "breakdown/{}_{}_{}/our_mc_64_{}_1/".format(hd, our_patch, c_state, n)
                write_breakdown_overall(dir_name, len(runs), mean_breakdown_c, mean_breakdown_c,  p999_breakdown_c, p999_breakdown_s,  p999_per_attribute_c, p999_per_attribute_s)
            mean_total = []
            l99_total = []
            l999_total = []
            thpt_total = 0
            total_client_cpu = 0
            total_server_cpu = 0
            for key in categories:
                mean_breakdown_c[key] = 0
                mean_breakdown_s[key] = 0
                p999_breakdown_c[key] = 0
                p999_breakdown_s[key] = 0
                p999_per_attribute_c[key] = 0
                p999_per_attribute_s[key] = 0
            # if breakdown:
            #     print ("percentage: ", total_irq / total_run)
            total_irq = 0
            total_run = 0
            if rx_sched_only:
                print("{} {} {} {} {}".format(i, sum(mean_rx_sched_c) / len(runs), sum(p999_rx_sched_c) / len(runs), 
                    sum(mean_rx_sched_s) / len(runs), sum(p999_rx_sched_s) / len(runs)))
            mean_rx_sched_c = []
            mean_rx_sched_s = []
            p999_rx_sched_c = []
            p999_rx_sched_s = []    
            # irq_client_total = irq_server_total = rx_sched_client_total = rx_sched_server_total = 0
        # Create directories and copy files

main()



