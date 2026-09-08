#!/bin/bash

###############################################################################
# Arguments
###############################################################################

N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
DIM=$5
PIN=$6
PERMUTE=$7


###############################################################################
# Experiment configuration
###############################################################################

DPORT=5001
CLIENT_TIME=300
TASKSET="1,73"

source ../env.sh


###############################################################################
# Helper functions
###############################################################################

configure_latency_sysctls_local()
{
    sudo sysctl -w net.core.latency_breakdown_on=1
    sudo sysctl -w net.core.latency_rx_sched_lat_only=1
    sudo sysctl -w net.core.latency_breakdown_log=$LOG
    sudo sysctl -w net.core.latency_breakdown_validation=0
    sudo sysctl -w net.core.latency_dumb_schedule_weight=1000
    sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0
    sudo sysctl -w net.core.latency_dumb_schedule_enable=0
    sudo sysctl -w net.core.latency_perstage_rdpmc_on=0
    echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting
    echo 1 | sudo tee /sys/module/core/parameters/scheduler_accounting
}


configure_latency_sysctls_remote()
{
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_on=1"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=1"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_log=$LOG"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_validation=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_weight=1000"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_enable=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_perstage_rdpmc_on=0"
    ssh $USER\@$TARGETC -t \
        "echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
    ssh $USER\@$TARGETC -t \
        "echo 1 | sudo tee /sys/module/core/parameters/scheduler_accounting"
}


reset_latency_sysctls_local()
{
    sudo sysctl -w net.core.latency_breakdown_on=0
    sudo sysctl -w net.core.latency_rx_sched_lat_only=0
    sudo sysctl -w net.core.latency_breakdown_nrfs=0
    sudo sysctl -w net.core.latency_breakdown_validation=0
    sudo sysctl -w net.core.latency_dumb_schedule_weight=156
    sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0
    sudo sysctl -w net.core.latency_dumb_schedule_enable=0
    sudo sysctl -w net.core.latency_perstage_rdpmc_on=0
    echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
    echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting
}


reset_latency_sysctls_remote()
{
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_on=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_nrfs=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_breakdown_validation=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_weight=156"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_dumb_schedule_enable=0"
    ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_perstage_rdpmc_on=0"
    ssh $USER\@$TARGETC -t \
        "echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
    ssh $USER\@$TARGETC -t \
        "echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"
}


enable_tracing_local()
{
    sudo trace-cmd clear
    echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
}


enable_tracing_remote()
{
    ssh $USER\@$TARGETC -t "sudo trace-cmd clear"
    ssh $USER\@$TARGETC -t \
        "echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on"
}


disable_tracing_local()
{
    echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on
}


disable_tracing_remote()
{
    ssh $USER\@$TARGETC -t \
        "echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on"
}


collect_stats_before()
{
    # Client
    cat /proc/interrupts > $DIR/interrupt_before
    cat /proc/softirqs > $DIR/softirq_before
    ifconfig $INTF > $DIR/ifconfig_before

    # Server
    ssh $USER\@$TARGETC -t "cat /proc/interrupts" \
        > $DIR/interrupt_before_server

    ssh $USER\@$TARGETC -t "cat /proc/softirqs" \
        > $DIR/softirq_before_server

    ssh $USER\@$TARGETC -t "ifconfig $INTF" \
        > $DIR/ifconfig_before_server
}


collect_stats_after()
{
    # Client
    cat /proc/interrupts > $DIR/interrupt_after
    cat /proc/softirqs > $DIR/softirq_after
    ifconfig $INTF > $DIR/ifconfig_after

    # Server
    ssh $USER\@$TARGETC -t "cat /proc/interrupts" \
        > $DIR/interrupt_after_server

    ssh $USER\@$TARGETC -t "cat /proc/softirqs" \
        > $DIR/softirq_after_server

    ssh $USER\@$TARGETC -t "ifconfig $INTF" \
        > $DIR/ifconfig_after_server
}


###############################################################################
# Initialization
###############################################################################

mkdir -p ../temp
ssh $USER\@$TARGETC -t "mkdir -p $TARGETDIR/latency/temp"

echo "$DIR"


###############################################################################
# Latency log size
###############################################################################

if [[ $N -le 1 ]]; then
    LOG=10
elif [[ $N -ge 10 ]]; then
    LOG=200
else
    LOG=$((10 + (N - 1) * 190 / 9))
fi

echo "[CONFIG] N=$N LOG=$LOG"
echo "[CONFIG] SIZE=$SIZE IODEPTH=$IODEPTH PIN=$PIN PERMUTE=$PERMUTE"
echo "[CONFIG] TASKSET=$TASKSET CLIENT_TIME=$CLIENT_TIME"


###############################################################################
# Record kernel version
###############################################################################

uname -r > $DIR/kernel_version.log


###############################################################################
# Configure latency instrumentation
###############################################################################

