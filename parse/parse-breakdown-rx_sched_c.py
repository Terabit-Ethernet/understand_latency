#!/usr/bin/env python3
import os
import re
import sys

# Parse args
if len(sys.argv) < 3:
    print("usage: parse-breakdown.py DIR NUM_APPS")
    exit(1)

DIR = sys.argv[1]
N = int(sys.argv[2])

# Read the latencies file
f = os.path.join(DIR, "latencies-{}.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()

# Patterm
pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+).*")

# Create a dict for samples
samples = {}

# Parse each line
for line in lines:
    m = pattern.match(line)
    if m is not None:
        timestamps = list(map(int, m.groups()))
        if len(timestamps) == 3:
            port = 0
            # port = timestamps[1]
            rx_sched = timestamps[2]
            if port not in samples:
                samples[port] = []

            samples[port].append({
                'rx_sched': rx_sched,
            })
            # if rx_data_copy - rx_ready > 800000:
            #     sys.stderr.write(line + "\n")

# Calculate latencies
latencies = {}
for port, ss in samples.items():
    latencies[port] = []
    for ts in ss:
        latencies[port].append({
            #'rx_irq': ts['rx_napi'] - ts['rx_irq'],
            #'rx_napi': ts['rx_gro'] - ts['rx_napi'],
            'rx_sched': ts['rx_sched']
        })
for port in latencies.keys():
   latencies[port].sort(key = lambda x: x['rx_sched'])
# Average and tail atencies
sum = {}
num = {}
avg = {}
tails = {}
tail = {}
tail999 = {}
for port, ls in latencies.items():
    sum[port] = {}
    num[port] = {}
    for ts in ls:
        for k, v in ts.items():
            if k not in sum[port]:
                sum[port][k] = 0
                num[port][k] = 0
            sum[port][k] += v
            num[port][k] += 1
for port, ts in sum.items():
    avg[port] = {}
    for k, v in ts.items():
        avg[port][k] = round(v / num[port][k], 3)
for port, ls in latencies.items():
    tails[port] = {}
    for ts in ls:
        for k, v in ts.items():
            if k not in tails[port]:
                tails[port][k] = []
            tails[port][k].append(v)
for port, ts in tails.items():
    tail[port] = {}
    for k, v in ts.items():
        # v.sort()
        tail[port][k] = (v)[round(0.99 * len(v)) - 1]
for port, ts in tails.items():
    tail999[port] = {}
    for k, v in ts.items():
       # v.sort()
        tail999[port][k] = (v)[round(0.999 * len(v)) - 1]

# Print latency breakdown
# categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit', 'full']
categories = ['rx_sched']

print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(avg[port][c]) for c in categories)))

print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(tail[port][c]) for c in categories)))

print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(tail999[port][c]) for c in categories)))

