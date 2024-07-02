if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
DPORT=5001

sleep 5
# client-side
sudo /home/qizhe/caladan/iokerneld ias noidlefastwake noht 0,32,4,36,8,40,12,44,16,48,20,52,24,56,28,60 &

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo /home/qizhe/caladan/iokerneld ias noidlefastwake noht 0,32,4,36,8,40,12,44,16,48,20,52,24,56,28,60' &

mkdir -p $DIR
sleep 10
# for i in `seq 1 $N`; do
        #sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
        ssh jaehyun\@128.84.155.146 -t "sudo /home/qizhe/caladan/apps/bench/netperf  /home/qizhe/caladan/server.config server 8080" &
# done

sleep 10

# for i in `seq 1 $N`; do
	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	# echo "/home/qizhe/caladan/apps/bench/netperf  /home/qizhe/caladan/client.config tcprr 192.168.10.125 $N 180 $SIZE"
	sudo /home/qizhe/caladan/apps/bench/netperf  /home/qizhe/caladan/client.config tcprr 192.168.10.125 $N 180 $SIZE 8080 0&
	PIDS="$PIDS $!"
	# echo "pid $PIDS dport $DPORT"
	#DPORT=$(($DPORT+1))
# done

# for i in `seq 1 8`; do
ssh jaehyun\@128.84.155.146 -t "sudo -s; cd /home/qizhe/latency;sudo /home/qizhe/caladan/apps/bench/compute_md /home/qizhe/caladan/compute.config 8 0" &
PIDS2="$PIDS2 $!"
# echo "pid2 $PIDS2"
# done

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

wait $PIDS
wait $PIDS2
# get compute log
ssh jaehyun\@128.84.155.146 -t 'sudo killall compute_md'
scp -r jaehyun\@128.84.155.146:/home/qizhe/latency/temp/compute*.log temp/
ssh jaehyun\@128.84.155.146 -t 'sudo rm -rf /home/qizhe/latency/temp/compute*.log'

# client-side
sudo killall iokerneld

# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo killall iokerneld'
ssh jaehyun\@128.84.155.146 -t 'sudo killall netperf'
