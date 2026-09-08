#include <linux/kernel.h>
#include <linux/netfilter.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/netfilter_ipv4.h>
#include <linux/ip.h>
#include <linux/inet.h>
#include <linux/sched.h>
#include <linux/percpu.h>

#define FILTER_ARRAY_SIZE 96
#define FILTER_OUTPUT_CPUS(x) (x == 1 || x == 73)
#define FILTER_PRINT_CPUS(x) (x == 73)
// #define COUNTING_SERVER_SIDE

static int enable_filter __read_mostly = 0;

module_param(enable_filter, int, 0644);
MODULE_PARM_DESC(enable_filter, "Count softirq handling");

struct filter_entry
{
	int pid;
	long count;
};

DEFINE_PER_CPU(struct filter_entry[FILTER_ARRAY_SIZE], percpu_counter);

u64 old_time, cur_time;


unsigned int softirq_packet_counter(void *priv, struct sk_buff *skb, const struct nf_hook_state *state) {
	struct iphdr *iph = ip_hdr(skb); 
	pid_t pid = 0;
	int hash_index = 0;
	int real_index = 0;
	int i = 0;
	struct filter_entry *arr;

	if (enable_filter > 0) {
#ifdef COUNTING_SERVER_SIDE
		if(iph->saddr == in_aton("192.168.1.101") && iph->daddr == in_aton("192.168.1.102")) {
#else
		if(iph->saddr == in_aton("192.168.1.102") && iph->daddr == in_aton("192.168.1.101")) {
#endif
			pid = current->pid;
			cur_time = ktime_get_ns();
			arr = per_cpu(percpu_counter, raw_smp_processor_id());
			hash_index = pid % FILTER_ARRAY_SIZE;
			for(i = 0; i < FILTER_ARRAY_SIZE; i++) {
				real_index = (hash_index + i) % FILTER_ARRAY_SIZE;
				if(arr[real_index].pid == 0 || arr[real_index].pid == pid) {
					arr[real_index].pid = pid;
					arr[real_index].count += (skb->len - 52) / 64;
					break;
				} 
			}
			if(cur_time - old_time > 10000000000 && FILTER_PRINT_CPUS(raw_smp_processor_id())) {
				for_each_possible_cpu(i) {
					arr = per_cpu(percpu_counter, i);
					if (FILTER_OUTPUT_CPUS(i)) {
						char pid_buffer[2048];
						char count_buffer[2048];
						int offset = 0;
						int j;
						for (j = 0; j < FILTER_ARRAY_SIZE; j++) {
							offset += snprintf(pid_buffer + offset, sizeof(pid_buffer) - offset, "%d ", arr[j].pid);
						}
						offset = 0;
						for (j = 0; j < FILTER_ARRAY_SIZE; j++) {
							offset += snprintf(count_buffer + offset, sizeof(count_buffer) - offset, "%ld ", arr[j].count);
							arr[j].count = 0;
						}
						printk("Core:%d PIDs: %s\n", i, pid_buffer);
						printk("Core:%d Counts: %s\n", i, count_buffer);
					}
				}
				old_time = cur_time;
			}
    	}
	} 
	return NF_ACCEPT;
}

// Monitor the packets handled in softIRQ
static struct nf_hook_ops nfho = {
	.hook = softirq_packet_counter,
    .pf = PF_INET,
    .hooknum = NF_INET_PRE_ROUTING,
    .priority = NF_IP_PRI_FIRST,
};


static int __init sknf_init(void)
{
	int ret, i, j;
	struct filter_entry *arr;

	ret = nf_register_net_hook(&init_net, &nfho);
	if (ret) {
		pr_err("nf_register nfho failed: %d\n", ret);
		return ret;
	}

 	pr_info("Loading filter module\n");

	cur_time = old_time = ktime_get_ns();

	for_each_possible_cpu(i) {
		arr = per_cpu(percpu_counter, i);
		if(FILTER_OUTPUT_CPUS(i)) {
			for (j = 0; j < FILTER_ARRAY_SIZE; j++) {
				arr[j].count = 0;
				arr[j].pid = 0;
			}
		}
	}

    return 0;
}

static void __exit sknf_exit(void)
{
	nf_unregister_net_hook(&init_net, &nfho);
	printk(KERN_INFO "Filter unloaded\n");
	return;
}

module_init(sknf_init);
module_exit(sknf_exit);
MODULE_AUTHOR("UVA NetSys");
MODULE_DESCRIPTION("Count packets processed in softIRQ by a thread");
MODULE_LICENSE("GPL");
