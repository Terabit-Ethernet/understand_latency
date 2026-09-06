#!/bin/bash

N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
DIM=$5
PIN=$6
PERMUTE=$7

DPORT=5001
CLIENT_TIME=300

source ../env.sh

mkdir -p ../temp
ssh $USER\@$TARGETC -t "mkdir -p $TARGETDIR/latency/temp"

echo "$DIR"

LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=200; fi
uname -r > $DIR/kernel_version.log

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_log=$LOG
sudo sysctl -w net.core.latency_breakdown_validation=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=1000
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0 # 0 means enable clamp now
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_perstage_rdpmc_on=0 # enable rdpmc for latency breakdown
# sudo sysctl -w kernel.sched_wakeup_granularity_ns=999999999 # Note: this is used to disable wake up preemption

echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting


# server-side
ssh $USER\@$TARGETC -t "sudo trace-cmd clear"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_on=1"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_weight=1000"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_perstage_rdpmc_on=0"

ssh $USER\@$TARGETC -t "echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"


# DIM settings: DIM_DISABLED = 0, DIM_ENABLED = 1, DIM_AUTO = 2
if [[ $DIM -eq 0 ]];
then
	echo "[DIM] Disabled"
	ssh $USER\@$TARGETC -t "sudo ethtool -C $INTF adaptive-rx off adaptive-tx off"
	sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
elif [[ $DIM -eq 1 ]];
then
	echo "[DIM] Enabled"
	ssh $USER\@$TARGETC -t "sudo ethtool -C $INTF adaptive-rx on adaptive-tx on"
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
else
    FRAMES=$(((N+3)/4))	# frames = N/4
    USECS=$((N)) # usecs = N

    echo "[DIM] Automatic tuning: rx/tx-frames: $FRAMES rx/tx-usecs:  $USECS"
    ssh $USER@$TARGETC -t "sudo ethtool -C $INTF adaptive-rx off adaptive-tx off"
    ssh $USER@$TARGETC -t "sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS"
    sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
    sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS
fi


TASKSET="1,73"

cat /proc/interrupts > $DIR/interrupt_before
cat /proc/softirqs > $DIR/softirq_before
ifconfig $INTF > $DIR/ifconfig_before
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_before_server
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_before_server
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_before_server


ssh "$USER@$TARGETC" -t "
  sudo sh -c '
    ulimit -n 65536
    exec taskset -c $TASKSET nice -n -20 \
      $TARGETDIR/latency/application/latency_server \
      --ip $TARGET --port $DPORT --count $N --iodepth $IODEPTH --flowsize $SIZE \
      --pin $PIN --permute $PERMUTE --sc 1
  ' > $TARGETDIR/latency/temp/server.log 2>&1
" &

echo "sudo sh -c '
  ulimit -n 65536
  exec taskset -c $TASKSET nice -n -20 \
    $TARGETDIR/latency/application/latency_server \
    --ip $TARGET --port $DPORT --count $N --iodepth $IODEPTH --flowsize $SIZE \
    --pin $PIN --permute $PERMUTE --sc 1
' > $TARGETDIR/latency/temp/server.log 2>&1"

sleep 3

sudo sh -c '
  ulimit -n 65536
  exec taskset -c '"$TASKSET"' nice -n -20 \
    ../application/latency_client \
    '"$TARGET"':'"$DPORT"' \
    --count '"$N"' \
    --iodepth '"$IODEPTH"' \
    --flowsize '"$SIZE"' \
    --pin '"$PIN"' \
    --sc 1 \
    --time '"$CLIENT_TIME"' \
    tcpppasync
' > ../temp/client.log 2>&1 &


echo "sudo sh -c '
  ulimit -n 65536
  exec taskset -c $TASKSET nice -n -20 \
    ../application/latency_client \
    $TARGET:$DPORT \
    --count $N \
    --iodepth $IODEPTH \
    --flowsize $SIZE \
    --pin $PIN \
    --sc 1 \
    --time $CLIENT_TIME \
    tcpppasync
' > ../temp/client.log 2>&1 &"


PIDS="$PIDS $!"
echo "pid $PIDS dport $DPORT"

sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL > $DIR/cpu-$N.log &
ssh $USER\@$TARGETC -t "sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL" > $DIR/cpu-server-$N.log &


wait $PIDS
kill -9 $PIDS2


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

sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear

echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting

# output involuntary context switch count in server side: get_involuntary_ctx_switch.py. Note the client side data are directly printed in netdriver_test_multithread.cc to client.log

# server-side
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_weight=156"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_perstage_rdpmc_on=0"

ssh $USER\@$TARGETC -t "sudo cat /sys/kernel/debug/tracing/trace > $TARGETDIR/latency/temp/latencies-$N-server.log"
ssh $USER\@$TARGETC -t "sudo trace-cmd clear"

ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"


ssh $USER\@$TARGETC -t "sudo killall latency_server"

# move latencies log
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/latencies-$N-server.log $DIR
ssh $USER\@$TARGETC -t "sudo rm -rf $TARGETDIR/latency/temp/*"


# Move data to experiment result folder
sudo mv ../temp/*.log $DIR/
sudo mv ../temp/*.bin $DIR/

# Parse the throughput and latency
./parse-netperf.py $DIR $N > $DIR/linux_latency


cat /proc/interrupts > $DIR/interrupt_after
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_after_server
cat /proc/softirqs > $DIR/softirq_after
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_after_server
ifconfig $INTF > $DIR/ifconfig_after
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_after_server

echo "done"  
