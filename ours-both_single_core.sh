if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
IRQCORES=$5
COMPUTE=$6
DPORT=5001

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_breakdown_nrfs=$IRQCORES
echo 100000 | sudo tee /proc/sys/kernel/sched_latency_ns
echo 100000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
echo HRTICK | sudo tee /sys/kernel/debug/sched_features
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on

# Get log frequency
LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=100; fi
LOG=249
sudo sysctl -w net.core.latency_breakdown_log=$LOG



# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=1'
ssh jaehyun\@128.84.155.146 -t "sudo sysctl -w net.core.latency_breakdown_nrfs=$IRQCORES"
ssh jaehyun\@128.84.155.146 -t 'echo 100000 | sudo tee /proc/sys/kernel/sched_latency_ns'
ssh jaehyun\@128.84.155.146 -t 'echo 100000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns'
ssh jaehyun\@128.84.155.146 -t 'echo HRTICK | sudo tee /sys/kernel/debug/sched_features'
ssh jaehyun\@128.84.155.146 -t 'echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on'
ssh jaehyun\@128.84.155.146 -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"

mkdir -p $DIR

ssh jaehyun\@128.84.155.146 -t "sudo taskset -c 0 nice -n -20 netserver -p $((DPORT))"

sleep 3

for i in `seq 1 $N`; do
	sudo taskset -c 0 netperf -H 192.168.10.125 -t TCP_RR -l 600 -f g -j -p $DPORT -- -r $SIZE,$SIZE -b $IODEPTH,$IODEPTH -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
#	DPORT=$(($DPORT+1))
done
if [[ $COMPUTE -eq 1 ]] 
then  
	for i in `seq 1 2`; 
	do
			ssh jaehyun\@128.84.155.146 -t "sudo taskset -c 0,28 nice -n 19 /home/jaehyun/latency/compute" > $DIR/compute-$i-2.log &
			PIDS2="$PIDS2 $!"
			echo "pid2 $PIDS2"
	done
fi

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

wait $PIDS

if [[ $COMPUTE -eq 1 ]] 
then
	kill -9 $PIDS2
fi

# client-side
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns
echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features
sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_on=0'
ssh jaehyun\@128.84.155.146 -t 'sudo sysctl -w net.core.latency_breakdown_nrfs=0'
ssh jaehyun\@128.84.155.146 -t 'echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns'
ssh jaehyun\@128.84.155.146 -t 'echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns'
ssh jaehyun\@128.84.155.146 -t 'echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features'
ssh jaehyun\@128.84.155.146 -t 'sudo cat /sys/kernel/debug/tracing/trace' > $DIR/latencies-$N-server.log
ssh jaehyun\@128.84.155.146 -t 'sudo trace-cmd clear'
ssh jaehyun\@128.84.155.146 -t 'sudo killall netserver'
