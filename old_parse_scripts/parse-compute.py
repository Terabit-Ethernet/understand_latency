#!/usr/bin/env python3
import os
import re
import sys

# Parse args
if len(sys.argv) < 3:
    print("usage: parse-compute.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])

# Parse netperf files
params = []
for i in range(0, N):
    f = os.path.join(DIR, "compute_{}-{}.log".format(i, N))
    lines = []
    avg = 0
    with open(f, "r") as file:
        lines = file.readlines()[0:50]
        for line in lines:
           param = line.split()
           if len(param) < 2:
               continue
           try: 
               avg += float(param[0])
           except:
               sys.stderr.write(DIR + "compute_{}-{}.log\n".format(i, N))
        avg = avg / len(lines)
        params.append(avg)
# Print the netperf latencies
categories = ['thru(M)']
print("idx\t{}".format("\t".join(categories)))
for i, p in enumerate(params):
    print("{}\t{}".format(i + 1, p / 1000000.0))
