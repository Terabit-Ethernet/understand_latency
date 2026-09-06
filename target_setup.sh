#!/bin/bash

# Disable Deep C-State
for g in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state[123]/disable; do
  echo 1 | sudo tee "$g"
done

# Get the dir of this project
DIR=$(realpath $(dirname $(readlink -f $0)))

# Source the environment file
source $DIR/env.sh

# Configure network
sudo ifconfig $INTF mtu 9000
sudo ifconfig $INTF $TARGET

# Enable aRFS, GRO, GSO, TSO, and disable LRO
sudo service irqbalance stop
sudo ethtool -K $INTF ntuple on gro on gso on tso on lro off
echo 32768 | sudo tee /proc/sys/net/core/rps_sock_flow_entries
for f in /sys/class/net/$INTF/queues/rx-*/rps_flow_cnt; do echo 32768 | sudo tee $f; done

# Set IRQ affinity for the network interface
sudo affinity_tool/set_irq_affinity.sh $INTF

# Increase sock size limits
sudo sysctl -w net.core.wmem_max=12582912
sudo sysctl -w net.core.rmem_max=12582912

# Enable hardware timestamps
sudo hwstamp_ctl -i $INTF -r 1

# Keep the hardware timer synchronized with the system clock
sudo phc2sys -s CLOCK_REALTIME -c $INTF -O 0 -m &

# change the open file limit
ulimit -n 8192

# Set the tracing buffer size
echo 451200 |sudo tee /sys/kernel/debug/tracing/buffer_size_kb
echo "Setup host done!"
exit
