# Understanding Host Network Stack Latency — Experiment Set

Experiment set for our SIGCOMM 2026 paper, *"Understanding Host Network Stack Latency"*.

## Table of Contents

- [Prelude](#prelude)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Kernel Installation](#kernel-installation)
- [Repository Layout](#repository-layout)
- [Artifact Evaluation Guide](#artifact-evaluation-guide)
  - [(Optional) CloudLab Setup](#optional-cloudlab-setup)
  - [Experiment Diagram](#experiment-diagram)
  - [Kernel Preparation](#kernel-preparation)
  - [Environment Preparation](#environment-preparation)
  - [Application Modification](#application-modification)
  - [Application and Kernel Module Compilation](#application-and-kernel-module-compilation)
  - [Figure 2: Isolated performance of default Linux](#figure-2-isolated-performance-of-default-linux)
  - [Figure 3-4: Latency-throughput curve and latency breakdown](#figure-3-4-latency-throughput-curve-and-latency-breakdown)
  - [Figure 5: Virtual runtime and softIRQ packet counts](#figure-5-virtual-runtime-and-softirq-packet-counts)
  - [Figure 7: Processing time and stall cycles for Linux with ACCa](#figure-7-processing-time-and-stall-cycles-for-linux-with-acca)
  - [Figure 8a-8b: Latency breakdown and interrupt counts](#figure-8a-8b-latency-breakdown-and-interrupt-counts)
  - [Figure 8c: Latency-throughput curve for AutoDIM](#figure-8c-latency-throughput-curve-for-autodim)
  - [Figure 9-11: Latency-throughput curve with increasing in-flight requests](#figure-9-11-latency-throughput-curve-with-increasing-in-flight-requests)
  - [Figure 12: Latency-throughput curve and breakdown with multiple CPU cores](#figure-12-latency-throughput-curve-and-breakdown-with-multiple-cpu-cores)
  - [Figure 13: In-flight requests with multiple CPU cores](#figure-13-in-flight-requests-with-multiple-cpu-cores)
  - [Figure 16: EEVDF performance](#figure-16-eevdf-performance)
  - [Figure 14-15, 17: Supplementary experiments](#figure-14-15-17-supplementary-experiments)
- [Acknowledgement](#acknowledgement)

## Prelude

> [!NOTE]
> This experiment set is not essential to understand Linux network stack latency. With our [customized Linux kernel](https://github.com/Terabit-Ethernet/linux-latency) you should be able to run the latency analysis on any workload you like; this experiment set only serves as a reference point.

> [!NOTE]
> We provide the essential data analysis tools in the `parse` folder **as reference**. It is extremely difficult for us to provide end-to-end (figure-level) analysis tools, since experiment results vary across hardware configurations.

## Hardware Requirements

There are two hard requirements:

1. You must use an x86-64 CPU if you want to use our PMU programming module. You will also have to change the PMU event codes if you are using a non-Intel CPU.
2. You must use a Mellanox NIC, since we rely on `mlx5e` driver instrumentation to report the recorded timestamps through the ftrace framework.

We used the following hardware and software configuration to run the experiments:

| Component | Configuration |
| --- | --- |
| CPU | 2-socket Intel Xeon Gold 6530 |
| RAM | 1024 GB |
| NIC | Mellanox ConnectX-7 (400 Gbps) |
| Distro | Ubuntu 22.04 |
| Toolchain | gcc/g++ 11.4.0, GNU Make 4.3 |

## Software Requirements

> [!IMPORTANT]
> You must uninstall every active OFED NIC driver on your system, since we rely on the kernel's in-tree `mlx5e` driver to report the recorded timestamps when the packet is finally injected onto the link. See [NVIDIA's documentation](https://networking-docs.nvidia.com/mlnxofedswum/24.10-5.1.6.1lts/uninstalling-the-driver) for how to uninstall OFED drivers.

Install the essential software:

- `hwstamp_ctl` and `phc2sys` (from `linuxptp`) — sync time between CPU and NIC, and read the NIC hardware timestamp.
- `sar` (from `sysstat`) — CPU utilization monitoring.
- `trace-cmd` — resetting the ftrace buffer.

```sh
sudo apt update
sudo apt install linuxptp sysstat trace-cmd
```

The experiments require `numpy` for data processing and `matplotlib` for the essential plotting:

```sh
wget https://bootstrap.pypa.io/get-pip.py
python3 get-pip.py
python3 -m pip install numpy
python3 -m pip install matplotlib
```

## Kernel Installation

Please refer to https://github.com/Terabit-Ethernet/linux-latency for kernel installation. In this document we explicitly state which kernel is required for each set of experiments.

> [!NOTE]
> We recommend keeping a separate clone per kernel version: compiling a kernel can be very slow, and we need to switch between kernels frequently.

> [!IMPORTANT]
> You **must** build separate kernel images for each machine. The latency monitor is keyed to the host's own IP address, which is hardcoded at compile time.

We assume two kernels: a default one (e.g., `5.10.46-default`) and one for IRQa, ACCa, and PCSched (e.g., `5.10.46-latency`), which are selected through runtime parameters.

## Repository Layout

| Path | Contents |
| --- | --- |
| `application/` | The test client and server applications (single-core and multi-core variants). |
| `experiment/` | Per-figure experiment runners (`run_fig*.py`). Start here. |
| `scripts/` | The experiment scripts that each runner invokes. |
| `modules/` | Kernel modules: `vruntime_probe`, `softirq_packets`, `program_pmu`, `packet_dist`. |
| `parse/` | Data analysis scripts (`parse_*.py`) and `draw_heatmap.py`. |
| `affinity_tool/` | Helper for setting IRQ/thread CPU affinity. |
| `env.sh` | Per-testbed settings (IPs, interface, remote host) sourced by the scripts. |
| `host_setup.sh`, `target_setup.sh` | Client-side and server-side machine setup. |
| `linux-6.12-latency.patch` | ACCa and PCSched patch for the Linux 6.12.66 (EEVDF) kernel. |

## Artifact Evaluation Guide

> [!IMPORTANT]
> The experimental results from artifact evaluation may look different from those in our paper due to hardware differences. To fully reproduce the paper's results we recommend using exactly the same hardware (CPU, RAM, and NIC). That said, due to potential export control and policy issues, we may only be able to provide access to our own servers upon request.

### (Optional) CloudLab Setup

To facilitate artifact evaluation, we recommend the [**r650**](https://docs.cloudlab.us/hardware.html#(part._cloudlab-clemson)) server type from CloudLab. The experiment scripts and settings in this section are based on the r650 server.

> [!IMPORTANT]
> Different servers differ in — most importantly — their CPU sibling mapping. If you run the experiments on another server type, make sure to prepare the applications correctly by following the instructions below.

The experiments generate a significant amount of data. In this guide we mount the `nvme0n1` NVMe device at `/data` to store all experiment output; we omit the NVMe mount setup steps (ChatGPT should help!). If you use a different environment, change the output directory in the experiment scripts.

### Experiment Diagram

<p align="center">
  <img src="image/latency_diagram.png" width="500"/>
</p>

The diagram shows the CPU layout, NIC interface, and IP addresses used in this evaluation guide, based on r650 machines.

### Kernel Preparation

> [!NOTE]
> Do this on both servers, with potentially different hardcoded parameters.

Assuming you have installed the kernel and drivers as instructed above, you should have two kernels in `/boot`:

1. `5.10.46-linux+` — the default Linux kernel, with the IRQ time accounting option disabled.
2. `5.10.46-latency+` — the experimental Linux kernel with IRQ time accounting; our designs (ACCa and PCSched) are enabled through runtime parameters.

### Environment Preparation

> [!NOTE]
> Do this on both servers, with potentially different scripts.

1. Clone the project into `latency` under the user's folder (e.g., `/users/netian` on an r650 server):

    ```sh
    cd ~
    git clone https://github.com/Terabit-Ethernet/understand_latency.git latency
    ```

2. Update `env.sh` with the correct physical settings. On the r650 server, `env.sh` should look like the following. `TARGETC` is the remote SSH host, `USER` is the SSH user name on the remote server, and `TARGETDIR` is the user folder where the `latency` project lives on the remote server. We assume `INTF` is the same on both sides; if not, set them independently.

    ```sh
    HOST=192.168.1.101
    TARGET=192.168.1.102
    INTF=enp202s0f0np0
    TARGETC=clnode264.clemson.cloudlab.us
    USER=netian
    TARGETDIR=/users/netian
    ```

3. Run `host_setup.sh` on the client side and `target_setup.sh` on the server side. These scripts set up the CPU affinity for the NIC interrupt channels, aRFS, GRO, and the other optimizations we used in our experiments.

    ```sh
    # Optional: use tmux
    tmux new -s setup

    # Client side
    ./host_setup.sh
    # Server side
    ./target_setup.sh
    ```

    > [!NOTE]
    > Keep the SSH window open so that `phc2sys` stays alive. We recommend using `tmux`; see the [Tmux Cheat Sheet](https://tmuxcheatsheet.com/) for usage.

### Application Modification

> [!NOTE]
> Do this on both servers. While not recommended, you can skip this part if you are using CloudLab r650.

We enable hyper-threading by default. As shown in the experiment diagram, for a selected physical CPU core we pin application threads to its two logical cores (siblings). The sibling numbering differs across CPU hardware.

We recommend using `lstopo` to check the CPU siblings, and to choose CPUs on the same NUMA node as the NIC. Below is an example of `lstopo` output on an r650 server:

<p align="center">
  <img src="image/lstopo.png" width="500"/>
</p>

In this example the NIC is `enp202s0f0np0`, so we use the same-NUMA CPUs L#36–L#71. Their logical cores are:

```plain
L#36: 1, 73
L#37: 3, 75
...
```

So when we say "single core", we mean the two logical cores (e.g., core 1 and core 73) of one physical core (e.g., L#36).

`cpu_list` in the test application (in `application/`) and `TASKSET` in the test scripts (in `scripts/`) must be changed accordingly. Note that they use different interleaving formats; in this r650 example they would be:

```c++
cpu_list[32] = {1, 73, 3, 75, 5, 77, 7, 79, ...};
TASKSET="1,73"                                  // Single core
TASKSET="1,3,5,7,....73,75,77,79,..."           // Multiple cores
```

> [!IMPORTANT]
> Make sure you have also changed the hardcoded CPU core numbers used to filter stashing measurement results in the kernel, as directed in the kernel repo.

### Application and Kernel Module Compilation

> [!NOTE]
> Do this on both servers.

Compile the test application:

```sh
cd application && make -j$(nproc)
```

### Figure 2: Isolated performance of default Linux

1. Reboot into the `5.10.46-linux+` (default Linux) kernel:

    ```sh
    sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.10.46-linux+"
    sudo reboot
    ```

2. (Optional) Adjust the experiment settings (e.g., the number of runs) in the experiment runner `experiment/run_fig2_default.py`:

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

3. Run the experiment runner. We recommend using tmux to avoid losing progress.

    ```sh
    cd experiment
    tmux new -s experiment   # Optional
    python3 run_fig2_default.py
    ```

> [!NOTE]
> Each run takes about 5 minutes of application runtime plus about 1 minute of data stashing. With 3 runs, this experiment takes ~18 minutes in total.

#### Evaluation and Data Parse

1. **Experiment** results are located at `/data/projects/latency/isolated_thread_default/` by default. This experiment has 3 runs of 5 minutes each, so the result folder should look like:

    ```sh
    netian@node0:/data/projects/latency/isolated_thread_default$ ls
    1_64_1_0_1_1_1_0  1_64_1_0_1_1_1_1  1_64_1_0_1_1_1_2
    ```

2. For each run, the throughput, the latency (average, P50, and P99.9), and the raw latency breakdown timestamps are recorded in `throughput.log`, `latency.log`, and `latencies-1.log` (client side) / `latencies-1-server.log` (server side). For example:

    ```sh
    netian@node0:/data/projects/latency/isolated_thread_default/1_64_1_0_1_1_1_2$ cat throughput.log
    53085.7 # Throughput = 53085.7 IOPS = 0.053 mIOPS
    netian@node0:/data/projects/latency/isolated_thread_default/1_64_1_0_1_1_1_2$ cat latency.log
    18.1494 23 34 # Average = 18.1494, P50 = 23, P99 = 34
    ```

    > [!NOTE]
    > The results may vary significantly from those in our paper due to hardware differences.

3. We also record the end-to-end latency distribution for each thread in `netperf-{#thread}_hist.bin`. To obtain the experiment-level P99.9 latency we merge the latency distributions across all runs before computing the percentile, rather than averaging the per-run P99.9 values.

4. To get the average throughput, average latency, and P99.9 tail latency (Figure 2a) for each **experiment**, point `parse/parse_single_core_latency_throughput.py` at the experiment results folder:

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

    The output should look like:

    ```plain
    netian@node0:~/latency/parse$ python3 parse_single_core_latency_throughput.py
    # isolated_thread_default
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  mean_lat_us  p999_lat_us  thpt_MIOPS
    --------  --------  -------  ---  ---  -------  -----  ----  -----------  -----------  ----------
        1        64        1    0    1        1      1     3       18.146       34.000     0.05312
    ```

5. To get the heatmap for the **experiment** (Figure 2b), first run `parse/parse_breakdown_to_heatmap.py` to parse the tail region (P99.8–P100) end-to-end latency into a NumPy `.npy` file. Set the configuration in `parse/parse_breakdown_to_heatmap.py` to:

    ```python
    result_dir = "/data/projects/latency"
    experiments = ["isolated_thread_default"]
    prefixes = ["1_64_1_0_1_1_1_"]
    ```

    and run the script:

    ```sh
    cd parse && python3 parse_breakdown_to_heatmap.py
    ```

    Processing may take ~2 minutes. Afterwards you will see the `.npy` file in the experiment folder:

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

> [!NOTE]
> We are unable to provide the full plotting scripts for artifact evaluation, since that would require significant code reorganization; we believe the first priority of artifact evaluation is functionality (producing the data needed for plotting) rather than plotting-level reproducibility. Nevertheless, if you are interested, you can refer to [GitHub](https://github.com/amefumi/understand_latency/tree/main/analysis) for the (partial) scripts we used to analyze the data and plot the figures.

### Figure 3-4: Latency-throughput curve and latency breakdown

Latency-throughput curve and latency breakdown for Linux, Linux+IRQa, Linux+ACCa, and Linux+PCSched.

1. (Optional) Adjust the experiment settings (e.g., the number of runs) in the experiment runners `experiment/run_fig3_4_{default,irqa,acca,pcsched}.py`:

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

2. Run `experiment/run_fig3_4_default.py` under `5.10.46-linux+` (default kernel).

3. Switch to the `5.10.46-latency+` kernel (assuming it is already installed in `/boot`):

    ```sh
    sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.10.46-latency+"
    sudo reboot
    ```

    > [!IMPORTANT]
    > After every reboot you must repeat step 3 of [Environment Preparation](#environment-preparation), i.e., run `host_setup.sh` and `target_setup.sh` again.

4. Run `experiment/run_fig3_4_irqa.py`, `experiment/run_fig3_4_acca.py`, and `experiment/run_fig3_4_pcsched.py` under `5.10.46-latency+` (customized kernel).

> [!NOTE]
> This experiment takes a significant amount of time. To reduce the waiting time you can decrease the number of runs or the duration of each run. On the r650 server, the knee point is at ~36 threads.

#### Evaluation and Data Parse

1. After all four experiments in this part finish, you should see the result directories `single_core_macro_default`, `single_core_macro_irqa`, `single_core_macro_acca`, and `single_core_macro_pcsched` under `/data/projects/latency`.

2. To get the latency-throughput curve (Figure 3), change the configuration in `parse/parse_single_core_latency_throughput.py` and run it for **each experiment** in this section, as described above. For example, for default Linux:

    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_macro_default"]
    ```

3. Then run the parse script, which produces the data needed to plot the latency-throughput curve:

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

4. To get the heatmap (Figure 4) at the knee point, change the configuration in `parse/parse_breakdown_to_heatmap.py` and run it for **each experiment** at its knee point. (This means you should first identify the knee point in step 3, then set **`prefixes`** to the knee-point runs.) Then draw the heatmap for each generated `.npy` file, as described in the Figure 2 experiment:

    ```sh
    python3 draw_heatmap.py \
      /data/projects/latency/single_core_macro_default/heatmap_single_core_macro_default_36_64_1_1_1_1_1.npy \
      -o single_core_macro_default.pdf \
      --cap 1500
    ```

### Figure 5: Virtual runtime and softIRQ packet counts

(Modeled) virtual runtime and packets processed in softIRQ for Linux, Linux+ACCa, and Linux+PCSched.

We use kernel modules to probe the virtual runtime of threads (`vruntime_probe`) and the packets handled in softIRQ (`softirq_packets`).

1. Change the number of threads in `experiment/run_fig5_{default,acca,pcsched}.py` to the knee point:

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

2. In `scripts/single_core_understand_{default,acca,pcsched}.sh`, change the CPU logical core monitored by the vruntime probe module to one of the cores you are using (i.e., 73 in the r650 case):

    ```sh
    sudo insmod ../modules/vruntime_probe.ko sample_cpu=73 total_count=300 interval_ms=1000
    ```

3. The kernel modules write to the kernel ring buffer (the one you normally read with `dmesg`). We stash the log in `scripts/single_core_understand_{default,acca,pcsched}.sh`. If you adjust the experiment duration, you also need to adjust how many lines are trimmed:

    ```sh
    sudo tail -n 1000 /var/log/kern.log > $DIR/iter_thread_client.log
    ```

    `vruntime_probe` generates 2 lines per second and `softirq_packets` generates 2 lines per 10 seconds, but we recommend adding 30% slack to avoid trimming caused by other services.

4. In `modules/softirq_packets.c`, change the CPU logical core monitored by the softIRQ packet probe module to one of the cores you are using (i.e., 73 in the r650 case).

    ```c
    #define FILTER_OUTPUT_CPUS(x) (x == 1 || x == 73)
    #define FILTER_PRINT_CPUS(x) (x == 73)
    // #define COUNTING_SERVER_SIDE // <- Uncomment this line on the server (target) side
    ```

    > [!IMPORTANT]
    > On the server side you must first uncomment `COUNTING_SERVER_SIDE` so that the netfilter hook matches the correct IP.

5. Recompile the modules on both sides **every time you change the kernel**, otherwise you will hit compatibility issues:

    ```sh
    cd modules && make
    ```

6. Switch to the `5.10.46-linux+` (default Linux) kernel on both sides and run the experiment:

    ```sh
    python3 run_fig5_default.py
    ```

7. Switch to the `5.10.46-latency+` (customized Linux) kernel on both sides and run the experiments for ACCa and PCSched:

    ```sh
    python3 run_fig5_acca.py
    python3 run_fig5_pcsched.py
    ```

#### Evaluation and Data Parse

1. Change the configuration in `parse/parse_understand_default.py` to the experiment result directory (specific to one run) of default Linux:

    ```python
    result_dir = "/data/projects/latency/"
    experiment = "single_core_understand_default/36_64_1_1_1_1_1_0"
    n_thread = 36
    ```

2. Run `parse/parse_understand_default.py`. You will get the P99.9 tail latency, virtual runtime, and number of packets processed in softIRQ for both the client and server side of a connection (thread).

3. Repeat steps 1 and 2 with `parse/parse_understand_acca.py` for Linux+ACCa (P99.9 tail latency, virtual runtime, modeled virtual runtime, and number of packets in softIRQ) and `parse/parse_understand_pcsched.py` for Linux+PCSched (P99.9 tail latency and number of packets in softIRQ).

### Figure 7: Processing time and stall cycles for Linux with ACCa

1. We use an Intel CPU as the example. Check the CPU model name:

    ```sh
    lscpu | grep "Model name"
    ```

2. Look up the CPU model's code name (family) in Intel's manual. For example, the r650 server has an "Intel(R) Xeon(R) Platinum 8360Y" CPU, whose family is "Ice Lake".

3. Look up the performance monitoring events for that CPU family in the [PerfMon Events Documentation](https://perfmon-events.intel.com/).

4. Change the event codes for `CYCLE_ACTIVITY.STALLS_TOTAL` and `CYCLE_ACTIVITY.STALLS_L1D_MISS` in `modules/program_pmu.c` to the codes from the documentation, since they vary across families:

    ```c
    static const struct counter_cfg counters[NUM_COUNTERS] = {
        { "CYCLE_ACTIVITY.STALLS_TOTAL",
            EVT(0xA3, 0x04), 0, false, 0, 0, 0x04 },
        { "CYCLE_ACTIVITY.STALLS_L1D_MISS",
            EVT(0xA3, 0x0C), 1, false, 0, 0, 0x0C },
    };
    ```

5. Switch to the `5.10.46-latency+` (customized) kernel.

6. Compile the `program_pmu` module on the client side. You must recompile the module **every time you change the kernel**:

    ```sh
    cd modules && make
    ```

7. Disable the NMI watchdog on the client side before installing the module, to avoid performance monitoring counter overlap. You should also not use Linux `perf` during this experiment:

    ```sh
    echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog
    ```

8. Install the `program_pmu` module on the client side:

    ```sh
    cd modules
    sudo rmmod program_pmu
    sudo insmod program_pmu.ko cpus=1,73
    ```

9. (Optional) Adjust the experiment settings (e.g., the number of runs) in the experiment runner `experiment/run_fig7_acca.py`:

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

10. Run `experiment/run_fig7_acca.py` under `5.10.46-latency+` (customized kernel).

#### Evaluation and Data Parse

1. After the experiment finishes you should see the result directory `single_core_rdpmc_acca` under `/data/projects/latency`. Select one run from the directory and change the configuration in `parse/parse_rdpmc_acca.py`:

    ```python
    result_dir = "/data/projects/latency/"
    experiment = "single_core_rdpmc_acca/36_64_1_1_1_1_1_0"
    n_thread = 36
    ```

2. Run `parse/parse_rdpmc_acca.py`. The output should look like the block below. `{cli,srv}_time` is the client/server-side processing time, `{cli,srv}_stall` is the stall cycles, and `{cli,srv}_stall_l1d` is the stall cycles during which at least one L1d miss is outstanding.

    > [!NOTE]
    > Only half of the ports belong to the same logical core; the remaining half belong to its sibling logical core.

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

### Figure 8a-8b: Latency breakdown and interrupt counts

You can obtain the latency breakdown heatmap and the number of interrupts on both the server and client side (`server_intr` and `client_intr`) at any load point by following the steps in the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) part.

### Figure 8c: Latency-throughput curve for AutoDIM

> [!IMPORTANT]
> As stated in our paper, AutoDIM sets "the minimum packet threshold and the maximum timeout before triggering an interrupt (i.e., `rx_frames` and `rx_usecs`) to half of the total in-flight packets across threads on a single logical core and the corresponding total processing time." Different hardware configurations lead to different processing times, and therefore to a different hyper-parameter (i.e., the average per-packet processing time). We leave this hyper-parameter tuning to the exerciser.

1. (Optional) Adjust the experiment settings (e.g., the number of runs) in the experiment runner `experiment/run_fig8c_autodim.py`:

    ```python
    experiment_name = "single_core_macro_autodim"
    script_name = "single_core_macro_pcsched.sh"
    num_apps = [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
    flowsize = [64]
    iodepth = [1]
    dim = [2]
    pin = [1]
    permute = [1]
    cores = [1]
    runs = [0, 1, 2]
    ```

2. Run `experiment/run_fig8c_autodim.py` under `5.10.46-latency+` (customized kernel).

#### Evaluation and Data Parse

1. After the experiment finishes you should see the result directory `single_core_macro_autodim` under `/data/projects/latency`.

2. Parse the experiment following the directions in the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) part.

### Figure 9-11: Latency-throughput curve with increasing in-flight requests

1. (Optional) Adjust the experiment settings (e.g., the number of runs) in the experiment runners `experiment/run_fig9_10_{default,acca,pcsched}.py`.

2. Run `experiment/run_fig9_10_default.py` under `5.10.46-linux+` (default Linux).

3. Run `experiment/run_fig9_10_acca.py` and `experiment/run_fig9_10_pcsched.py` under `5.10.46-latency+` (customized kernel).

#### Evaluation and Data Parse

1. The experiment results are located in the `single_core_iodepth_default`, `single_core_iodepth_acca`, and `single_core_iodepth_pcsched` folders under `/data/projects/latency`.

2. You can obtain the latency-throughput curve data by running the script from the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) part — just remember to change the configuration.

3. As mentioned in our paper, due to batching we can only measure the `rx_sched` latency when there are multiple in-flight requests per connection. Change the configuration in `parse/parse_iodepth_rxsched.py`:

    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_iodepth_acca"]
    ```

4. Run `parse/parse_iodepth_rxsched.py`. The script outputs the client-side and server-side P99.9 `rx_sched` latency. For example, for Linux+ACCa the results may look like:

    ```plain
    netian@node0:~/latency/parse$ python3 parse_iodepth_rxsched.py
    # single_core_iodepth_acca
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  client_samples  server_samples  client_p999  server_p999
    --------  --------  -------  ---  ---  -------  -----  ----  --------------  --------------  -----------  -----------
        2        64       32    1    1        1      1     3        24739133        24739139        76178        48594
    ......
    ```

5. Change the configuration in `parse/parse_iodepth_segments.py` to the experiments and run prefixes you are interested in:

    ```python
    result_dir = "/data/projects/latency"
    experiments = ["single_core_iodepth_acca"]
    prefixes = ["2_64_32_1_1_1_1_"]
    ```

6. Run `parse/parse_iodepth_segments.py`. The first column is the number of requests per segment and the second is the CDF at that value. For example:

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

### Figure 12: Latency-throughput curve and breakdown with multiple CPU cores

1. If you use different CPU cores, or your logical core numbering differs, you must change the configuration in the experiment scripts (`scripts/multi_cores_macro_{default,acca,pcsched}.sh`), the server-side experiment helper (`scripts/multi_cores_helper.sh`), and the experiment runners (`experiment/run_fig12_{default,acca,pcsched}.py`) — specifically `TASKSET`, `THREADS_PER_CORE`, and `cores`.

2. In that case you also need to change the client-side application core offset. Locate the following lines in `application/latency_client_cores.cc`, change the `core_offset` calculation to match the `TASKSET` you use, and recompile the application:

    ```c++
    int core_offset = sc < 48 ? (sc - 32) : (sc - 96 + 16);
    int starting_index = core_offset * thread_count;
    ```

3. (Optional) Change the configuration in `experiment/run_fig12_{default,acca,pcsched}.py`:

    ```python
    num_apps = [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
    flowsize = [64]
    iodepth = [1]
    dim = [0, 1]
    pin = [1]
    permute = [1]
    # NOTE: Unfortunately, the script is hardcoded to use 16 physical cores.
    # If you want to use a different number of cores, you will need to modify the
    # script, the helper, and application, and this runner script accordingly.
    cores = [16]
    runs = [0, 1, 2]
    ```

4. Run the experiment with `experiment/run_fig12_default.py` under `5.10.46-linux+` (default Linux).

5. Run the experiment with `experiment/run_fig12_{acca,pcsched}.py` under `5.10.46-latency+` (customized kernel).

#### Evaluation and Data Parse

1. The results of this experiment are in the `multi_cores_macro_{default,acca,pcsched}` folders under `/data/projects/latency`. Change the configuration in `parse/parse_multi_cores_latency_throughput.py` to the correct results directory. For example:

    ```python
    result_dir = "/data/projects/latency"
    experiments = ["multi_cores_macro_acca"]
    ```

2. Run `parse/parse_multi_cores_latency_throughput.py`. The results include the throughput, the P99.9 tail latency, and the number of interrupts for each setting across all its runs:

    ```plain
    netian@node0:~/latency/parse$ python3 parse_multi_cores_latency_throughput.py
    # multi_cores_macro_acca
    num_apps  flowsize  iodepth  dim  pin  permute  cores  runs  threads  mean_lat_us  p999_lat_us  thpt_mIOPS  client_intr/core  server_intr/core
    --------  --------  -------  ---  ---  -------  -----  ----  -------  -----------  -----------  ----------  ----------------  ----------------
        32        64        1    1    1        1     16     3      512      147.801      576.000     3.45124          14359687          14007636
    ```

3. To get the latency breakdown heatmap, follow the same process as in the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) part: first generate the `.npy` file with `parse/parse_breakdown_to_heatmap.py`, then draw the heatmap with `draw_heatmap.py`.

### Figure 13: In-flight requests with multiple CPU cores

Latency-throughput curve with increasing in-flight requests under multiple cores.

1. (Optional) Change the configuration in `experiment/run_fig13_{default,acca,pcsched}.py`:

    ```python
    num_apps = [2, 8, 32]
    flowsize = [64]
    iodepth = [1, 2, 4, 8, 16, 24, 32]
    dim = [0, 1]
    pin = [1]
    permute = [1]
    # NOTE: Unfortunately, the script is hardcoded to use 16 physical cores.
    # If you want to use a different number of cores, you will need to modify the
    # script, the helper, and application, and this runner script accordingly.
    cores = [16]
    runs = [0, 1, 2]
    ```

2. Run the experiment with `experiment/run_fig13_default.py` under `5.10.46-linux+` (default Linux).

3. Run the experiment with `experiment/run_fig13_{acca,pcsched}.py` under `5.10.46-latency+` (customized kernel).

#### Evaluation and Data Parse

1. Change the configuration in `parse/parse_multi_cores_latency_throughput.py` and run the script; the results include the throughput, the P99.9 tail latency, and the number of interrupts for each setting across all its runs.

### Figure 16: EEVDF performance

TODO: The imbalanced io depth experiment

1. Download the Linux 6.12.66 (EEVDF) kernel from [kernel.org](https://kernel.org):

    ```sh
    cd ~
    wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.12.66.tar.xz
    tar -xJf linux-6.12.66.tar.xz
    cp -r linux-6.12.66 linux-6.12-latency
    ```

2. Apply our ACCa and PCSched patch for the Linux 6.12.66 kernel:

    ```sh
    cd linux-6.12-latency
    git apply --check ../latency/linux-6.12-latency.patch
    git apply ../latency/linux-6.12-latency.patch
    ```

3. Compile the kernel following the directions above.

    > [!IMPORTANT]
    > Disable IRQ time accounting for the `linux-6.12.66` kernel, and enable it for the `linux-6.12.66-latency` kernel. See the kernel repo — the installation is similar.

4. Run the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) experiment under the default EEVDF kernel (`linux-6.12.66`) and our customized EEVDF kernel (`linux-6.12.66-latency`).

#### Evaluation and Data Parse

1. Please refer to the [Figure 3-4](#figure-3-4-latency-throughput-curve-and-latency-breakdown) part for the latency-throughput curve.

### Figure 14-15, 17: Supplementary experiments

The experiments above already support the key insights of our paper:

1. Scheduling dominates high tail latency.
2. Runtime may not be the ideal scheduling abstraction for low latency.
3. Traffic predictability can make interrupt tuning more effective.
4. Choose your parallelism carefully.

The experiments for Figures 14, 15, and 17 are **supplementary**. **We will update the experiment set for these experiments when time is available.**

If you are interested in the meantime, you can check our unorganized codebase ([link](https://github.com/amefumi/understand_latency)) for the applications and scripts used to run them. For example, Figure 14 can be produced by setting `flowsize` in the Figure 3-4 experiment; Figure 15 can be produced by changing the test application; and Figure 17 can be produced by referring to the Redis experiment in [NetChannel](https://github.com/Terabit-Ethernet/NetChannel).

## Acknowledgement

[Tianyu](https://netian.me) is the current maintainer of this project. Please contact him at zuotianyu@virginia.edu if you run into any issue.

Codex and Claude Code were used to polish this document and reorganize the experiment scripts.

If you find this work useful, please cite:

```bibtex
@inproceedings{UnderstandLatencyUVA,
  title={Understanding Host Network Stack Latency},
  author={Zuo, Tianyu and Hwang, Jaehyun and Tang, Ao and Agarwal, Rachit and Cai, Qizhe},
  booktitle={Proceedings of the ACM SIGCOMM 2026 Conference},
  pages={1127--1140},
  year={2026}
}
```
