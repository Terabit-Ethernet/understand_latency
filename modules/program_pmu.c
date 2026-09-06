// SPDX-License-Identifier: GPL-2.0
/*
 * program_pmu.ko — program General-Purpose PMCs on selected CPUs for per-stage
 * measurement via rdpmc. Pairs with the customized latency-breakdown
 * instrumentation kernel.
 *
 * Counters programmed (per target CPU), in counters[] order:
 *   PMC0: CYCLE_ACTIVITY.STALLS_TOTAL. The total number of cycles during which
 *      the pipeline is stalled on any resource.
 *   PMC1: CYCLE_ACTIVITY.STALLS_L1D_MISS. The total number of stall cycles
 *      when there is at least one outstanding L1D cache demand.
 *
 * See https://perfmon-events.intel.com/ for details on the counter definitions.
 *
 */

#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/cpu.h>
#include <linux/smp.h>
#include <linux/slab.h>
#include <asm/msr.h>
#include <asm/perf_event.h>
#include <asm/nmi.h>

#define DRV_NAME "program_pmu"

/* PERFEVTSEL bits */
#define EVTSEL_USR              (1ULL << 16)
#define EVTSEL_OS               (1ULL << 17)
#define EVTSEL_EN               (1ULL << 22)

#define EVT(ev, um)             ((ev) | ((um) << 8))

#define NUM_COUNTERS 2

struct counter_cfg {
	const char *name;
	u64 event_umask;
	u32 pmc;            /* which GP counter: 0..7 */
	bool needs_offcore;
	u32 offcore_msr;
	u64 offcore_value;
	u32 cmask;          /* PERFEVTSEL bits 24-31; 0 for most events */
};

static const struct counter_cfg counters[NUM_COUNTERS] = {
	{ "CYCLE_ACTIVITY.STALLS_TOTAL",
		EVT(0xA3, 0x04), 0, false, 0, 0, 0x04 },
	{ "CYCLE_ACTIVITY.STALLS_L1D_MISS",
 		EVT(0xA3, 0x0C), 1, false, 0, 0, 0x0C },
};

static int cpus[NR_CPUS] = { 32, 96 };
static int ncpus = 2;
module_param_array(cpus, int, &ncpus, 0444);
MODULE_PARM_DESC(cpus, "CPUs to program (default: 32,96)");

struct pmu_state {
	bool reserved_pmc[NUM_COUNTERS];
	bool reserved_evt[NUM_COUNTERS];
	bool programmed;
};
static struct pmu_state *pmu_states;

static void pmu_program_this_cpu(void *info)
{
	int cpu = smp_processor_id();
	struct pmu_state *st = &pmu_states[cpu];
	int i;
	u64 v;
	u64 gctrl;

	/* Disable all first */
	for (i = 0; i < NUM_COUNTERS; i++) {
		wrmsrl(MSR_P6_EVNTSEL0 + counters[i].pmc, 0);
		wrmsrl(MSR_IA32_PMC0   + counters[i].pmc, 0);
	}

	/* Program offcore_rsp MSRs first */
	for (i = 0; i < NUM_COUNTERS; i++) {
		if (counters[i].needs_offcore)
			wrmsrl(counters[i].offcore_msr,
			       counters[i].offcore_value);
	}

	/* Now arm the event selectors */
	for (i = 0; i < NUM_COUNTERS; i++) {
		v = counters[i].event_umask | EVTSEL_USR | EVTSEL_OS | EVTSEL_EN 
			| ((u64)counters[i].cmask << 24);
		wrmsrl(MSR_P6_EVNTSEL0 + counters[i].pmc, v);
	}

	/* Make sure we enable counters 4-7 */
	rdmsrl(MSR_CORE_PERF_GLOBAL_CTRL, gctrl);
	for (i = 0; i < NUM_COUNTERS; i++)
		gctrl |= BIT_ULL(counters[i].pmc);
	wrmsrl(MSR_CORE_PERF_GLOBAL_CTRL, gctrl);

	/* Self-check: read back and log */
	for (i = 0; i < NUM_COUNTERS; i++) {
		u64 evt, pmc;
		rdmsrl(MSR_P6_EVNTSEL0 + counters[i].pmc, evt);
		rdmsrl(MSR_IA32_PMC0   + counters[i].pmc, pmc);
		pr_info(DRV_NAME ": CPU%d PMC%d evtsel=0x%llx pmc=%llu (%s)\n",
		        cpu, counters[i].pmc, evt, pmc, counters[i].name);
	}
	for (i = 0; i < NUM_COUNTERS; i++) {
		u64 rsp;
		if (!counters[i].needs_offcore)
			continue;
		rdmsrl(counters[i].offcore_msr, rsp);
		pr_info(DRV_NAME ": CPU%d OFFCORE_RSP(0x%x)=0x%llx\n",
		        cpu, counters[i].offcore_msr, rsp);
	}

	st->programmed = true;
}

