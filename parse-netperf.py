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
results = []
total_thpt = 0
for i in range(0, N ):
    f = os.path.join(DIR, "netperf-{}.log".format(i))
    lines = []
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            params = line.split()
            time = float(params[2])
            results.append(time)
    f = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            params = line.split()
            thpt = float(params[0])
            total_thpt += thpt

results.sort()
# Print the netperf latencies
categories = ['m_lat', 'p99_lat', 'p999_lat']
print("{}\t{}\t{}".format('m_lat','p99_lat',  'p999_lat', "thpt"))

print("{}\t{}\t{}".format(sum(results) / len(results), np.percentile(results, 99),  np.percentile(results, 99.9)), total_thpt)
