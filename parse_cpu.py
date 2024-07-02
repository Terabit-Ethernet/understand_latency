import os
import subprocess
from itertools import product

# Define parameters
hd="testing"
our_patch=1
c_state=1
num_apps = [2]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [128]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]
breakdown = False

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

def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    total_client = 0
    total_server = 0
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        cpu_file = "{}/{}".format(DIR, "cpu-server-{}.log".format(n * core))
        app_cpu = read_cpu_files(cpu_file)
        cpu_file = "{}/{}".format(DIR, "cpu-{}.log".format(n * core))
        client_app_cpu = read_cpu_files(cpu_file)
        total_client += client_app_cpu
        total_server += app_cpu
        if run == len(runs) - 1:
            print(i, total_client / len(runs), total_server / len(runs))

main()