static void pmu_disable_this_cpu(void *info)
{
	int cpu = smp_processor_id();
	struct pmu_state *st = &pmu_states[cpu];
	int i;

	if (!st->programmed)
		return;

	for (i = 0; i < NUM_COUNTERS; i++) {
		wrmsrl(MSR_P6_EVNTSEL0 + counters[i].pmc, 0);
		wrmsrl(MSR_IA32_PMC0   + counters[i].pmc, 0);
	}
	/* Don't clear OFFCORE_RSP — perf or others may want it later */

	st->programmed = false;
}

static int reserve_all_counters(void)
{
	struct pmu_state *st = &pmu_states[cpus[0]];
	int i;

	for (i = 0; i < NUM_COUNTERS; i++) {
		if (!reserve_perfctr_nmi(MSR_IA32_PMC0 + counters[i].pmc))
			return -EBUSY;
		st->reserved_pmc[i] = true;

		if (!reserve_evntsel_nmi(MSR_P6_EVNTSEL0 + counters[i].pmc))
			return -EBUSY;
		st->reserved_evt[i] = true;
	}
	return 0;
}

static void release_all_counters(void)
{
	struct pmu_state *st = &pmu_states[cpus[0]];
	int i;

	for (i = NUM_COUNTERS - 1; i >= 0; i--) {
		if (st->reserved_evt[i]) {
			release_evntsel_nmi(MSR_P6_EVNTSEL0 + counters[i].pmc);
			st->reserved_evt[i] = false;
		}
		if (st->reserved_pmc[i]) {
			release_perfctr_nmi(MSR_IA32_PMC0 + counters[i].pmc);
			st->reserved_pmc[i] = false;
		}
	}
}

static int __init latency_pmu_init(void)
{
	int i, ret;

	pmu_states = kcalloc(num_possible_cpus(), sizeof(*pmu_states), GFP_KERNEL);
	if (!pmu_states)
		return -ENOMEM;

	if (ncpus < 1) { ret = -EINVAL; goto out_free; }

	ret = reserve_all_counters();
	if (ret) {
		pr_err(DRV_NAME ": PMCs not reserved (watchdog on? perf busy?)\n");
		pr_err(DRV_NAME ": try: echo 0 > /proc/sys/kernel/nmi_watchdog\n");
		goto out_release;
	}

	for (i = 0; i < ncpus; i++) {
		int cpu = cpus[i];
		if (cpu < 0 || cpu >= num_possible_cpus() || !cpu_online(cpu)) {
			pr_warn(DRV_NAME ": cpu %d invalid or offline, skipping\n", cpu);
			continue;
		}
		smp_call_function_single(cpu, pmu_program_this_cpu, NULL, 1);
	}

	pr_info(DRV_NAME ": loaded with %d counters\n", NUM_COUNTERS);
	return 0;

out_release:
	release_all_counters();
out_free:
	kfree(pmu_states);
	return ret;
}

static void __exit latency_pmu_exit(void)
{
	int i;

	for (i = 0; i < ncpus; i++) {
		int cpu = cpus[i];
		if (cpu < 0 || cpu >= num_possible_cpus() || !cpu_online(cpu))
			continue;
		smp_call_function_single(cpu, pmu_disable_this_cpu, NULL, 1);
	}

	release_all_counters();
	kfree(pmu_states);
	pr_info(DRV_NAME ": unloaded\n");
}

module_init(latency_pmu_init);
module_exit(latency_pmu_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Tianyu Zuo <zuotianyu@virginia.edu>");
MODULE_DESCRIPTION("Per-CPU PMU setup for per-stage CPU events measurement.");