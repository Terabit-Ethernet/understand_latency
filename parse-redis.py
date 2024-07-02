#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
# Parse args
# if len(sys.argv) < 3:
#     print("usage: parse-netperf.py DIR NUM_APPS")
#     exit(1)

# DIR = sys.argv[1]
N = int(sys.argv[1])
# n = int(sys.argv[2])
iodepth = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

def get_data(dir_template, num_files):
    # Parse netperf files
    results = []
    total_thpt = 0
    for i in range(0, len(iodepth)):
        temp_results = []
        tail_latency = 0
        throughput = 0
        for j in range(0, num_files):
  #      print(iodepth[i])
            f = os.path.join(dir_template.format(iodepth[i]), "client_{}.log".format(j + 1))
            lines = []

            with open(f, "r") as file:
                lines = file.readlines()
                for line in lines:
                    if "Throughput:" in line:
                        throughput += float(line.split()[1])
                    elif "Tail latency" in line:
                        if float(line.split()[2]) > tail_latency:
                            tail_latency = float(line.split()[2])
        results.append([tail_latency, throughput])
        
 #   results.sort()
    return results

def print_results(results):
    for params in results:
        print (params[0], params[1])
    
def main():
    dir_template = "temp/our_mc_redis_32_{}_2_1/"
    results = get_data(dir_template, 2)
    print_results(results)
    dir_template = "temp/linux_mc_redis_32_{}_1/"
    results = get_data(dir_template, 2)
    print_results(results)
    # dir_template = "temp/tas_mc_redis_{}_1_2_1/"
    # results = get_data(dir_template, 2)
    # print_results(results)

main()
# Print the netperf latencies
# categories = ['m_lat', 'p99_lat', 'p999_lat']
# print("{}\t{}\t{}".format('m_lat','p99_lat',  'p999_lat', "thpt"))

# print("{}\t{}\t{}".format(sum(results) / len(results), np.percentile(results, 99),  np.percentile(results, 99.9)), total_thpt)
