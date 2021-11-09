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


def process_util_output(lines):
    cpu_util = {}
    num_samples = {}
    # Get the utilisation for each core
    for line in lines[::-1]:
        elements = line.split()
        if len(elements) == 9 and elements[2] != "CPU":
            if(elements[2] == "all"):
                continue
            cpu = int(elements[2])
            util = float(elements[8])
            if cpu not in cpu_util:
                cpu_util[cpu] = (100 - util)
                num_samples[cpu] = 1
            else:
                cpu_util[cpu] += (100 - util)
                num_samples[cpu] += 1

    # Average the utilisation
    for cpu in cpu_util:
        if num_samples[cpu] != 0:
            cpu_util[cpu] /= num_samples[cpu]
    # Add total CPU usage
    total_usage = 0
    for cpu in cpu_util:
        total_usage += cpu_util[cpu]
    return total_usage

# Parse netperf files
params = []
f = os.path.join(DIR, "cpu-{}.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()
    print("client: ", process_util_output(lines))

f = os.path.join(DIR, "cpu-server-{}.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()
    print("server: ", process_util_output(lines))
