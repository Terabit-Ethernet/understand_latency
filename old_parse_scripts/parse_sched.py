#!/usr/bin/env python3
import os
import re
import sys
import numpy as np


client_dict = {}
server_dict = {}

f = os.path.join(DIR, "client_sched_latency.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "sched:sched_switch:" not in line:
            continue
        params = line.split()
        thread_id = params[1]
        if thread_id not in client_dict:
            client_dict[thread_id] = 1
        else
            client_dict[thread_id] += 1


f = os.path.join(DIR, "server_sched_latency.log")
with open(f, "r") as file:
    lines = file.readlines()
    for line in lines:
        if "sched:sched_switch:" not in line:
            continue
        params = line.split()
        thread_id = params[1]
        if thread_id not in server_dict:
            server_dict[thread_id] = 1
        else
            server_dict[thread_id] += 1