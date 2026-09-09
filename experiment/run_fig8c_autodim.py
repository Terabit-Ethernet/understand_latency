import os
import subprocess
from itertools import product

# Experiment Parameters:
experiment_name = "single_core_macro_autodim"
script_name = "single_core_macro_pcsched.sh"
num_apps = [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
flowsize = [64]
iodepth = [1]
dim = [2]
pin = [1]
permute = [1]
cores = [1]
runs = [0, 1, 2]

# Configuration Parameters for Record:
config_data = """[settings]
experiment_name= {}
num_apps = {}
flowsize = {}
iodepth = {}
dim = {}
pin = {}
permute = {}
cores = {}
"""

def wrtie_to_config(exp_outdir, experiment_name, n, f, i, d, p, perm, core):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(exp_outdir)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(experiment_name, n, f, i, d, p, perm, core))

def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, cores, runs)
    for n, f, i, d, p, perm, core, run in combinations:
        exp_outdir = "/data/projects/latency/{}/{}_{}_{}_{}_{}_{}_{}_{}".format(experiment_name, n, f, i, d, p, perm, core, run)
        os.makedirs(exp_outdir, exist_ok=True)
        wrtie_to_config(exp_outdir, experiment_name, n * core, f, i, d, p, perm, core)
        command = f"../scripts/{script_name} {n} {exp_outdir} {f} {i} {d} {p} {perm}"
        print(command)
        subprocess.run(command, shell=True)

main()
