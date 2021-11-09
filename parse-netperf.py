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

# Parse netperf files
params = []
for i in range(1, N + 1):
    f = os.path.join(DIR, "netperf-{}-{}.log".format(i, N))
    lines = []
    with open(f, "r") as file:
        lines = file.readlines()
    params.append(list(map(float, lines[2].split(","))))

# Print the netperf latencies
categories = ['thru(M)', 'm_lat', 'p99_lat', 'p999_lat']
print("idx\t{}".format("\t".join(categories)))
for i, p in enumerate(params):
    print("{}\t{}\t{}\t{}\t{}".format(i + 1, p[0], p[1], p[2], p[3]))
