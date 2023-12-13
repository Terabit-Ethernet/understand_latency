import os
import subprocess
from itertools import product

# Define parameters
hd=1
our_patch=0
c_state=1
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 84, 88]
# num_apps =[84, 88]
# num_apps = [8]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [100]
cores = [1]
runs = [0, 1, 2, 3, 4]
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

def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(DIR)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run))

def main():
    # Generate all combinations
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        os.makedirs(DIR, exist_ok=True)
        wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        command = f"./linux-both-8c-compute.sh {n} {DIR} {f} {i} {d} {p} {perm} {h} {s} {core} {run}"
        print(command)
        subprocess.run(command, shell=True)
        # get latency breakdown 
        # command = f"./parse-breakdown-server.py {DIR} {n} > {DIR}/linux_latency_breakdown_s"
        # subprocess.run(command, shell=True)
        # command = f"./parse-breakdown.py {DIR} {n} > {DIR}/linux_latency_breakdown_c"
        # subprocess.run(command, shell=True)
        # Create directories and copy files

main()
