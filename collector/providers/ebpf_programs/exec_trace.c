/*
 * exec_trace.c: BPF program for process exec events.
 * Attaches to tracepoint/sched/sched_process_exec.
 * Captures: pid, ppid, binary path (filename), comm.
 */

#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

#define MAX_PATH 256
#define TASK_COMM_LEN 16

struct exec_event_t {
    __u32 pid;
    __u32 ppid;
    char comm[TASK_COMM_LEN];
    char filename[MAX_PATH];
};

BPF_PERF_OUTPUT(exec_events);

int trace_sched_process_exec(struct pt_regs *ctx, void *arg)
{
    struct exec_event_t ev = {};
    __u32 loc;
    __u32 data_len;
    __u32 data_offset;
    void *filename_ptr;
    struct task_struct *task;

    ev.pid = bpf_get_current_pid_tgid() >> 32;

    task = (struct task_struct *)bpf_get_current_task();
    if (task && task->real_parent)
        ev.ppid = task->real_parent->tgid;

    bpf_get_current_comm(&ev.comm, sizeof(ev.comm));

    loc = *(__u32 *)((char *)arg + 8);
    data_offset = loc & 0xFFFF;
    data_len = (loc >> 16) & 0xFFFF;
    if (data_len > MAX_PATH - 1)
        data_len = MAX_PATH - 1;
    filename_ptr = (char *)arg + data_offset;
    bpf_probe_read_kernel(&ev.filename, data_len, filename_ptr);
    ev.filename[MAX_PATH - 1] = '\0';

    exec_events.perf_submit(ctx, &ev, sizeof(ev));
    return 0;
}
