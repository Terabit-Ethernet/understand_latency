if [[ $# < 3 ]]; then
    echo "usage: netperf.sh NUM_APPS DIR SIZE"
    exit 1
fi
N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
DPORT=5001

TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"

thread=11
bytes=$(($SIZE*$IODEPTH))
if [[ "$N" -lt 11 ]]; then
   thread=$N
fi
echo $thread
echo $bytes
#sleep 30
# client-si3e
sudo /home/qizhe/tas/tas/tas --ip-addr=192.168.10.124/24 --fp-cores-max=3 --fp-no-autoscale --tcp-link-bw=100 --dpdk-extra="-w" --dpdk-extra="0000:25:00.0" --dpdk-extra="-l" --dpdk-extra="0,4,8,12" > temp/tas_client.log &
# server-side
#
ssh jaehyun\@128.84.155.146 -t 'sudo /home/qizhe/tas/tas/tas --ip-addr=192.168.10.125/24 --fp-cores-max=3 --fp-no-autoscale --tcp-link-bw=100 --dpdk-extra="-w" --dpdk-extra="0000:25:00.0" --dpdk-extra="-l" --dpdk-extra="0,4,8,12" &' > temp/tas_server.log &

mkdir -p $DIR
sleep 20
# for i in `seq 1 $N`; do
        #sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
        # ssh jaehyun\@128.84.155.146 -t "sudo LD_PRELOAD=/home/qizhe/tas/lib/libtas_interpose.so taskset -c $TASKSET /home/qizhe/latency/pingpong_server_tas  --ip 192.168.10.125 --port 9090 --iodepth $IODEPTH --flowsize $SIZE " &
# done
ssh jaehyun\@128.84.155.146 -t "sudo LD_PRELOAD=/home/qizhe/tas/lib/libtas_interpose.so taskset -c 16,20,24,28,32,36,40,44,48,52,56,60 nice -n -20 /home/qizhe/tas/benchmarks/micro_rpc/echoserver_linux 1234 $thread foo 4096 $bytes" > temp/server.log &
sleep 10

# for i in `seq 1 $N`; do
	#sudo taskset -c 0 nice -n -19 netperf -H 192.168.10.146 -t TCP_RR -l 100 -f g -j -p $DPORT -- -r $SIZE,$SIZE -o throughput,mean_latency,p99_latency,p999_latency &> $DIR/netperf-$i-$N.log&
	# echo "/home/qizhe/caladan/apps/bench/netperf  /home/qizhe/caladan/client.config tcprr 192.168.10.125 $N 180 $SIZE"
	# sudo LD_PRELOAD=/home/qizhe/tas/lib/libtas_interpose.so taskset -c $TASKSET ./netdriver_test_multithread_tas 192.168.10.125:9090 --sp 5000 --count $N --iodepth  $IODEPTH --flowsize $SIZE tcpppasync &
sudo LD_PRELOAD=/home/qizhe/tas/lib/libtas_interpose.so taskset -c 16,20,24,28,32,36,40,44,48,52,56,60  nice -n -20 /home/qizhe/tas/benchmarks/micro_rpc/testclient_linux 192.168.10.125 1234 $thread foo $SIZE $IODEPTH $N > temp/client.log &
PIDS="$PIDS $!"
	# echo "pid $PIDS dport $DPORT"
	#DPORT=$(($DPORT+1))
# done

# for i in `seq 1 8`; do
ssh jaehyun\@128.84.155.146 -t "cd /home/qizhe/latency; sudo taskset -c $TASKSET nice -n 19 ./compute_md 16" &
PIDS2="$PIDS2 $!"
# echo "pid2 $PIDS2"
# done

sar -u 55 1 -P ALL > $DIR/cpu-$N.log &
ssh jaehyun\@128.84.155.146 -t 'sar -u 55 1 -P ALL' > $DIR/cpu-server-$N.log &

sleep 480
# wait $PIDS
# wait $PIDS2
# get compute log
ssh jaehyun\@128.84.155.146 -t 'sudo killall compute_md'
scp -r jaehyun\@128.84.155.146:/home/qizhe/latency/temp/compute*.log temp/
ssh jaehyun\@128.84.155.146 -t 'sudo rm -rf /home/qizhe/latency/temp/compute*.log'

# client-side
sudo killall testclient_linux
sudo killall tas
# sudo killall netdriver_test_multithread_tas
# server-side
ssh jaehyun\@128.84.155.146 -t 'sudo killall tas echoserver_linux'
ssh jaehyun\@128.84.155.146 -t 'sudo killall pingpong_server_tas'
