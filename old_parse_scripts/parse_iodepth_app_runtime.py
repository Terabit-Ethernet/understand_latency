import re
import sys
from statistics import mean 
def readFile(file):
    results = []
    f = open(file)
    lines = f.readlines()
    for line in lines:
        if "netdriver" in line or "pingpong_server" in line:
            results.append(line)
    return results

def parse_log(lines):
    # Regular expressions to extract relevant information
    runtime_pattern = re.compile(r'sched:sched_stat_runtime:.*pid=(\d+).*?runtime=(\d+).*?\[ns\].*?vruntime=(\d+).*?\[ns\]')
    switch_pattern = re.compile(r'sched:sched_switch:.*prev_pid=(\d+).*next_pid=(\d+)')
    runtime_arr = 0
    # Initialize variables
    thread_runtimes = 0
    current_thread = -1
    sched_times = 0
    i = 0
    # Parse the log
    for line in lines:
        runtime_match = runtime_pattern.search(line)
        switch_match = switch_pattern.search(line)

        if runtime_match:
            thread_pid = int(runtime_match.group(1))
            runtime = int(runtime_match.group(2))
            if current_thread != -1:
                if current_thread != thread_pid or ("kworker" in line) or ("ksoft" in line):
                    print("err")
            else:
                current_thread = thread_pid
            thread_runtimes += runtime
        elif switch_match:
            next_pid = int(switch_match.group(2))
            if current_thread != -1:
                # Accumulate runtime until the next sched_switch event for the same thread
                runtime_arr += thread_runtimes
                sched_times += 1
                thread_runtimes = 0
                current_thread = -1
    print(runtime_arr / sched_times, sched_times, runtime_arr)
    return
DIR = sys.argv[1]
results = readFile(DIR)
parse_log(results)