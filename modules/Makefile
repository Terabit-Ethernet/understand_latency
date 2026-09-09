obj-m = vruntime_probe.o softirq_packets.o program_pmu.o packet_dist.o
KVERSION = $(shell uname -r)
all:
		make -C /lib/modules/$(KVERSION)/build M=$(PWD) modules
clean:
		make -C /lib/modules/$(KVERSION)/build M=$(PWD) clean