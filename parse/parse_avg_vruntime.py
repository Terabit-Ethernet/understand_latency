import os
import re
import subprocess
import numpy as np
from itertools import product


# Define parameters
hd=1000
our_patch=0
c_state=1
num_apps = [64]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [11, 12, 13, 14, 15]
breakdown = False




def read_file():
    # Initialize a dictionary to hold sums and counts for each line
    line_sums = {}
    line_counts = {}
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    result = []
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        file = "{}/runtime_diff".format(DIR)
        arr = []
        with open(file, 'r') as f:
            # Iterate over each line in the file
            for i, line in enumerate(f):
                # Split the line into columns
                columns = line.split()
                result.append(list(map(float, columns)))
                # Check if there are at least two columns
                # if len(columns) >= 2:
                #     # Convert the second column to a float and add it to the sum for the line
                #     value = float(columns[1])
                #     arr.append(value)
            # arr = sorted(arr)
            # normalzied_arr = [x / min(arr) for x in arr]
            # result.append(normalzied_arr)
            # print (arr)
            # i = 0
            # for value in arr:
            #     line_sums[i] = line_sums.get(i, 0) + value
            #      # Increment the count for the line
            #     line_counts[i] = line_counts.get(i, 0) + 1
            #     i += 1
            # arr = []
    # print(result)
    result = np.array(result)
    std_value = np.std(result, axis=0)
    mean_value = np.mean(result, axis=0)
    # print(mean_value)
    # Compute the average for each line and store it in a list
    # averages = [line_sums[i] / line_counts[i] for i in sorted(line_sums.keys())]
    # index = 0
    for i in range(len(mean_value)):
        print (i * (100 / len(mean_value)), mean_value[i], std_value[i])
read_file()