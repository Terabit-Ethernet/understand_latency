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
4. The structure of directories should look like:

```
$TARGETDIR/
├── latency/                   # Latency directory
│   ├── ...
├── iter_thread/                    # iter_thread module

```
## Running experiments

#### Single core:
```
./run_mc_all_params.sh 
```

#### Multiple cores:

```
./run_mc_all_params_multi_core.sh 
```

#### netdriver_multithread.cc and pingpong_server.cc are needed to change two places:

1. Whether or not using round-robin scheduler:
```
//      struct sched_param param;
//      param.sched_priority = 99;
//      sched_setscheduler(pid, SCHED_RR, &param);
```
2. Whether or not using single core or multiple cores:

  Single core:
  ```
  threads_per_core = count / 2;
  ```
  Multiple cores:
  ```
  threads_per_core = count / 16;
  ```
  
#### whether to track rx_sched only :

In `linux-both-8c-compute.sh` (single core) or `linux-both-8c-compute-hd.sh `(multiple cores):

1. only track rx_sched latency:
```
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=1
```

2. track all latency:
```
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
```


## Note
1. trace_printk will discard some output for the latency breakdown. https://stackoverflow.com/questions/57141796/how-to-print-full-trace-file-of-trace-printk-in-ftrace. To solve this, we need to increase buffer_size_skb:
   ```
   sudo -s
   echo $LARGE_SIZE > buffer_size_kb
   ```

