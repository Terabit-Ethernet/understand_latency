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
f = os.path.join(DIR, "latencies-{}-server.log".format(N))
lines = []
with open(f, "r") as file:
    lines = file.readlines()

# Patterm
pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*")

# Create a dict for samples
samples = {}

# Parse each line
for line in lines:
    m = pattern.match(line)
    if m is not None:
        timestamps = list(map(int, m.groups()))
        if len(timestamps) == 23:
            port = timestamps[0]
            rx_hw = timestamps[2]
            rx_alloc = timestamps[3]
            rx_irq = timestamps[4]
            rx_napi = timestamps[5]
            rx_gro = timestamps[6]
            rx_ip = timestamps[7]
            rx_tcp = timestamps[8]
            rx_read = timestamps[9]
            rx_sleep = timestamps[10]
            rx_ready = timestamps[11]
            rx_wake_up = timestamps[12]
            rx_data_copy = timestamps[13]
            rx_return = timestamps[14]
            tx_alloc = timestamps[15]
            tx_write = timestamps[16]
            tx_data_copy = timestamps[17]
            tx_tcp = timestamps[18]
            tx_ip = timestamps[19]
            tx_queue = timestamps[20]
            tx_xmit = timestamps[21]
            tx_finish = timestamps[22]

            if port not in samples:
                samples[port] = []

            samples[port].append({
                'rx_hw': rx_hw,
                'rx_alloc': rx_alloc,
                'rx_irq': rx_irq,
                'rx_napi': rx_napi,
                'rx_gro': rx_gro,
                'rx_ip': rx_ip,
                'rx_tcp': rx_tcp,
                'rx_read': rx_read,
                'rx_sleep': rx_sleep,
                'rx_ready': rx_ready,
                'rx_wake_up': rx_wake_up,
                'rx_data_copy': rx_data_copy,
                'rx_return': rx_return,
                'tx_alloc': tx_alloc,
                'tx_write': tx_write,
                'tx_data_copy': tx_data_copy,
                'tx_tcp': tx_tcp,
                'tx_ip': tx_ip,
                'tx_queue': tx_queue,
                'tx_xmit': tx_xmit,
                'tx_finish': tx_finish
            })
            # if rx_ip - rx_gro > 40000:
            #     sys.stderr.write(line + "\n")

# Calculate latencies
latencies = {}
for port, ss in samples.items():
    latencies[port] = []
    for ts in ss:
        if ts['rx_ready'] > ts['rx_wake_up']:
            ts['rx_wake_up'] = ts['rx_ready']

        latencies[port].append({
            #'rx_irq': ts['rx_napi'] - ts['rx_irq'],
            #'rx_napi': ts['rx_gro'] - ts['rx_napi'],
            'rx_irq': ts['rx_alloc'] - ts['rx_hw'],
            'rx_napi': ts['rx_gro'] - ts['rx_alloc'],
#            'rx_gro': ts['rx_ip'] - ts['rx_gro'],
            'rx_ip': ts['rx_tcp'] - ts['rx_gro'],
            'rx_tcp': ts['rx_ready'] - ts['rx_tcp'],
            'rx_sched': ts['rx_wake_up'] - ts['rx_ready'],
            'rx_data_copy': ts['rx_return'] - ts['rx_data_copy'],
            'app': ts['tx_write'] - ts['rx_return'],
            'tx_data_copy': ts['tx_tcp'] - ts['tx_data_copy'],
            'tx_tcp': ts['tx_ip'] - ts['tx_tcp'],
            'tx_ip': ts['tx_queue'] - ts['tx_ip'],
            'tx_queue': ts['tx_xmit'] - ts['tx_queue'],
            'tx_xmit': ts['tx_finish'] - ts['tx_xmit'],
            #'full': ts['tx_finish'] - ts['rx_irq'],
            'full': ts['tx_finish'] - ts['rx_hw'],
        })
for port in latencies.keys():
   latencies[port].sort(key = lambda x: x['full'])
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
        tail[port][k] = sorted(v)[round(0.99 * len(v)) - 1]
for port, ts in tails.items():
    tail999[port] = {}
    for k, v in ts.items():
        tail999[port][k] = sorted(v)[round(0.999 * len(v)) - 1]

# Print latency breakdown
categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit', 'full']
print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(avg[port][c]) for c in categories)))

print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(tail[port][c]) for c in categories)))

print("port\t{}".format("\t".join(categories)))
for port in avg:
    print("{}\t{}".format(port, "\t".join("{}".format(tail999[port][c]) for c in categories)))

