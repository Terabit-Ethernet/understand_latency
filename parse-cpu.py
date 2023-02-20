#!/usr/bin/env python3
import os
import re
import sys

# Parse args
if len(sys.argv) < 3:
    print("usage: parse-netperf.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])
irq_cores = int(sys.argv[3])

def process_util_output(lines, irq_cores):
    cpu_util = {}
    num_samples = {}
    tx_util = 0
    rx_util = 0
    application_util = 0.0
    # Get the utilisation for each core
    for line in lines[::-1]:
        elements = line.split()
        if len(elements) == 9 and elements[2] != "CPU":
            if(elements[2] == "all"):
                continue
            cpu = int(elements[2])
            app_util = float(elements[3])
            sys_util = float(elements[5])
            util = float(elements[8])
            if cpu not in cpu_util:
                cpu_util[cpu] = (100 - util)
                num_samples[cpu] = 1
            else:
                cpu_util[cpu] += (100 - util)
                num_samples[cpu] += 1
            if cpu / 4 < 16 - irq_cores:
                tx_util += sys_util
            else:
                rx_util += sys_util
            application_util += app_util
    # Average the utilisation
    for cpu in cpu_util:
        if num_samples[cpu] != 0:
            cpu_util[cpu] /= num_samples[cpu]
    # Add total CPU usage
    total_usage = 0
    for cpu in cpu_util:
        total_usage += cpu_util[cpu]
    return total_usage, application_util / (16 - irq_cores), tx_util / (16 - irq_cores), rx_util / irq_cores

# Parse netperf files
params = []
f = os.path.join(DIR, "cpu-{}.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()
    print("client: ", process_util_output(lines, irq_cores))

f = os.path.join(DIR, "cpu-server-{}.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()
    print("server: ", process_util_output(lines, irq_cores))
