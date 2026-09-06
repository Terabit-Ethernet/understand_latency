# Understanding Host Network Stack Latency

Measurement tools for SIGCOMM '2026 paper "Understanding Host Network Stack Latency"

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


We rely on `hwstamp_ctl` and `phc2sys` to sync time between CPU and NIC, and read NIC's hardware timestamp. We also rely on `sar` for CPU utilization monitoring.
```sh
sudo apt update
sudo apt install linuxptp sysstat
```


## Kernel Installation

Please refer to linux-latency repo for kernel installation. In this document, we will explicitely denote which kernel is required for each set of experiments.

Note: We recommend duplicate the clone for different kernel version since kernel compiling could be very slow, and we need to switch between different kernels. You MUST build separate kernel images for each machine. The latency monitor is keyed to the host's own IP address, which is hardcoded at compile time.

We assume we have two kernel: one is the default (e.g., 5.10.46-default), and one is for IRQa, ACCa, and PCSched (e.g., 5.10.46-latency), which are switched by runtime parameters.

## Artifact Evaluation Guide
Important: the experimental results from artifact evaluation may differ significantly from that in our paper due to hardware differences. To fully reproduce the results in our paper, we recommend using exactly the same hardware (i.e., CPU, RAM, and NIC); that said, due to potential export control and policy issue, we were unable to provide access to our own servers.

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
We assume you have installed the kernel and drivers as we instructed before. We should have two kernel in `/boot`:
1. `5.10.46-linux+`: This is the default Linux kernel that disable the IRQ time accounting option.
2. `5.10.46-latency+`: This is the experimental Linux kernel with IRQ time accounting; our design (ACCa and PCSched) will work through runtime parameter settings.

### Environment Preparation
1. Clone the project to `latency` under user's folder (`/usr/netian` in r650 server).
    ```sh
    cd /user/netian
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

1. Run `host_setup.sh` on the Client side, and run `target_setup.sh` in the server side. These script will setup the CPU affinity to NIC's interrupt channel, aRFS, GRO, and other optimization we used in our experiment. Note: You should use tmux to run these script, or keep the ssh window, to make sure `phc2sys` alive.
    ```sh
    tmux new -s setup

    # Client side
    sudo ./host_setup.sh
    # Server side
    sudo ./target_setup.sh

    # Note: Use Ctrl+B, then D to leave tmux window.
    ```

### Application Preparation
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

Compile the test application:
```sh
cd ./application
make clean && make
```


### Figure 2: the isolated performance for default Linux
1. Reboot to `5.10.46-linux+` kernel:
    ```sh
    sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.10.46-linux+"
    sudo reboot
    ```
2. 


#### Evaluation and Data Parse


### Figure 3-4: The latency-throughput curve and latency breakdown for Linux, Linux+IRQa, Linux+ACCa, and Linux+PCSched

- You should also be able to get the Figure 8a and Figure 8b through this set of experiment

### Figure 5: (Modeled) virtual runtime and packets processed in softIRQ for Linux, Linux+ACCa, and Linux+PCSched

### Figure 7: Processing Time vs Stall Cycles for Linux+ACCa


program_pmu.c -> Subtitute code with Perfmon; disable nmi_watchdog first:
echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog

sudo rmmod latency_pmu
sudo insmod /home/ame/latency/read_rdpmc/latency_pmu.ko


### Figure 8c: The latency-throughput curve for Linux+PCSched+AutoDIM

### Figure 9-10: Latency-throughput curve with increasing in-flight requests for Linux, Linux+ACCa, and Linux+PCSched

### Figure 11: CDF for the number of requests per segment

### Figure 12: Latency-throughput curve and latency breakdown for Linux, Linux+ACCa, Linux+PCSched, and Linux+PCSched+AutoDIM with multiple CPU cores

### Figure 13: 

### [Linux, Linux+ACCa, Linux+PCSched] Single Core, Multiple Threads


## Unorganized Codebase

Due to time limit and the standard to fulfill the "functional" requirement, we only show the functionality our our customized kernel used to measure per-component latency, our experimental application, our kernel modules (to observe virtual runtime, packets in softIRQ, and packet size distribution, and to program general-purpose PMU), and reference experiment script. The experiments in our paper would need more adjustment in experiment script.

Please note it is hard to reproduce all experiments results in our paper due to hardware differences. If you are interested in reproducing the exact results, please try to build the same hardware environment as mentioned in this document.


For more experiments, if you are interested, please refer to the codebase in (Tianyu's Github), where lies the code for 

When we (more specifically, Tianyu) have time, we will update the code to fully cover the experiments, including:
- Incast/outcast
- Hetergenous message size
- 

Though, once you have the customized kernel, the experimental application, the essential kernel modules, and the reference experiment script, you should be able to design any new experiments.


## Contact Us
Please contact Tianyu if you have any issue running this codebase: zuotianyu@virginia.edu

If you find this work helpful, please consider citing us:
