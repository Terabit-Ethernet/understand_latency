# Get the dir of this project
DIR=$(realpath $(dirname $(readlink -f $0)))

# Source the environment file
source $DIR/env.sh

if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
# DIM_DISABLED = 0, DIM_ENABLED = 1
DIM=$5
# off = 0, on = 1
PIN=$6
# NO TAPP = 0, WITH TAPP = 1
TAPP=$7
# SCHED_IDLE = 1, SCHED_NORMAL = 2
TAPPSCHED=$8
DPORT=5001

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
sudo sysctl -w net.core.latency_breakdown_nrfs=0
echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns
echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting
LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=100; fi
#LOG=249
sudo sysctl -w net.core.latency_breakdown_log=$LOG

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=1'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_rx_sched_lat_only=1'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_nrfs=0'
ssh jaehyun\@128.84.155.146 -t 'echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns'
ssh jaehyun\@128.84.155.146 -t 'echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns'
ssh jaehyun\@128.84.155.146 -t 'echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features'
ssh jaehyun\@128.84.155.146 -t 'echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on'
ssh jaehyun\@128.84.155.146 -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"
ssh jaehyun\@128.84.155.146 -t "echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting"

TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
#TASKSET="0,4,8,12,16,20,24,28"
mkdir -p $DIR

if [[ $DIM -eq 1 ]]
then
	echo "enable dim"
	ssh jaehyun\@128.84.155.146 -t 'sudo ethtool -C $INTF adaptive-rx on adaptive-tx on'
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
else
	ssh jaehyun\@128.84.155.146 -t 'sudo ethtool -C $INTF adaptive-rx off adaptive-tx off'
	ssh jaehyun\@128.84.155.146 -t 'sudo ethtool -C $INTF rx-frames 28 rx-usecs 50'
	sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
	sudo ethtool -C $INTF rx-frames 28 rx-usecs 50
fi

if [[ $PIN -eq 1 ]]
then
	echo "pin"
    ssh jaehyun\@128.84.155.146 -t "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.10.125 --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin > /home/jaehyun/server.log" &
	sleep 3
	echo "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.10.125 --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin > /home/qizhe/latency/temp/server.log"
	sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.10.125:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin tcpppasync > temp/client.log &
	echo "sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.10.125:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin tcpppasync"
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
else
	echo "no pin"
    ssh jaehyun\@128.84.155.146 -t "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.10.125 --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE > /home/jaehyun/server.log" &
	sleep 3
	sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.10.125:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE tcpppasync  > temp/client.log&
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
fi
# for i in `seq 1 $N`; do
        # sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
# done

# sleep 3

# # for i in `seq 1 $N`; do
# 	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
# 	sudo taskset -c $TASKSET nice -n -20  ./netdriver_test_multithread 192.168.10.125:$DPORT --sp 10000 --count $N  --iodepth $IODEPTH --flowsize $SIZE tcpppasync &
# 	PIDS="$PIDS $!"
# 	echo "pid $PIDS dport $DPORT"
	#DPORT=$(($DPORT+1))
# done

# run compute app
if [[ $TAPP -eq 1 ]]
then
	echo "run compute bound app"
	if [[ $TAPPSCHED -eq 1 ]]
	then
		echo "sched idle"		
		ssh jaehyun\@128.84.155.146 -t "cd /home/qizhe/latency; sudo taskset -c $TASKSET nice -n 0 ./compute_md 16 $TAPPSCHED" &
		PIDS2="$PIDS2 $!"
		echo "pid2 $PIDS2"
	else
		echo "sched normal"		
		ssh jaehyun\@128.84.155.146 -t "cd /home/qizhe/latency; sudo taskset -c $TASKSET nice -n 19 ./compute_md 16 $TAPPSCHED" &
		PIDS2="$PIDS2 $!"
		echo "pid2 $PIDS2"
	fi
fi


sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

wait $PIDS
kill -9 $PIDS2

# get compute log
ssh jaehyun\@128.84.155.146 -t 'sudo killall compute_md'
scp -r jaehyun\@128.84.155.146:/home/qizhe/latency/temp/compute*.log temp/
scp -r jaehyun\@128.84.155.146:/home/jaehyun/server.log temp/
ssh jaehyun\@128.84.155.146 -t 'sudo rm -rf /home/qizhe/latency/temp/compute*.log'

PIDS2="$!"
# client-side
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=0'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_rx_sched_lat_only=0'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_nrfs=0'
ssh jaehyun\@128.84.155.146 -t 'sudo cat /sys/kernel/debug/tracing/trace' > $DIR/latencies-$N-server.log
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo killall pingpong_server'
ssh jaehyun\@128.84.155.146 -t "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
