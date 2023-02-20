# latency

## Setup
1. Host side: `./host_setup.sh`; target side: "./target_setup.sh".
2. Check the hw time and os time diff: `sudo phc_ctl ens2f1 cmp`.

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




### Old scripts:
  ```
  sudo ./run_mc_all_params.sh 
  ```
  Running TAS (linux 5.4),
  ```
  sudo ./run_mc_all_params_hd_tas.sh
  ```
  TAS performance is not very stable, we pick the best possible performance.
  
2. IO Depth,

```
sudo ./run_mc_all_params_iodepth.sh
```

```
sudo ./run_mc_all_params_tas_iodepth.sh
```

3. Flow Size,
```
run_mc_all_params_flowsize.sh
```

```
sudo ./run_mc_all_params_tas_flowsize.sh
```

## Note
1. trace_printk will discard some output for the latency breakdown. https://stackoverflow.com/questions/57141796/how-to-print-full-trace-file-of-trace-printk-in-ftrace
