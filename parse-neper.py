#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
# Parse args
if len(sys.argv) < 3:
    print("usage: parse-netperf.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])

# Parse netperf files
results = {}
total_thpt = 0
f = os.path.join(DIR, "client.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        params = line.split("=")
        results[params[0]] = params[1][:-1]    

# Print the netperf latencies
categories = ['m_lat', 'p99_lat', 'p999_lat']
print("{}\t{}\t{}".format('m_lat',  'p999_lat', "thpt"))

print("{}\t{}\t{}".format(results["latency_mean"], results["latency_p99.9"], float(results["throughput"])))
