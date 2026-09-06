#!/bin/bash

N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
DIM=$5
# off = 0, on = 1
PIN=$6
PERMUTE=$7
SC=${8}

DPORT=5001

CLIENT_TIME=300

# DIR=$(realpath $(dirname $(readlink -f $0)))
source env.sh

echo "$DIR"

LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=200; fi
uname -r > $DIR/kernel_version.log

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_log=$LOG
sudo sysctl -w net.core.latency_breakdown_validation=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=1000
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0 # 0 means enable clamp now
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_perstage_rdpmc_on=0 # enable rdpmc for latency breakdown
# sudo sysctl -w kernel.sched_wakeup_granularity_ns=999999999 # Note: this is used to disable wake up preemption

echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting


# server-side
ssh $USER\@$TARGETC -t "sudo trace-cmd clear"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_weight=1000"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_perstage_rdpmc_on=0"

ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"


# DIM settings: DIM_DISABLED = 0, DIM_ENABLED = 1, DIM_AUTO = 2
if [[ $DIM -eq 0 ]];
then
	echo "[DIM] Disabled"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
	sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
elif [[ $DIM -eq 1 ]];
then
	echo "[DIM] Enabled"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx on adaptive-tx on"
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
else
    FRAMES=$(((N+3)/4))	# frames = N/4
    USECS=$((N)) # usecs = N

    echo "[DIM] Automatic tuning: rx/tx-frames: $FRAMES rx/tx-usecs:  $USECS"
    ssh $USER@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
    ssh $USER@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS"
    sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
    sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS
fi



#TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
#TASKSET="32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111"
if [[ $SC -eq 1 ]];
then
	TASKSET="32,96"
else
	TASKSET="32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111"
fi

cat /proc/interrupts > $DIR/interrupt_before
cat /proc/softirqs > $DIR/softirq_before
ifconfig $INTF > $DIR/ifconfig_before
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_before_server
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_before_server
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_before_server


# #　Enable virtual runtime monitoring: total_count=1200 interval_ms=100
# sudo insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300 interval_ms=1000
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300 interval_ms=1000"



# # eanble packet distribution
# sudo insmod $TARGETDIR/pkt_dist/filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo insmod $TARGETDIR/pkt_dist/filter.ko"
# echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"



# # # Enable Netfilter
# sudo insmod $TARGETDIR/netfilter/filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/netfilter/filter.ko"
# # echo 5200 | sudo tee /sys/module/filter/parameters/base_target
# # ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 5200 | sudo tee /sys/module/filter/parameters/base_target"
# echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"


# Start server side
ssh $USER\@$TARGETC -t "python3 $TARGETDIR/latency/get_involuntary_ctx_switch.py --time 300 > $TARGETDIR/latency/temp/server_nivcsw.log" &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --permute $PERMUTE --sc $SC > $TARGETDIR/latency/temp/server.log" &
ssh $USER\@$TARGETC -t "
  echo '$SUDOPW' | sudo -S zsh -c '
    ulimit -n 65536
    exec taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server \
      --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE \
      --pin $PIN --permute $PERMUTE --sc $SC \
      > $TARGETDIR/latency/temp/server.log 2>&1
  '
" &

echo "sudo taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN  > $TARGETDIR/latency/temp/server.log"
sleep 3

# seq 24 | while read i; do date "+%F %T" >> temp/dim.log; ethtool -c $INTF | egrep "Adaptive RX|rx-usecs:|rx-frames:|tx-usecs:|tx-frames:" >> temp/dim.log; sleep 5; done &
# sudo taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync  > temp/client.log &
sudo zsh -c 'ulimit -n 65536; exec taskset -c '"$TASKSET"' nice -n -20 ./netdriver_test_multithread '"$TARGET"':'"$DPORT"' --count '"$N"'  --iodepth '"$IODEPTH"' --flowsize '"$SIZE"' --pin '"$PIN"' --sc '"$SC"' --time '"$CLIENT_TIME"' tcpppasync > temp/client.log' &

