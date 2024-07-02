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

if [ "$IRQCORES" -eq 2 ]; then 
	TASKSET="0,4,8,12,16,20"
	TASKSET2="0,4,8,12,16,20,56,60"
elif [ "$IRQCORES" -eq 3 ]; then 
	TASKSET="0,4,8,12,16"
	TASKSET2="0,4,8,12,16,52,56,60"
elif [ "$IRQCORES" -eq 4 ]; then 
	TASKSET="0,4,8,12"
	TASKSET2="0,4,8,12,48,52,56,60"
elif [ "$IRQCORES" -eq 5 ]; then 
	TASKSET="0,4,8,12,16,20,24,28,32,36,40"
elif [ "$IRQCORES" -eq 6 ]; then
    TASKSET="0,4,8,12,16,20,24,28,32,36"
elif [ "$IRQCORES" -eq 7 ]; then
        TASKSET="0,4,8,12,16,20,24,28,32"
elif [ "$IRQCORES" -eq 8 ]; then
        TASKSET="0,4,8,12,16,20,24,28"
else 
	echo "invalid #irq cores"
fi

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
# sudo sysctl -w net.core.latency_breakdown_nrfs=3
# echo 100000 | sudo tee /proc/sys/kernel/sched_latency_ns
# echo 100000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
# echo HRTICK | sudo tee /sys/kernel/debug/sched_features
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


# TASKSET2="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
TASKSET3="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
TASKSET4="1,5,9,13,17,21,25,29,33,37,41,45,49,53,57,61"

thread=$((16))
echo $thread
if [[ "$N" -lt $((32)) ]]; then
   thread=$(($N/2))
fi

mkdir -p $DIR
# for i in `seq 1 $N`; do
        #sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
        ssh jaehyun\@128.84.155.146 "cd /home/qizhe/redis;sudo taskset -c $TASKSET  ./run_server.sh $thread" > debug &
# done

sleep 2

# for i in `seq 1 $N`; do
	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	sudo taskset -c $TASKSET3 nice -n -20 /home/qizhe/redis/redis_async 192.168.10.125 10000 $(($thread)) 0.18 $IODEPTH $(($N/2)) > temp/client_1.log&
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	sudo taskset -c $TASKSET4 nice -n -20 /home/qizhe/redis/redis_async 192.168.10.125 10000 $(($thread)) 0.18 $IODEPTH $(($N/2)) > temp/client_2.log&
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
	#DPORT=$(($DPORT+1))
# done

# for i in `seq 1 8`; do
ssh jaehyun\@128.84.155.146 -t "cd /home/qizhe/latency; sudo taskset -c $TASKSET2 nice -n 19 ./compute_md 16" &
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
ssh jaehyun\@128.84.155.146 -t 'sudo killall redis-server'
