#!/bin/bash

N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
# DIM_DISABLED = 0, DIM_ENABLED = 1
DIM=$5
# off = 0, on = 1
PIN=$6
PERMUTE=$7
HRTICK=$8
SCHE=$9
SC=${10}
RUN=${11}
DPORT=5001

echo "$DIR"
# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
sudo sysctl -w net.core.latency_breakdown_nrfs=0
echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting

if [[ $SCHE -eq 0 ]];
then
	echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns
	echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
	ssh jaehyun\@128.84.155.146 -t 'echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns'
	ssh jaehyun\@128.84.155.146 -t 'echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns'
else
	echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_latency_ns
	echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
	ssh jaehyun\@128.84.155.146 -t "echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_latency_ns"
	ssh jaehyun\@128.84.155.146 -t "echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns"
fi

if [[ $HRTICK -eq 1 ]];
then
	echo HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh jaehyun\@128.84.155.146 -t 'echo HRTICK | sudo tee /sys/kernel/debug/sched_features'
else
	echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh jaehyun\@128.84.155.146 -t 'echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features'
fi

if [[ $DIM -eq 1 ]];
then
	echo "enable dim"
	ssh jaehyun\@128.84.155.146 -t 'sudo ethtool -C ens2f0np0 adaptive-rx on adaptive-tx on'
	sudo ethtool -C ens2f0np0 adaptive-rx on adaptive-tx on
else
	ssh jaehyun\@128.84.155.146 -t 'sudo ethtool -C ens2f0np0 adaptive-rx off adaptive-tx off'
	sudo ethtool -C ens2f0np0 adaptive-rx off adaptive-tx off
fi
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=200; fi
#LOG=249
sudo sysctl -w net.core.latency_breakdown_log=$LOG

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=1'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_rx_sched_lat_only=1'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_nrfs=0'
ssh jaehyun\@128.84.155.146 -t 'echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on'
ssh jaehyun\@128.84.155.146 -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"
ssh jaehyun\@128.84.155.146 -t "echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting"

# enable netfilter 
# sudo insmod /home/qizhe/netfilter/filter.ko
# ssh jaehyun\@128.84.155.146 -t "sudo insmod /home/qizhe/netfilter/filter.ko"
# echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
# ssh jaehyun\@128.84.155.146 -t "echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"


#TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
if [[ $SC -eq 1 ]];
then
	TASKSET="0,32"
else
	TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
fi
mkdir -p $DIR



ssh jaehyun\@128.84.155.146 -t "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.11.125 --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --permute $PERMUTE $PERM --sc $SC > /home/jaehyun/server.log" &
sleep 3
echo "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.11.125 --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN  --permute $PERMUTE --sc $SC > /home/qizhe/latency/temp/server.log"
sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.11.125:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC tcpppasync  > temp/client.log &
echo "sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.11.125:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC tcpppasync"
PIDS="$PIDS $!"
echo "pid $PIDS dport $DPORT"

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

# get perf
# sudo ../perf sched record -C 0 -k CLOCK_MONOTONIC -- sleep 30
# sudo ../perf sched script > temp/client_perf.log

wait $PIDS
kill -9 $PIDS2

# get compute log
ssh jaehyun\@128.84.155.146 -t 'sudo killall compute_md'
scp -r jaehyun\@128.84.155.146:/home/qizhe/latency/temp/compute*.log temp/
scp -r jaehyun\@128.84.155.146:/home/jaehyun/server.log temp/
ssh jaehyun\@128.84.155.146 -t 'sudo rm -rf /home/qizhe/latency/temp/compute*.log'

PIDS2="$!"
# client-side
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=0'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_rx_sched_lat_only=0'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_nrfs=0'
ssh jaehyun\@128.84.155.146 -t 'sudo cat /sys/kernel/debug/tracing/trace' > $DIR/latencies-$N-server.log
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo killall pingpong_server'
ssh jaehyun\@128.84.155.146 -t "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"

#remove filter
# sudo rmmod filter.ko
# ssh jaehyun\@128.84.155.146 -t "sudo rmmod filter.ko"
# sudo tail -n 32  /var/log/kern.log > temp/filter_client.log
# ssh jaehyun\@128.84.155.146 -t "sudo tail -n 32  /var/log/kern.log" > temp/filter_server.log


sudo mv temp/*.log $DIR/
./parse-netperf.py $DIR $N > $DIR/linux_latency
if [[ $IODEPTH -eq 1 ]];
then
	./parse-breakdown-server.py $DIR $N > $DIR/linux_latency_breakdown_s
	./parse-breakdown.py $DIR $N >  $DIR/linux_latency_breakdown_c 
else
	./parse-breakdown-rx_sched_c.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_c 
	./parse-breakdown-rx_sched_s.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_s
fi

# PIDS="$PIDS $!"
# ./parse-breakdown-server.py $DIR $N > $DIR/linux_latency_breakdown_s
# ./parse-breakdown.py $DIR $N >  $DIR/linux_latency_breakdown_c 
python3 parse_vruntime.py $DIR/client_perf.log $N > $DIR/runtime_diff
echo "done"  