echo "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync"
PIDS="$PIDS $!"
echo "pid $PIDS dport $DPORT"

sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL > $DIR/cpu-$N.log &
ssh $USER\@$TARGETC -t "sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL" > $DIR/cpu-server-$N.log &


wait $PIDS
kill -9 $PIDS2

echo $SUDOPW | sudo -S echo "Local shell privilege escalation after experiment successful"

# get compute log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S killall compute_md"
sleep 15 # wait for server side perf/bpftrace to finish


scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/server.log temp/
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/server_nivcsw.log temp/


PIDS2="$!"
# client-side
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo sysctl -w net.core.latency_breakdown_validation=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=156 # just reset to default value
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_perstage_rdpmc_on=0

# sudo sysctl -w kernel.sched_wakeup_granularity_ns=4000000

sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting

# output involuntary context switch count in server side: get_involuntary_ctx_switch.py. Note the client side data are directly printed in netdriver_test_multithread.cc to client.log

# server-side
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_weight=156"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_perstage_rdpmc_on=0"

# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w kernel.sched_wakeup_granularity_ns=4000000"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S cat /sys/kernel/debug/tracing/trace > $TARGETDIR/latency/temp/latencies-$N-server.log"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S killall pingpong_server"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"

# move latencies log
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/latencies-$N-server.log $DIR
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rm -rf $TARGETDIR/latency/temp/*"


# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo ../perf sched script > temp/server_perf.log"
# scp -r $USER\@$TARGETC:/home/$USER/server_perf.log temp/

# # Stop processed packets in softIRQ monitoring:
# # 		We suppose to have 4*6*5 = 120 log entries for each time. Due to unwanted logs, we set 230 here (it will be safe as long as it is less than 2*120=240)
# # 		30000 entries for packet runqueue.
# #			Also note we can output the results along with virtual runtime.
# sudo rmmod filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 300  /var/log/kern.log > temp/filter_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 300  /var/log/kern.log" > temp/filter_server.log

# # remove iter sock
# # sudo rmmod iterate_inet_socks.ko
# # ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod iterate_inet_socks.ko"

# #remove pkt_dist
# sudo rmmod filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 500  /var/log/kern.log > temp/pkt_dist_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 500  /var/log/kern.log" > temp/pkt_dist_server.log

# # Stop virtual runtime monitoring:
# 	# 550 for only iter_thread, 700 for both iter_thread and filter, 6000 for finer details
# sudo rmmod iter_thread
# sudo tail -n 1700  /var/log/kern.log > $DIR/iter_thread_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rmmod iter_thread"
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S tail -n 1700  /var/log/kern.log" > $DIR/iter_thread_server.log

# # Stop rdpmc monitoring
# echo 1 | sudo tee /proc/sys/kernel/nmi_watchdog
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /proc/sys/kernel/nmi_watchdog"
# sudo rmmod latency_pmu
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rmmod latency_pmu"

# Move data to experiment result folder
sudo mv temp/*.log $DIR/
sudo mv temp/*.bin $DIR/
# sudo mv temp/cache_sample_server.data $DIR/
# sudo mv temp/perf_sample_client.svg $DIR/
# sudo mv temp/perf_sample_server.svg $DIR/
./parse/parse-netperf.py $DIR $N > $DIR/linux_latency

# if [[ $IODEPTH -eq 1 ]];
# then
# 	./parse/parse-breakdown-server.py $DIR $N > $DIR/linux_latency_breakdown_s
# 	./parse/parse-breakdown.py $DIR $N >  $DIR/linux_latency_breakdown_c 
# else
# 	./parse/parse-breakdown-rx_sched_c.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_c 
# 	./parse/parse-breakdown-rx_sched_s.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_s
# fi

cat /proc/interrupts > $DIR/interrupt_after
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_after_server
cat /proc/softirqs > $DIR/softirq_after
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_after_server
ifconfig $INTF > $DIR/ifconfig_after
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_after_server

echo "done"  
