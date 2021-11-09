if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
DPORT=5001
#sudo trace-cmd clear
#sudo sysctl -w net.core.latency_breakdown_on=1
#echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
#LOG=$((997 / $N))
#if [[ $N -gt 10 ]]; then LOG=100; fi
#sudo sysctl -w net.core.latency_breakdown_log=$LOG
mkdir -p $DIR
for i in `seq 1 $N`; do
	#sudo taskset -c 0 netperf -H 192.168.10.146 -t TCP_RR -l 10 -f g -j -- -r $SIZE,$SIZE -o throughput,mean_latency,p50_latency,p99_latency &> $DIR/netperf-$i-$N.log&
	sudo taskset -c 0 netperf -H 192.168.10.146 -t TCP_RR -l 60 -f m -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p50_latency,p99_latency &> $DIR/netperf-$i-$N.log&
	PIDS="$PIDS $!"
	echo "pid $PIDS dport $DPORT"
	DPORT=$(($DPORT+1))
done

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

wait $PIDS
#sudo sysctl -w net.core.latency_breakdown_on=0
#sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
#sudo trace-cmd clear
