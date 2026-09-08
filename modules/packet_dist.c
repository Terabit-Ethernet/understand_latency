#include <linux/kernel.h>
#include <linux/netfilter.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/netfilter_ipv4.h>
#include <linux/ip.h>
#include <linux/inet.h>
#include <linux/ktime.h>

#define SEGMENT_HISTO_SIZE 96 // should be 64, but we leave some margin
#define FILTER_OUTPUT_CPUS(x) (x == 1 || x == 1)
#define FILTER_PRINT_CPUS(x) (x == 73)
// #define COUNTING_SERVER_SIDE

static int enable_filter __read_mostly = 0;

module_param(enable_filter, int, 0644);
MODULE_PARM_DESC(enable_filter, "Count softirq handling");

long rx_softirq_histo[SEGMENT_HISTO_SIZE] __read_mostly;

u64 old_time, cur_time;
u64 segment_counter_total_bytes = 0;
u64 segment_counter_total_pkts = 0;
u64 segment_counter_acks = 0;


unsigned int skb_segments_counter(void *priv, struct sk_buff *skb, const struct nf_hook_state *state) {
    struct iphdr *iph = ip_hdr(skb);
    int i;

    if (enable_filter > 0) {
#ifdef COUNTING_SERVER_SIDE
        if(iph->saddr == in_aton("192.168.1.101") && iph->daddr == in_aton("192.168.1.102")) {
#else
        if(iph->saddr == in_aton("192.168.1.102") && iph->daddr == in_aton("192.168.1.101")) {
#endif
            cur_time = ktime_get_ns();

            if(FILTER_OUTPUT_CPUS(raw_smp_processor_id())) {
                if(skb->len >= 64) {
                    rx_softirq_histo[(skb->len - 52) / 64] += 1;
                    segment_counter_total_bytes += skb->len - 52;
                    segment_counter_total_pkts += 1;
                } else {
                    segment_counter_acks += 1;
                }
            }

            if(cur_time - old_time > 10000000000 && FILTER_PRINT_CPUS(raw_smp_processor_id())) {
                int offset = 0;
                char buffer[2048]; // Ensure this buffer is large enough for your data

                buffer[0] = '\0';
                old_time = cur_time;

                for (i = 0; i < SEGMENT_HISTO_SIZE; i++) {
                    offset += snprintf(buffer + offset, sizeof(buffer) - offset, "%lu ", rx_softirq_histo[i]);
                }
                printk("Segments Histogram: %s\n", buffer);

                for (i = 0; i < SEGMENT_HISTO_SIZE; i++){
                    rx_softirq_histo[i] = 0;
                }

                if(segment_counter_total_pkts != 0) {
                    printk("Segments Stats: %llu %llu %llu %llu\n", segment_counter_total_bytes / segment_counter_total_pkts, segment_counter_total_bytes, segment_counter_total_pkts, segment_counter_acks);
                }
                segment_counter_total_pkts = 0;
                segment_counter_total_bytes = 0;
                segment_counter_acks = 0;
            }
        }
    }
    return NF_ACCEPT;
}

// Monitor the requests number in a single skb.
static struct nf_hook_ops nfho = {
    .hook = skb_segments_counter,
    .pf = PF_INET,
    .hooknum = NF_INET_PRE_ROUTING,
    .priority = NF_IP_PRI_FIRST,
};

static int __init sknf_init(void)
{
    int ret;

    ret = nf_register_net_hook(&init_net, &nfho);
    if (ret) {
        pr_err("nf_register nfho failed: %d\n", ret);
        return ret;
    }

    pr_info("Loading filter module\n");

    cur_time = old_time = ktime_get_ns();

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
MODULE_DESCRIPTION("Get the number of segments in a single skb");
MODULE_LICENSE("GPL");
