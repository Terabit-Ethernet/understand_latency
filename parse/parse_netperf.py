#!/usr/bin/env python3
import os
import sys

# Parse args
if len(sys.argv) < 3:
    print("usage: parse-netperf.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])

total_thpt = 0

class thread_data:
    client_core = 0
    client_pid = 0
    client_port = 0
    server_core = 0
    server_pid = 0
    thpt = 0
    latency = 0

thread_dict = {}
f = os.path.join(DIR, "client.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "cpu" not in line:
            continue
        t = thread_data()
        params = line.split()
        t.client_core = int(params[2])
        t.client_pid = int(params[4])
        t.client_port = int(params[7])
        thread_dict[t.client_port] = t

f = os.path.join(DIR, "server.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "core" not in line:
            continue
        params = line.split()
        t = thread_dict[int(params[7])]
        t.server_core = int(params[2])
        t.server_pid = int(params[4])
        thread_dict[t.client_port] = t

for i in range(0, N):
    f = os.path.join(DIR, "netperf-{}_thpt.log".format(i))
    with open(f, "r") as file:
        lines = file.readlines()
        for line in lines:
            params = line.split()
            port = int(params[1])
            thpt = float(params[5])
            latency = float(params[4])
            total_thpt += thpt
            t = thread_dict[port]
            t.thpt = thpt
            t.latency = latency
            thread_dict[port] = t

print("{}\t".format(total_thpt))
