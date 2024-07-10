 #!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from statistics import stdev
# import matplotlib.pyplot as plt
# from matplotlib.ticker import FuncFormatter
runtime_pattern = r'sched_stat_runtime.*comm=(netdriver_test_|pingpong_server) pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]'

def readFile(file):
    results = []
    f = open(file)
    lines = f.readlines()
    for line in lines:
        if "netdriver" in line or "pingpong_server" in line:
            results.append(line)
    return results

def dumpFile(time, core2pids):
    string1 = str(time)
    for i in sorted(core2pids.keys()):
        string1 += ", " + str(core2pids[i])

# Function to format the tick labels
def scientific_format(tick_val, pos):
    return "{:.0e}".format(tick_val)
def checkDistribution(results):
    string1 = "time"
    core2pids = {}
    pid2core = {}
    i = 0
    ptime = 0
    while i < 32:
        string1 += " " + str(i)
        core2pids[i] = 0
        i += 4
    for line in results[:-1]:
        params = line.split()
        time = float(params[3][:-1])
        core = int(params[2][1:-1])
        pid = int(params[11][9:])
        if core % 4 != 0:
            continue
        if pid not in pid2core:
            pid2core[pid] = core
            core2pids[core] += 1
            dumpFile(time, core2pids)
            ptime = time
        if pid2core[pid] != core:
            core2pids[pid2core[pid]] -= 1
            pid2core[pid] = core
            core2pids[core] += 1
            dumpFile(time, core2pids)
            ptime = time
        else:
            if time - ptime >= 0.1:
                dumpFile(time, core2pids)
                ptime = time

def checkDistribution2(results, flows):

    vruntime_dict = {}
    wakingtime_dict = {}
    switch_dict = {}
    print_time = 0
    total_dict = {}
    total = 0
    pid2cpu = {}
    for line in results:
        params = line.split()
        if "Q:Reg" in line:
            continue
        if len(line.split()) < 4:
            continue
        try:
            time = float(line.split()[3][:-1])
        except:
            print(line)
        runtime_match = re.search(runtime_pattern, line)
        # if "sched:sched_waking:" == params[4]:
        #     pid = int(params[6].split("=")[1])
        #     if  (pid < 5000):
        #         continue
        #     wakingtime_dict[pid] = time 
        core = int(line.split()[2].strip('[]'))
        current_pid = int(line.split()[1])
        pid2cpu[current_pid] = core
        if runtime_match and core == 0:
            pid = int(runtime_match.group(2))
            runtime = int(runtime_match.group(3))
            vruntime =  float(runtime_match.group(4))
            vruntime_dict[pid] = vruntime
            # if pid in wakingtime_dict and time - wakingtime_dict[pid] > 0.001:
            #     # print time, "pid,", pid, time - wakingtime_dict[pid]
            #     mini = -1
            #     for key in vruntime_dict:
            #         if mini == -1:
            #             mini = vruntime_dict[key]
            #         elif mini  > vruntime_dict[key]:
            #             mini = vruntime_dict[key]
            #     for key in vruntime_dict:
            #         # if vruntime_dict[key] - mini > 10000000:
            #         #     continue
            #         # print key, vruntime_dict[key] - mini
            #         if key not in total_dict:
            #             total_dict[key] = 0
            #         total_dict[key] += vruntime_dict[key] - mini
            #         total += 1.0
            if time - print_time > 1:
                mini = -1
                if len(vruntime_dict) != flows:
                    # print(vruntime_dict)
                    print_time = time
                   # vruntime_dict = {}
                    continue
                # if total < 3:
                #     total += 1.0
                #     print_time = time
                #     continue
                for key in vruntime_dict:
                    if mini == -1:
                        mini = vruntime_dict[key]
                    elif mini  > vruntime_dict[key]:
                        mini = vruntime_dict[key]
                # print time
                # vruntime_dict= sorted(vruntime_dict.items(), key=lambda x: x[1])
                # str = ""
                for key in vruntime_dict:
                    # str += " {}".format((element[1] - mini) * 88761 / 1024 / 1000)
                    if key not in total_dict:
                        total_dict[key] = []
                    total_dict[key].append(vruntime_dict[key] - mini)
                    # print(key, (vruntime_dict[key] - mini) * 88761 / 1024 / 1000)
                    # # print key, vruntime_dict[key] - mini
                # print (str)
                total += 1.0
                print_time = time
                # vruntime_dict = {}
                    # break
    # print (total)
    i = 0
    # skip the fist time
    total -= 1.0
    return_dict = total_dict
    # print(return_dict)
    total_dict = sorted(total_dict.items(), key=lambda x: sum(x[1]))
    for element in total_dict:
        if pid2cpu[element[0]] == 0:
            print (i, sum(element[1]) / total * 88761 / 1024 / 1000, stdev(np.array(element[1]) * 88761 / 1024 / 1000), element[0])
            i += 1
                # for key in vruntime_dict:
                #     if vruntime_dict[key] > 2e10:
                #         print key, vruntime_dict[key]
            #     del wakingtime_dict[pid]
    return return_dict
# def draw_lins(total_dict):


#     # Number of lines
#     num_lines = len(total_dict)
#     # Create a new figure
#     plt.figure(figsize=(10, 6))
#     # plt.ylim(top=10000000)
#     plt.ylim((1, 10000000))

#     plt.yscale("log") 
#     for key in total_dict.keys():
#         print(key)
#         y_values = total_dict[key]
#         x_values = []
#         value = 0
#         for i in y_values:
#             x_values.append(value)
#             value += 1
#         plt.plot(np.array(x_values), np.array(y_values), label=f'{key}')
#     # Generating 32 lines
#     # for i in range(1, num_lines + 1):
#     #     x = np.linspace(0, 10, 100)  # 100 linearly spaced numbers
#     #     y = i * x  # y = i * x, where i is the slope of each line
#     #     plt.plot(x, y, label=f'Line with slope {i}')

#     # Add title and labels
#     # plt.title('32 Lines with Different Slopes')
#     plt.xlabel('Time(s)')
#     plt.ylabel('vruntime diff(us)')

#     # Add a legend
#     plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
#     plt.tick_params(axis='y', direction='in', labelleft=True, labelright=False)

#     # Show the plot
#     plt.tight_layout()
#     yticks = [1, 1e2, 1e4, 1e6, 1e8]
#     plt.yticks(yticks)
#     plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.1)
#     plt.gca().yaxis.set_major_formatter(FuncFormatter(scientific_format))

#     plt.show()

DIR = sys.argv[1]
flows= int(sys.argv[2])
flows /= 2
results = readFile(DIR)
total_dict = checkDistribution2(results, flows)
# draw_lins(total_dict)
