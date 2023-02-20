#!/usr/bin/env python3
import os
import re
import sys

def readFile(file):
    results = []
    f = open(file)
    lines = f.readlines()
    for line in lines:
        if "pingpong_server" in line:
            results.append(line)
    return results

def dumpFile(time, core2pids):
    string1 = str(time)
    for i in sorted(core2pids.keys()):
        string1 += ", " + str(core2pids[i])

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
    for line in results:
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

def checkDistribution2(results):

    vruntime_dict = {}
    wakingtime_dict = {}
    switch_dict = {}
    print_time = 0
    total_dict = {}
    total = 0
    for line in results:
        params = line.split()
        time = float(params[3][:-1])
        if "sched:sched_waking:" == params[4]:
            pid = int(params[6].split("=")[1])
            if  (pid < 5000):
                continue
            wakingtime_dict[pid] = time 
        if "sched:sched_stat_runtime:" == params[4]:
            pid = int(params[6].split("=")[1])
            if (pid < 5000) or "comm=pingpong_server" not in line:
                continue
            vruntime_dict[pid] = float(params[9].split("=")[1])
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
                for key in vruntime_dict:
                    if mini == -1:
                        mini = vruntime_dict[key]
                    elif mini  > vruntime_dict[key]:
                        mini = vruntime_dict[key]
                # print time
                for key in vruntime_dict:
                    if key not in total_dict:
                        total_dict[key] = 0
                    total_dict[key] += vruntime_dict[key] - mini
                    # print key, vruntime_dict[key] - mini
                total += 1.0
                print_time = time
                # break
    print total
    for key in total_dict:
        print key, total_dict[key] / total

                # for key in vruntime_dict:
                #     if vruntime_dict[key] > 2e10:
                #         print key, vruntime_dict[key]
            #     del wakingtime_dict[pid]

results = readFile("sched_history")
checkDistribution2(results)
