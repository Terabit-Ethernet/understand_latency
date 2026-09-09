# Understanding Host Network Stack Latency — Experiment Set

Experiment set for our SIGCOMM '2026 paper "Understanding Host Network Stack Latency"

## Prelude
Note: This experiment set is not essential to understand the Linux network stack latency. Actually, with our [customized Linux kernel](https://github.com/Terabit-Ethernet/linux-latency), you should be able to run the latency analysis on any desired workload. This experiment set works as the reference point.

Note: we provide essential data analysis tools in `parse` folder **as reference**; it's extremely difficult for us to provide end-to-end (figure level) analysis tools since the experiment results may vary across different hardware configuration.

## Hardware Requirement

There are two hardware requirements: 
1. You must use an x86/64 CPU if you want to use the PMU programming module of ours --- You will also have to change the PMU event if you are using non-Intel CPU.
2. You must use an Mellanox NIC, since we rely on `mlx5e` driver instrumentation to report the recorded timestampes through ftrace framework.

We have used the follwing hardware and software configurations for running the experiments.

* CPU: 2-Socket Intel Xeon Gold 6530
* RAM: 1024 GB
* NIC: Mellanox ConnectX-7 (400 Gbps)
* Distro: Ubuntu 22.04
* Others: gcc/g++ 11.4.0 and GNU Make 4.3

## Software Requirement
You must uninstall all active OFED driver for NIC in your system since we rely on kernel's in-tree mlx5e driver to report the recorded timestamps when finally injectign the packet to the link.
Please refer to [NVIDIA](https://networking-docs.nvidia.com/mlnxofedswum/24.10-5.1.6.1lts/uninstalling-the-driver) for how to uninstalling OFED drivers.

Install the essential software:
1. We rely on `hwstamp_ctl` and `phc2sys` to sync time between CPU and NIC, and read NIC's hardware timestamp.
1. We rely on `sar` for CPU utilization monitoring.
1. We rely on `trace-cmd` for resetting ftrace buffer.
```sh
sudo apt update
sudo apt install linuxptp sysstat trace-cmd
```

The expeirment requires `numpy` for data processing, and `matplotlib` for essential plotting:
```sh
wget https://bootstrap.pypa.io/get-pip.py
python3 get-pip.py
python3 -m pip install numpy
python3 -m pip install matplotlib
```

## Kernel Installation

Please refer to https://github.com/Terabit-Ethernet/linux-latency for kernel installation. In this document, we will explicitely denote which kernel is required for each set of experiments.

Note: We recommend duplicate the clone for different kernel version since kernel compiling could be very slow, and we need to switch between different kernels. You MUST build separate kernel images for each machine. The latency monitor is keyed to the host's own IP address, which is hardcoded at compile time.

We assume we have two kernel: one is the default (e.g., 5.10.46-default), and one is for IRQa, ACCa, and PCSched (e.g., 5.10.46-latency), which are switched by runtime parameters.

## Artifact Evaluation Guide
Important: the experimental results from artifact evaluation may look different from that in our paper due to hardware differences. To fully reproduce the results in our paper, we recommend using exactly the same hardware (i.e., CPU, RAM, and NIC); that said, due to potential export control and policy issue, we might only be able to provide access to our own servers upon request.

### (Optional) CloudLab Setup
To facilitate the artifact evaluation, we recommend using the [**r650**](https://docs.cloudlab.us/hardware.html#(part._cloudlab-clemson))) type server from CloudLab. Our experiment scripts and settings in this section will also be based on r650 server.

Important: Different servers may have, most importantly, the CPU siblings mapping. If you are running experiments in other type servers, please make sure to prepare the applications correctly, following the instructions.

The experiment will generate significant amount of data. In this artifact evaluation guide, we mount the `nvme0n1` NVMe as `/data` to store all experiment output. We omit the NVMe mount setting steps (ChatGPT should help!). If you are using a different experiment environment, you should change the output directory in the experiment script.


### Experiment Diagram

<p align="center">
  <img src="image/latency_diagram.png" width="500
  "/>
</p>

The diagram shows the CPU layout, NIC interface and IP address for this evaluation guide based on r650 machines.

### Kernel Preparation
Note: do this in both server, with potentially different hardcoded parameters.

We assume you have installed the kernel and drivers as we instructed before. We should have two kernel in `/boot`:
1. `5.10.46-linux+`: This is the default Linux kernel that disable the IRQ time accounting option.
2. `5.10.46-latency+`: This is the experimental Linux kernel with IRQ time accounting; our design (ACCa and PCSched) will work through runtime parameter settings.

### Environment Preparation
Note: Do this on both server, with potentially different scripts.

1. Clone the project to `latency` under user's folder (e.g., `/users/netian` in r650 server).
    ```sh
    cd ~
    git clone https://github.com/Terabit-Ethernet/understand_latency.git latency
    ```

1. Update the env.sh to the correct physical settings. In the r650 server, the env.sh should look like below. `TARGETC` means the remote ssh server, `USER` means the ssh name for remote server, and `TARGETDIR` means the user's folder where `latency` project lies in the remote server. We assume `INTF` in both sides to be same; if not, please set them independently.
    ```sh
    HOST=192.168.1.101
    TARGET=192.168.1.102
    INTF=enp202s0f0np0
    TARGETC=clnode264.clemson.cloudlab.us
    USER=netian
    TARGETDIR=/users/netian
    ```

1. Run `host_setup.sh` on the Client side, and run `target_setup.sh` in the server side. These script will setup the CPU affinity to NIC's interrupt channel, aRFS, GRO, and other optimization we used in our experiment. Note: You should keep the ssh window open to make sure `phc2sys` alive; we recommend using `tmux`, see [Tmux Cheat Sheet](https://tmuxcheatsheet.com/) for usage.
    ```sh
    # Optional: Use tmux
    tmux new -s setup

    # Client side
    ./host_setup.sh
    # Server side
    ./target_setup.sh
    ```

### Application Modification

Note: Do this on both servers.

Note: While not recommended, if you are using CloudLab r650, you can skip this part.

We enable hyper-threading by default. As shown in the experiment diagram, for a selected physical CPU core, we need to pin application threads to its two logical cores (siblings). With different CPU hardware, siblings number could be different.

We recommend using `lstopo` to check the CPU siblings, as well as choosing the CPU within the same NUMA of NIC. Below shows the example of `lstopo` on r650 server:

<p align="center">
  <img src="image/lstopo.png" width="500
  "/>
</p>

In this example, the NIC we are using is `enp202s0f0np0`, therefore we choose to use the same-NUMA CPUs L#36~L#71. Their logical core are:

```plain
L#36: 1, 73
L#37: 3, 75
...
```

So when we say "single core", it means using the two logical core (e.g., core 1 and core 73) within a physical core (e.g., L#36).

The `cpu_list` in the test application (i.e., in `./application` folder) and `TASKSET` in the test script (i.e., in `scripts` folder) should be changed accordingly. Note they use differnet interleaving format, in this r650 example, they should be:
```c++
cpu_list[32] = {1, 73, 3, 75, 5, 77, 7, 79, ...};
TASKSET="1,73" // Single Core
TASKSET="1,3,5,7,....73,75,77,79,..." // Multiple Cores

```

Note: Please make sure you have also changed the hardcoded CPU core numbers used to filter stashing measurement results in the kernel, as directed in the kernel repo.

### Application and Kernel Module Compilation
Note: You should do this on both servers.

Compile the test application:
```sh
cd ./application && make
```

### Figure 2: the isolated performance for default Linux
1. Reboot to `5.10.46-linux+` (Default Linux) kernel:
    ```sh
    sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.10.46-linux+"
    sudo reboot
    ```

2. (Optional) Adjust the experiment settings (e.g., number of experiment runs) in the experiment runner `experiment/run_fig2_default.py`:
    ```python
    experiment_name = "isolated_thread_default"
    script_name = "single_core_macro_default.sh"
    num_apps = [1]
    flowsize = [64]
    iodepth = [1]
    dim = [0]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

3. Run the experiment runner. We recommend using tmux to avoid progress loss.
    ```shell
    cd ./experiment
    tmux new -s experiment # Optional tmux
    python3 run_fig2_default.py
    ```

Note: Each run of the experiment takes about 5mins of application running and about 1min of data stashing. With 3 runs in this experiment, it takes ~18mins in total.


#### Evaluation and Data Parse
1. **Experiment** results will be located at `/data/projects/latency/isolated_thread_default/` by default. In this experiment, we have 3 runs, 5 mins per run. For example, the result folder should look like:
    ```sh
    netian@node0:/data/projects/latency/isolated_thread_default$ ls
    1_64_1_0_1_1_1_0  1_64_1_0_1_1_1_1  1_64_1_0_1_1_1_2
    ```

1. For each run, the throughput, the latency (average, P50, and P99.9), and the raw latency breakdown timestamps will be recorded in `throughput.log`, `latency.log`, and `latencies-1.log` for client side and `latencies-1-server.log` for server side. For example:
    ```sh
    netian@node0:/data/projects/latency/isolated_thread_default/1_64_1_0_1_1_1_2$ cat throughput.log
    53085.7 # Throughput = 53085.7 IOPS = 0.053 mIOPS
    netian@node0:/data/projects/latency/isolated_thread_default/1_64_1_0_1_1_1_2$ cat latency.log 
    18.1494 23 34 # Average = 18.1494, P50 = 23, P99 = 34
    ```
    Note: the results may vary significantly compared to the results in our paper due to hardware differences.

1. We also record the end-to-end latency distribution for each thread in `netperf-{#thread}_hist.bin`. To obtain the experiment-level P99.9 latency, we merge the latency distributions across all runs before computing the percentile, rather than averaging the P99.9 values from individual runs.

1. To get the average throughput, average latency and P99.9 tail latency (Figure 2-a) for each **experiment**, change the configuration in `parse/parse_single_core_latency_throughput` to the experient results folder:
    ```python
    # Configuration:
    result_dir = "/data/projects/latency"
    # Experiments to parse. Leave empty to parse every experiment found in result_dir.
    experiments = ["isolated_thread_default"]
    ```
    and run the script:
    ```sh
    cd parse && python3 parse_single_core_latency_throughput.py
    ```
    the output should look like:
    ```plain
    netian@node0:~/latency/parse$ python3 parse_single_core_latency_throughput.py 
    # isolated_thread_default
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  mean_lat_us  p999_lat_us  thpt_MIOPS
    --------  --------  -------  ---  ---  -------  -----  ----  -----------  -----------  ----------
        1        64        1    0    1        1      1     3       18.146       34.000     0.05312
    ```

1. To get the heatmap for the **experiment** (Figure 2-b), we first need to run `parse/parse_breakdown_to_heatmap.py` to parse the tail region (P99.8-P100) end-to-end latency as a numpy .npy file. Change the configuration in the `parse/parse_breakdown_to_heatmap.py` as:
    ```python
    result_dir = "/data/projects/latency"
    experiments = ["isolated_thread_default"]
    prefixes = ["1_64_1_0_1_1_1_"]
    ```
    and run the script:
    ```sh
    cd parse && python3 parse_breakdown_to_heatmap.py
    ```
    It may takes ~2mins for processing to finish. After that, we will see the npy file in the experiment folder:
    ```plain
    netian@node0:/data/projects/latency/isolated_thread_default$ ls
    1_64_1_0_1_1_1_0  1_64_1_0_1_1_1_2
    1_64_1_0_1_1_1_1  heatmap_isolated_thread_default_1_64_1_0_1_1_1.npy
    ```
    Then run `parse/draw_heatmap.py` to generate the heatmap:
    ```sh
    python3 draw_heatmap.py \
    /data/projects/latency/isolated_thread_default/heatmap_isolated_thread_default_1_64_1_0_1_1_1.npy \
    -o heatmap_isolated_thread_default.pdf \
    --cap 10
    ```

Note: We are unable to provide the full plotting script for artifact evaluation since that will introduce significant workload for code re-organization; we believe the first priority of artifact evaluation is on the functionality (to produce the data needed for plotting), rather than plotting-level reproducibility. Nevertheless, if you are interested, you can refer to [Github](https://github.com/amefumi/understand_latency/tree/main/analysis) for (partial) scripts we used to analysis the data and plot the figures.


### Figure 3-4: The latency-throughput curve and latency breakdown for Linux, Linux+IRQa, Linux+ACCa, and Linux+PCSched

1. (Optional) Adjust the experiment settings (e.g., number of experiment runs) in the experiment runner `experiment/run_fig3_4_{default,irqa,acca,pcsched}.py`:
    ```python
    experiment_name = ...
    script_name = ...
    num_apps = [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
    flowsize = [64]
    iodepth = [1]
    dim = [0, 1]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

1. Run `experiment/run_fig3_4_default.py` under `5.10.46-linux+` (Default Kernel); 

1. Switch the kernel to `5.10.46-latency+` (assuming its already installed on `/boot`):
    ```sh
    sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.10.46-latency+"
    sudo reboot
    ```
    Note that after each time you reboot the server, you have to repeat the Step 3 in Environment Preparation Section, i.e., the `host_setup.sh` and `target_setup.sh`.

1. Run `experiment/run_fig3_4_irqa.py`, `experiment/run_fig3_4_acca.py`, and `experiment/run_fig3_4_pcsched.py` under `5.10.46-latency+` (Customized Kernel)

Note: This experiment takes significant time. To reduce the waiting time, you can decrease the number of runs, or the time for each run. In r650 server, the knee point is ~36 threads.

#### Evaluation and Data Parse
1. After all four experiments in this part finish, you should see results dir `single_core_macro_default`, `single_core_macro_irqa`, `single_core_macro_acca`, and `single_core_macro_pcsched` in `/data/project/latency` dir.

1. To get the latency-throughput curve (Figure 3), change the configuration in `parse/parse_single_core_latency_throughput` and run it for **each experiment** in this section, as directed before. For example, we need to adjust the parameter for default Linux as:
    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_macro_default"]
    ```
1. Then run the parse script, which will parse the data needed to plot the latency-throughput curve figure:
    ```plain
    netian@node0:~/latency/parse$ python3 parse_single_core_latency_throughput.py 
    # single_core_macro_default
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  mean_lat_us  p999_lat_us  thpt_mIOPS  client_intr  server_intr
    --------  --------  -------  ---  ---  -------  -----  ----  -----------  -----------  ----------  -----------  -----------
        2        64        1    0    1        1      1     3       20.705       37.000     0.09482        90810        86657
        2        64        1    1    1        1      1     3       22.289       48.000     0.08747        86005        83199
        4        64        1    0    1        1      1     3       27.449       49.000     0.14290        75966        75795
        4        64        1    1    1        1      1     3       26.307      103.000     0.14900        75272        79020
        8        64        1    0    1        1      1     3       44.685      320.000     0.17617        70068        67972
        8        64        1    1    1        1      1     3       68.772      169.000     0.11542        66912        72080
        12        64        1    0    1        1      1     3       64.004     2002.000     0.18477        65539        65713
        12        64        1    1    1        1      1     3       94.728      273.000     0.12594        66975        67792
        16        64        1    0    1        1      1     3       85.226     1966.000     0.18633        68603        68811
        16        64        1    1    1        1      1     3      111.530      318.000     0.14275        69496        70319
        20        64        1    0    1        1      1     3      106.889     3239.000     0.18609        65657        67823
        20        64        1    1    1        1      1     3      134.589      292.000     0.14801        65270        64308
        24        64        1    0    1        1      1     3      128.859     3523.000     0.18541        70822        70757
        24        64        1    1    1        1      1     3      104.463     1665.000     0.22820        72952        71279
        28        64        1    0    1        1      1     3      150.203     4317.000     0.18555        68525        72552
        28        64        1    1    1        1      1     3      120.002     2626.000     0.23196        91271        91275
        32        64        1    0    1        1      1     3      172.028     4067.000     0.18538        68513        61198
        32        64        1    1    1        1      1     3      140.060     1558.000     0.22728        71012        70658
        36        64        1    0    1        1      1     3      193.705     4416.000     0.18526        68366        63227
        36        64        1    1    1        1      1     3      151.565     1505.000     0.23656        71850        72083
        40        64        1    0    1        1      1     3      215.587     4660.000     0.18501        84726        86299
        40        64        1    1    1        1      1     3      170.895     2333.000     0.23309        68681        69632
        44        64        1    0    1        1      1     3      237.890     4037.000     0.18446        63981        65018
        44        64        1    1    1        1      1     3      185.738     2325.000     0.23602        66872        66200
    ```

1. To get the heatmap (Figure 4) at the knee point, change the configuration in `parse/parse_breakdown_to_heatmap.py` and run it for **each experiment** on its knee point (this means you should first identify the knee point through step 1, and set the **prefix** to the knee point runs). Then draw the heatmap for each generated npy file, as directed in the Figure 2 experiment:
    ```sh
    python3 draw_heatmap.py \
    /data/projects/latency/single_core_macro_default/heatmap_single_core_macro_default_36_64_1_1_1_1_1.npy \
    -o single_core_macro_default.pdf \
    --cap 1500
    ```

### Figure 5: (Modeled) virtual runtime and packets processed in softIRQ for Linux, Linux+ACCa, and Linux+PCSched

1. Change the number of threads in `experiment/run_fig5_{default,acca,pcsched}.py to the knee point.
    ```python
    experiment_name = "single_core_understand_{default,acca,pcsched}"
    script_name = "single_core_understand_{default,acca,pcsched}.sh"
    num_apps = [36]
    flowsize = [64]
    iodepth = [1]
    dim = [1]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

1. We use kernel modules to probe the virutal runtime of threads (`vruntime_probe`) and the packets handled in softIRQ (`softirq_packets`).

1. In `script/sing_core_understand_{default,acca,pcsched}.sh`, change the monitored CPU logical core of vruntime probe module to the one of the cores we are using (i.e., 73 in r650 case).
    ```sh
    sudo insmod ../modules/vruntime_probe.ko sample_cpu=73 total_count=300 interval_ms=1000
    ```

1. The kernel modules will output to the Kernel Ring Buffer (that you usually check with `dmesg`). We stash the log with `dmesg` in the `script/sing_core_understand_{default,acca,pcsched}.sh` script. If you adjust the experiment time, you will also need to adjust how many lines should be trimmed:
    ```sh
    sudo tail -n 1000  /var/log/kern.log > $DIR/iter_thread_client.log
    ```
    `vruntime_probe` generates 2 lines per second, `softirq_packets` generate 2 lines per 10 seconds, but we recommend adding 30% slack to avoid trimming by other services.

1. In `modules/softirq_packets.c`, change the monitored CPU logical core of packets processed in softIRQ probe module to the one of the cores we are using (i.e., 73 in r650 case). Note that in the server side, you need to first uncommet the `COUNTING_SERVER_SIDE` for the netfilter to match the correct IP:
    ```c
    #define FILTER_OUTPUT_CPUS(x) (x == 1 || x == 73)
    #define FILTER_PRINT_CPUS(x) (x == 73)
    // #define COUNTING_SERVER_SIDE // <- Uncomment this line in server (target) side
    ```

1. Re-compile the modules on both side **each time you changed the kernel**, or there will be compatibility issue:
    ```sh
    cd modules && make
    ```

1. Swithc the kernel to `5.10.46-linux+` (default Linux) on both side. Run the experiment:
    ```sh
    python3 run_fig5_default.py
    ```

1. Switch the kernel to `5.10.46-latency+` (customized Linux) on both side. Run the experiment for ACCa and PCSched:
    ```sh
    python3 run_fig5_acca.py
    python3 run_fig5_pcsched.py
    ```

#### Evaluation and Data Parse

1. Change the configurations in `parse/parse_understand_default.py` to the experiment result dir (one run specific) of default Linux:
    ```python
    result_dir = "/data/projects/latency/"
    experiment = "single_core_understand_default/36_64_1_1_1_1_1_0"
    n_thread = 36
    ```

2. Run the `parse/parse_understand_default.py`. You will get the P99.9 tail latency, virtual runtime, and number of packets processed in softIRQ for both client and server side of a connection (thread).

3. Repeat step 1 and 2 for `parse/parse_understand_acca.py` and `parse/parse_understand_pcsched.py` for Linux + ACCa (P99.9 tail latency, virtual runtime, modeled virtual runtime, and #packets in softIRQ), and Linux + PCSched (P99.9 tail latency, #packets in softIRQ)


### Figure 7: Processing Time vs Stall Cycles for Linux+ACCa

1. We use Intel CPU as example. Check the CPU model name:
    ```sh
    lscpu |grep "Model name"
    ```

1. Check the CPU model's "Code Name" (family) in Intel's manual. For example, r650 server has "Intel(R) Xeon(R) Platinum 8360Y" CPU, whose family is "Ice Lake"

1. Check the performance monitoring event for the CPU family at [PerfMon Events Documentation](https://perfmon-events.intel.com/)

1. Change the event code for `CYCLE_ACTIVITY.STALLS_TOTAL` and `CYCLE_ACTIVITY.STALLS_L1D_MISS` in `modules/program_pmu.c` to the codes in the documentation since it may vary across different families:
    ```c
    static const struct counter_cfg counters[NUM_COUNTERS] = {
        { "CYCLE_ACTIVITY.STALLS_TOTAL",
            EVT(0xA3, 0x04), 0, false, 0, 0, 0x04 },
        { "CYCLE_ACTIVITY.STALLS_L1D_MISS",
            EVT(0xA3, 0x0C), 1, false, 0, 0, 0x0C },
    };
    ```

1. Switch the kernel to `5.10.46-latency+` (our customized kernel)
1. Compile the `program_pmu` module on the client side. You should re-compile the module **every time you change the kernel**:
    ```sh
    cd modules && make
    ```

1. Disable NMI watchdog on the client side before installing the module to avoid performance monitor counter overlap; you should also not use Linux perf during this experiment:
    ```sh
    echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog
    ```

1. Install the `program_pmu` module in the client side:
    ```sh
    cd modules
    sudo rmmod program_pmu
    sudo insmod program_pmu.ko cpus=1,73
    ```

1. (Optional) Adjust the experiment settings (e.g., number of experiment runs) in the experiment runner `experiment/run_fig7_acca.py`:
    ```python
    experiment_name = "single_core_rdpmc_acca"
    script_name = "single_core_rdpmc_acca.sh"
    num_apps = [32, 34, 36, 38, 40]
    flowsize = [64]
    iodepth = [1]
    dim = [1]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

1. Run `experiment/run_fig7_acca.py` under `5.10.46-latency+` (customized kernel)

#### Evaluation and Data Parse
1. After the experiments finishes, you should see result dir `single_core_rdpmc_acca` in `/data/project/latency` dir. Select one run from the dir and change the configuration in `parse/parse_rdpmc_acca.py`:
    ```python
    result_dir = "/data/projects/latency/"
    experiment = "single_core_rdpmc_acca/36_64_1_1_1_1_1_0"
    n_thread = 36
    ```

1. Run the `parse/parse_rdpmc_acca.py`. The output should look like below. `{cli,srv}_time` is the client/server-side processing time, `{cli,srv}_stall` is the stall cycles, and `{cli,srv}_stall_l1d` is the stall cycles when there is at least one outstanding L1d miss. Note only half of the ports belong the same logical core, and the remaining half belongs to its sibling logical core.
    ```plain
    netian@node0:~/latency/parse$ python3 parse_rdpmc_acca.py 
    port  cli_time  cli_stall  cli_stall_l1d  srv_time  srv_stall  srv_stall_l1d
    -----------------------------------------------------------------------------
    10000    1995.0     2814.0          374.7    1868.2     2573.9          354.3
    10001    1988.9     2807.6          408.2    1859.5     2539.8          298.8
    10002    1983.2     2782.0          383.3    1859.6     2546.1          331.4
    10003    2005.1     2855.9          466.6    1877.2     2594.7          316.1
    10004    1977.9     2773.6          394.0    1868.2     2564.0          296.9
    10005    2002.9     2845.6          447.0    1868.2     2568.1          311.8
    10006    1977.5     2767.3          374.7    1851.0     2517.8          305.0
    10007    1982.9     2784.7          378.7    1863.4     2553.0          304.6
    10008    1982.2     2776.9          376.7    1865.9     2566.3          345.6
    10009    1989.3     2801.9          401.9    1865.6     2557.4          320.8
    10010    2008.6     2866.1          489.6    1870.0     2568.9          290.2
    10011    1985.4     2791.0          415.3    1872.6     2577.1          299.4
    10012    1987.6     2806.2          426.5    1878.3     2598.5          349.1
    10013    1983.2     2788.1          382.8    1888.0     2624.5          372.0
    10014    2000.6     2846.7          471.4    1873.7     2582.3          294.7
    10015    1989.2     2802.3          389.3    1867.4     2563.6          350.4
    10016    1981.1     2785.6          419.7    1871.6     2573.8          305.2
    10017    1984.5     2785.0          360.1    1869.5     2573.5          396.9
    10018    1979.8     2781.0          386.1    1848.1     2529.6          286.8
    10019    2007.3     2870.8          498.4    1864.0     2564.2          300.0
    10020    1982.7     2797.9          424.9    1855.6     2542.0          297.3
    10021    1986.4     2805.5          379.7    1857.4     2557.4          347.4
    10022    1985.5     2798.4          370.5    1840.2     2513.7          302.3
    10023    1971.1     2755.6          356.8    1831.8     2483.2          310.4
    10024    1974.2     2766.1          372.4    1855.1     2552.2          339.1
    10025    1962.7     2731.8          359.1    1855.3     2544.3          309.2
    10026    1980.5     2785.9          380.6    1836.9     2500.4          293.5
    10027    1982.0     2792.6          415.6    1858.2     2549.9          296.6
    10028    1972.6     2759.0          374.4    1848.0     2526.4          288.2
    10029    1980.7     2786.2          410.8    1856.2     2542.5          331.8
    10030    1989.2     2817.4          455.8    1870.4     2581.5          287.0
    10031    1971.4     2759.4          369.3    1848.0     2524.7          282.4
    10032    1988.9     2812.7          419.8    1868.2     2587.3          362.9
    10033    1970.3     2759.2          383.2    1857.8     2549.1          305.2
    10034    1981.6     2793.5          440.3    1861.3     2559.7          302.8
    10035    1979.0     2784.1          382.3    1849.5     2527.5          326.0
    [STATS] client: 36 threads, processing time 1962.7 .. 2008.6 ns, gap 45.9 ns
    [STATS] server: 36 threads, processing time 1831.8 .. 1888.0 ns, gap 56.3 ns
    ```

### Figure 8a-8b: Latency breakdown at certain point and 
1. You should be able to get the latency breakdown heatmap and the number of interrupt in both server and client side (`server_intr` and `client_intr`) at any point by performing the steps in Figure 3-4 part.

### Figure 8c: The latency-throughput curve for AutoDIM

Important: as we state in our paper, the AutoDIM sets "the minimum packet threshold and the maximum timeout before triggering an interrupt (i.e., `rx_frames` and `rx_usecs`) to half of the total in-flight packets across threads on a single logical core and the corresponding total processing time." However, different hardware configuration leads to different processing time, thus different hyper-parameter (i.e., average processing time per-packet). We leave this hyper-parameter tuning to the exerciser.

1. (Optional) Adjust the experiment settings (e.g., number of experiment runs) in the experiment runner `experiment/run_fig8c_autodim.py`:
    ```python
    experiment_name = "single_core_macro_autodim"
    script_name = "single_core_macro_psched.sh"
    num_apps = [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
    flowsize = [64]
    iodepth = [1]
    dim = [2]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

1. Run `experiment/run_fig8c_autodim.py` under `5.10.46-latency+` (customized kernel)

#### Evaluation and Data Parse
1. After all four experiments in this part finish, you should see result dir `single_core_macro_autodim` in `/data/project/latency` dir.

1. Parse the experiment with directions in Figure 3-4 part.

### Figure 9-10: Latency-throughput curve with increasing in-flight requests
1. (Optional) Adjust the experiment settings (e.g., number of experiment runs) in the experiment runner `experiment/run_fig9_10_{default,acca,pcsched}.py`.

1. Run `experiment/run_fig9_10_default.py` under `5.10.46-linux+` (default Linux).

1. Run `experiment/run_fig9_10_acca.py` and `experiment/run_fig9_10_pcsched.py` under `5.10.46-latency+` (customized kernel).

### Evaluation and Data Parse

1. The experiment results will be located at `single_core_iodepth_default`, `single_core_iodepth_acca`, and `single_core_iodepth_pcshed` folder in `/data/projects/latency`.

1. You should be able to get the latency-throughput curve data by running the script in Figure 3-4 part---Just rememeber to change the configurations.

1. As we mentioned in our paper, due to batching, we are only able to measure the `rx_sched` latency when there are multiple in-flight requests per connection. Change the configuration of `parse/parse_iodepth_rxsched.py`:
    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_iodepth_acca"]
    ```

1. Run `parse/parse_iodepth_rxsched.py`, the script will output the client-side and server-side P99.9 `rx_sched` latency. For example, for Linux + ACCa, the results may look like:
    ```plain
    netian@node0:~/latency/parse$ python3 parse_iodepth_rxsched.py 
    # single_core_iodepth_acca
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  client_samples  server_samples  client_p999  server_p999
    --------  --------  -------  ---  ---  -------  -----  ----  --------------  --------------  -----------  -----------
        2        64       32    1    1        1      1     3        24739133        24739139        76178        48594
    ......
    ```

### Figure 11: CDF for the number of requests per segment

1. The CDF data is shipped-in with the Figure 9-10 experiments, we just need to parse the data!

#### Evaluation and Data Parse

1. Change the configurations in `parse/parse_iodepth_segments.py` to the interested experiments and runs prefix:
    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_iodepth_acca"]
    prefixes = ["2_64_32_1_1_1_1_"]
    ```

1. Run the `parse/parse_iodepth_segments.py`. The first column is the number of requests per segment, and the second is the CDF to the number. For example:
    ```plain
    netian@node0:~/latency/parse$ python3 parse_iodepth_segments.py 
    ## single_core_iodepth_acca/2_64_32_1_1_1_1 (2 run(s))
    # client: 67463583 samples
    0 0.0
    1 0.003293910434611811
    2 0.010197249677652016
    3 0.0319743616344836
    4 0.06776414469418264
    5 0.14515177766351367
    6 0.37522356320742706
    7 0.7046617135647836
    8 0.8923228106636435
    9 0.9842263788450133
    10 0.9955283726925681
    ......
    ```

### Figure 12: Latency-throughput curve and latency breakdown with multiple CPU cores

TODO: multiple core helper scripts

TODO: scripts

### Figure 13:  Latency-throughput curve with increasing in-flight requests under multiple cores

TODO: parse

### Figure 16: EEVDF Performance

1. Download Linux 6.12.12 kernel from [Linux](https://kernel.org)
    ```sh
    cd ~
    wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.12.12.tar.xz
    TODO: complete the shell snippet
    ```

TODO: add EEVDF patch

TODO: EEVDF macro script

TODO: EEVDF understand script and parse

### Figure 14-15, 17: Supplementary experiment

The experiments above have well support our key insights in our paper:
1. Scheduling dominates the high tail latency
2. Runtime may not be the idea scheduling abstraction for low latency
3. Traffic predictability can make interrupt tuning more effective
4. Choose your parallelism carefully.

The experiments for Figure 14 to Figure 17 are **supplementary** experiments to our paper. **We will update the experiment set for these experiment when time availiable.**

However, if you are interested, you can check the following section for our unorganized codebase ([Link](https://github.com/amefumi/understand_latency)) to find the application and scripts for running these experiments. For example, Figure 14 can be done by setting the `flowsize` in the Figure 3-4 part experiment; Figure 16 can be done by changing the test application; and Figure 17 can be done by refering the Redis experiment in [NetChannel](https://github.com/Terabit-Ethernet/NetChannel).


## Acknowledgement
[Tianyu](https://netian.me) is the current maintainer for this project. Please contact him if you have any issue: zuotianyu@virginia.edu

Codex and Claude Code are used to polish this document and re-organize the experiment scripts.

If you find this work useful, please cite:
```plain
@inproceedings{UnderstandLatencyUVA,
  title={Understanding Host Network Stack Latency},
  author={Zuo, Tianyu and Hwang, Jaehyun and Tang, Ao and Agarwal, Rachit and Cai, Qizhe},
  booktitle={Proceedings of the ACM SIGCOMM 2026 Conference},
  pages={1127--1140},
  year={2026}
}
```