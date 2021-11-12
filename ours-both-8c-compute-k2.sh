if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
IRQCORES=$5
DPORT=5001

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_breakdown_nrfs=$IRQCORES
echo 100000 | sudo tee /proc/sys/kernel/sched_latency_ns
echo 100000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
echo HRTICK | sudo tee /sys/kernel/debug/sched_features
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=100; fi
#LOG=100
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
#ssh jaehyun\@128.84.155.146 -t "sudo sysctl -w net.core.latency_breakdown_log=50"

TASKSET="0,4,8,12,16,20"
TASKSET2="0,4,8,12,16,20,24,28"

mkdir -p $DIR
# for i in `seq 1 $N`; do
        #sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
        ssh jaehyun\@128.84.155.146 -t "sudo taskset -c $TASKSET nice -n -20 /home/qizhe/latency/pingpong_server  --ip 192.168.10.125 --port $((DPORT))" &
# done

sleep 3

# for i in `seq 1 $N`; do
	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	sudo taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread 192.168.10.125:$DPORT --sp 10000 --count $N tcpppasync &
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
	#DPORT=$(($DPORT+1))
# done

# for i in `seq 1 8`; do
ssh jaehyun\@128.84.155.146 -t "cd /home/qizhe/latency; sudo taskset -c $TASKSET nice -n 19 ./compute_md 8" &
PIDS2="$PIDS2 $!"
echo "pid2 $PIDS2"
# done

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

wait $PIDS
kill -9 $PIDS2
# get compute log
ssh jaehyun\@128.84.155.146 -t 'sudo killall compute_md'
scp -r jaehyun\@128.84.155.146:/home/qizhe/latency/temp/compute*.log temp/
ssh jaehyun\@128.84.155.146 -t 'sudo rm -rf /home/qizhe/latency/temp/compute*.log'

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
ssh jaehyun\@128.84.155.146 -t 'sudo killall pingpong_server'
