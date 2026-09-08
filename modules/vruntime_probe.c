#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/init.h>
#include <linux/sched/signal.h>
#include <linux/sched.h>
#include <linux/string.h>
#include <linux/hrtimer.h>
#include <linux/workqueue.h>
#include <linux/rcupdate.h>

#ifndef UINT64_MAX
#define UINT64_MAX              (u64)(~((u64)0))
#endif

#define THREAD_ARRAY_SIZE 128

static int count = 0;
static struct workqueue_struct *iter_thread_wq;
static struct work_struct iterate_thread_work;
static struct work_struct iterate_thread_start_work;
static struct hrtimer iter_thread_timer;
static u64 per_thread_runtime[THREAD_ARRAY_SIZE];
static u64 per_thread_id[THREAD_ARRAY_SIZE];
static u64 rq_thread_runtime[THREAD_ARRAY_SIZE];
static u64 rq_thread_id[THREAD_ARRAY_SIZE];

static int sample_cpu = 73;
module_param(sample_cpu, int, 0644);
MODULE_PARM_DESC(sample_cpu, "CPU to run sampling workqueue on");

static int total_count = 120;
module_param(total_count, int, 0644);
MODULE_PARM_DESC(total_count, "Total number of samples to take");

static unsigned int interval_ms = 1000;
module_param(interval_ms, uint, 0644);
MODULE_PARM_DESC(interval_ms, "Interval between samples in milliseconds");


int iterate_thread(void)                    /*    Init Module    */
{
    struct task_struct *task, *thread;
    int num_threads = 0, num_rq_thread = 0, i=0;
    u64 min_runtime = UINT64_MAX;
    char buffer[2048];
    char buffer2[2048];
    int offset = 0;

    buffer[0] = '\0';
    buffer2[0] = '\0';

    rcu_read_lock();
    for_each_process( task ){
        if(strcmp(task->comm, "latency_client") == 0 || strcmp(task->comm, "latency_server") == 0) {
            for_each_thread(task, thread) {
                per_thread_runtime[num_threads] = thread->se.vruntime;
                per_thread_id[num_threads] = thread->pid;
                num_threads += 1;
                if (thread->se.vruntime < min_runtime || min_runtime == -1) {
                        min_runtime = thread->se.vruntime;
                }
                if (READ_ONCE(thread->on_rq)) {
                    rq_thread_runtime[num_rq_thread] = thread->se.vruntime;
                    rq_thread_id[num_rq_thread] = thread->pid;
                    num_rq_thread += 1;
                }
            }       
        }
    }
    rcu_read_unlock();


    offset = 0;
    for (i = 0; i < num_threads; i++) {
        offset += scnprintf(buffer2 + offset, sizeof(buffer2) - offset, "%llu ", (unsigned long long)per_thread_id[i]);
        per_thread_id[i] = 0;
    }
    pr_info("All-thread IDs: %s\n", buffer2);

    offset = 0;
    for (i = 0; i < num_threads; i++) {
        offset += scnprintf(buffer + offset, sizeof(buffer) - offset, "%llu ", (unsigned long long)per_thread_runtime[i]);
        per_thread_runtime[i] = 0;
    }
    pr_info("All-thread vruntime: %s\n", buffer);

    count += 1;
    return 0;
}
     

static void iterate_thread_work_handler(struct work_struct *w) {
    iterate_thread();
    return;
}

static void iterate_thread_start_work_handler(struct work_struct *w) {
    hrtimer_start(&iter_thread_timer, ns_to_ktime(0), HRTIMER_MODE_REL_PINNED_SOFT);
    return;
}

enum hrtimer_restart iter_thread_timer_handler(struct hrtimer *timer)
{
    ktime_t interval = ns_to_ktime((u64)interval_ms * NSEC_PER_MSEC);
    if (count < total_count) {
        hrtimer_forward_now(timer, interval);
        queue_work_on(sample_cpu, iter_thread_wq, &iterate_thread_work);
        return HRTIMER_RESTART;
    }
    return HRTIMER_NORESTART;
}

static int __init init_iterate(void)
{
    iter_thread_wq = alloc_workqueue("iter_thread_wq", WQ_MEM_RECLAIM | WQ_HIGHPRI, 0); 
    hrtimer_init(&iter_thread_timer, CLOCK_MONOTONIC, HRTIMER_MODE_REL_PINNED_SOFT);
    iter_thread_timer.function = &iter_thread_timer_handler;

    INIT_WORK(&iterate_thread_work, iterate_thread_work_handler);
    INIT_WORK(&iterate_thread_start_work, iterate_thread_start_work_handler);

    queue_work_on(sample_cpu, iter_thread_wq, &iterate_thread_start_work);

    pr_info("iterate_cfs_rq: sampling CFS rq on all CPUs; worker on CPU %d\n", sample_cpu);

    return 0;
}
void cleanup_exit(void)
{
    hrtimer_cancel(&iter_thread_timer);
    flush_workqueue(iter_thread_wq);
    destroy_workqueue(iter_thread_wq);
    pr_info("iterate_cfs_rq: unloaded\n");
}
 
module_init(init_iterate);
module_exit(cleanup_exit);
 
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Probe virtual runtime of latency_{client,server} in a given CPU");
MODULE_AUTHOR("UVA NetSys");