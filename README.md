# Understanding Host Network Stack Latency

## Setup
1. Install the Linux kernel in this [repo](https://github.com/Terabit-Ethernet/linux-latency). Before installing, changing the kernel configuration file to enable IRQ_TIME_ACCOUNTING.
3. Run the setup script in both servers. 
  host side: 
  ```
  `./host_setup.sh
  ```
  
  target side: 
  ```
  ./target_setup.sh
  ```
  You might need to change HOST and TARGET IP address in the `env.sh`

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

