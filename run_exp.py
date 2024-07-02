import os
import subprocess
from itertools import product

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
timeout = {}
pkt_t = {}
runs = {}
"""

def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, timeout, pkt_t, run):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(DIR)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, timeout, pkt_t, run))

def main():
    # Generate all combinations
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs, timeout, pkt_threshold)
    for n, f, i, d, p, perm, h, s, core, run, t, pkt_t in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, t, pkt_t, run)
        os.makedirs(DIR, exist_ok=True)
        wrtie_to_config(DIR, hd, our_patch, c_state, n * core, f, i, d, p, perm, h, s, core, t, pkt_t, run)
        command = f"./linux-both-8c-compute.sh {n * core} {DIR} {f} {i} {d} {p} {perm} {h} {s} {core} {run} {t} {pkt_t}"
        print(command)
        subprocess.run(command, shell=True)
        # get latency breakdown 
        # command = f"./parse-breakdown-server.py {DIR} {n} > {DIR}/linux_latency_breakdown_s"
        # subprocess.run(command, shell=True)
        # command = f"./parse-breakdown.py {DIR} {n} > {DIR}/linux_latency_breakdown_c"
        # subprocess.run(command, shell=True)
        # Create directories and copy files

main()
