# latency

## Setup
1. Host side: `./host_setup.sh`; target side: "./target_setup.sh".
2. Check the hw time and os time diff: `sudo phc_ctl ens2f1 cmp`.

## Running experiments
1. Hyperthreading experiments,
  ```
  sudo ./run_mc_all_params_hd.sh 
  ```
  
## Note
1. trace_printk will discard some output for the latency breakdown. https://stackoverflow.com/questions/57141796/how-to-print-full-trace-file-of-trace-printk-in-ftrace