echo "[SETUP] Configure client latency instrumentation"
enable_tracing_local
configure_latency_sysctls_local

echo "[SETUP] Configure server latency instrumentation"
enable_tracing_remote
configure_latency_sysctls_remote


###############################################################################
# Configure DIM
#
# DIM_DISABLED = 0
# DIM_ENABLED  = 1
# DIM_AUTO     = 2
###############################################################################

if [[ $DIM -eq 0 ]]; then

    echo "[DIM] Disabled"

    ssh $USER\@$TARGETC -t \
        "sudo ethtool -C $INTF adaptive-rx off adaptive-tx off"

    sudo ethtool -C $INTF adaptive-rx off adaptive-tx off

elif [[ $DIM -eq 1 ]]; then

    echo "[DIM] Enabled"

    ssh $USER\@$TARGETC -t \
        "sudo ethtool -C $INTF adaptive-rx on adaptive-tx on"

    sudo ethtool -C $INTF adaptive-rx on adaptive-tx on

else

    # frames ~= N / 4, rounded up
    FRAMES=$(((N + 3) / 4))
    USECS=$N

    echo "[DIM] Automatic tuning:"
    echo "      rx/tx-frames = $FRAMES"
    echo "      rx/tx-usecs  = $USECS"

    ssh $USER@$TARGETC -t \
        "sudo ethtool -C $INTF adaptive-rx off adaptive-tx off"

    ssh $USER@$TARGETC -t "sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS"

    sudo ethtool -C $INTF adaptive-rx off adaptive-tx off

    sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS
fi


###############################################################################
# Collect system state before the experiment
###############################################################################

echo "[STATS] Collecting pre-experiment statistics"
collect_stats_before


###############################################################################
# Start server
#
# NOTE:
# Keep the existing SSH mechanism and server launch mechanism unchanged.
###############################################################################

echo "[SERVER] Starting latency_server"

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


###############################################################################
# Give server time to initialize
###############################################################################

sleep 3


###############################################################################
# Start client
#
# NOTE:
# Keep the existing client launch mechanism unchanged.
###############################################################################

echo "[CLIENT] Starting latency_client"

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


CLIENT_PID=$!
PIDS="$PIDS $CLIENT_PID"

echo "[CLIENT] pid=$CLIENT_PID dport=$DPORT"


###############################################################################
# Start CPU utilization monitoring
###############################################################################

SAR_INTERVAL=60
SAR_COUNT=$((CLIENT_TIME / SAR_INTERVAL - 1))

echo "[SAR] interval=$SAR_INTERVAL count=$SAR_COUNT"

sar -u $SAR_INTERVAL $SAR_COUNT -P ALL \
    > $DIR/cpu-$N.log &

ssh $USER\@$TARGETC -t \
    "sar -u $SAR_INTERVAL $SAR_COUNT -P ALL" \
    > $DIR/cpu-server-$N.log &


###############################################################################
# Wait for client
###############################################################################

echo "[CLIENT] Waiting for client to finish"

wait $PIDS

echo "[CLIENT] Client finished"


###############################################################################
# Stop instrumentation and collect client trace
###############################################################################

echo "[CLEANUP] Client instrumentation"

reset_latency_sysctls_local

sudo cat /sys/kernel/debug/tracing/trace \
    &> $DIR/latencies-$N.log

sudo trace-cmd clear

disable_tracing_local


###############################################################################
# Stop instrumentation and collect server trace
###############################################################################

echo "[CLEANUP] Server instrumentation"

reset_latency_sysctls_remote

ssh $USER\@$TARGETC -t \
    "sudo cat /sys/kernel/debug/tracing/trace > \
     $TARGETDIR/latency/temp/latencies-$N-server.log"

ssh $USER\@$TARGETC -t "sudo trace-cmd clear"

disable_tracing_remote


###############################################################################
# Stop server
###############################################################################

ssh $USER\@$TARGETC -t "sudo killall latency_server"


###############################################################################
# Copy server-side logs
###############################################################################

echo "[LOG] Copying server logs"

scp -r \
    $USER\@$TARGETC:$TARGETDIR/latency/temp/server.log \
    $DIR

scp -r \
    $USER\@$TARGETC:$TARGETDIR/latency/temp/latencies-$N-server.log \
    $DIR

ssh $USER\@$TARGETC -t \
    "sudo rm -rf $TARGETDIR/latency/temp/*"


###############################################################################
# Move client-side logs
###############################################################################

echo "[LOG] Moving client logs"

sudo mv ../temp/*.log $DIR/
sudo mv ../temp/*.bin $DIR/


###############################################################################
# Parse throughput and latency
###############################################################################

echo "[PARSE] Parsing results"

../parse/parse_netperf.py $DIR $N \
    > $DIR/throughput.log


###############################################################################
# Collect system state after the experiment
###############################################################################

echo "[STATS] Collecting post-experiment statistics"

collect_stats_after


###############################################################################
# Done
###############################################################################

echo "done"