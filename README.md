# Understanding Host Network Stack Latency

## Setup
1. Install the Linux kernel in this [repo](https://github.com/Terabit-Ethernet/linux-latency). Before installing, changing the kernel configuration file to enable IRQ_TIME_ACCOUNTING.

2. Hardware/Software Configuration:
We have used the follwing hardware and software configurations for running the experiments.

* CPU: 4-Socket Intel Xeon Gold 6234 3.3 GHz with 8 cores per socket (with hyperthreading enabled)
* RAM: 384 GB
* NIC: Mellanox ConnectX-5 Ex VPI (100 Gbps)
* OS: Ubuntu 20.04 with Linux 5.10.46

To run experiments, the client will initiate scripts to run programs on both the client and server. The parameters, including HOST (client) IP address, TARGET (server) IP address, and interface names, need to be set properly in `kernel_impl/env.sh`:
```
HOST=192.168.11.124
TARGET=192.168.11.125
INTF=ens2f1
USER=qizhe
TARGETDIR=/home/qizhe/
TARGETC=128.84.155.146
```

2. Run the setup script in both servers. 
  host side: 
  ```
  `./host_setup.sh
  ```
  
  target side: 
  ```
  ./target_setup.sh
  ```
3. Install kernel modules [iter_thread](https://github.com/Terabit-Ethernet/iter_thread) outside this repo.
4. Install kernel modules [pkt dist](https://github.com/Terabit-Ethernet/pkt_dist/tree/main) outside this repo.
5. The structure of directories should look like:

```
$TARGETDIR/
├── latency/                   # Latency directory
│   ├── ...
├── iter_thread/                    # iter_thread module
├── pkt_dist/                    # pkt_dist module
```
5. Note: trace_printk will discard some output for the latency breakdown. https://stackoverflow.com/questions/57141796/how-to-print-full-trace-file-of-trace-printk-in-ftrace. To solve this, we need to increase buffer_size_skb (which in host_setup.sh/target_setup.sh):
   ```
   sudo -s
   echo 451200 > /sys/kernel/debug/tracing/buffer_size_kb
   ```
## Running experiments

All experiments will be run using  `run_exp.py`. And results are stored in `results/`.

#### Single core:
1. Running single core, single IO depth with the number of threads results:
In run_exp.y, first change the setup inside run_exp.py:

```
hd="1"
our_patch="1"
c_state=1
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False
```
This allows to run experiments with increasing number of threads and repeat each experiment five times (decided by runs).

```
sudo -s
python3 run_exp.py
```

2. Similarly to run single core, fix number of threads and increasing number of IO depths:
In run_exp.py, first change the setup:
```
hd="1"
our_patch="1"
c_state=1
num_apps = [2, 8, 32]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1, 2, 4, 8, 16, 32, 64, 128, 256]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False
```

Then setting `latency_rx_sched_lat_only` to 1 in linux-both-8c-compute.sh:
```
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=1"
```

```
sudo -s
python3 run_exp.py
```

#### Multiple cores:

1. Running single core, single IO depth with the number of threads results:
In run_exp.y, first change the setup inside run_exp.py (changing the number of cores from 1 to 8; the core specifies the physical core):

```
hd="1"
our_patch="1"
c_state=1
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [8]
runs = [0, 1, 2, 3, 4]
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False
```
This allows to run experiments with increasing number of threads and repeat each experiment five times (decided by runs).

```
sudo -s
python3 run_exp.py
```

2. Similarly to run single core, fix number of threads and increasing number of IO depths:
In run_exp.py, first change the setup:
```
hd="1"
our_patch="1"
c_state=1
num_apps = [2, 8, 32]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1, 2, 4, 8, 16, 32, 64, 128, 256]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [8]
runs = [0, 1, 2, 3, 4]
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False
```

Then setting `latency_rx_sched_lat_only` to 1 in linux-both-8c-compute.sh:
```
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
ssh $USER\@$TARGETC -t "sudo sysctl -w net.core.latency_rx_sched_lat_only=1"
```

```
sudo -s
python3 run_exp.py
```


## Note

### For increasing IO-depth experiments we can only  track rx_sched rather than other breakdown values:

In `linux-both-8c-compute.sh:

1. only track rx_sched latency (for IO depth > 1):
```
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
```

2. track all latency (for IO depth = 1):
```
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
```

### Get packet distribution to check batching effect

In `linux-both-8c-compute.sh`, uncomment:

```
00 # sudo insmod $TARGETDIR/pkt_dist/filter.ko
101 # ssh $USER\@$TARGETC -t "sudo insmod $TARGETDIR/pkt_dist/filter.ko"
102 # echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
103 # ssh $USER\@$TARGETC -t "echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"
...
197 # ssh $USER\@$TARGETC -t "sudo rmmod filter.ko"
198 # sudo tail -n 60  /var/log/kern.log > temp/pkt_dist_client.log
199 # ssh $USER\@$TARGETC -t "sudo tail -n 61  /var/log/kern.log" > temp/pkt_dist_server.log
```

And comment iter_thread.ko out as outputs of two modules will mix up:
```
118 sudo insmod $TARGETDIR/iter_thread/iter_thread.ko &
119 ssh $USER\@$TARGETC -t "sudo insmod $TARGETDIR/iter_thread/iter_thread.ko" &
...
202 sudo tail -n 260  /var/log/kern.log > $DIR/iter_thread_client.log
203 sudo rmmod iter_thread
```
