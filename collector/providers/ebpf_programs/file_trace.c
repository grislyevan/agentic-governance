/*
 * file_trace.c: BPF program for file open events.
 * Attaches to tracepoint syscalls/sys_enter_openat.
 * Captures: pid, filename, flags (O_CREAT/O_WRONLY/O_RDWR for create/write).
 */

#include <uapi/linux/ptrace.h>
#include <linux/fs.h>

#define NAME_MAX 255
#define TASK_COMM_LEN 16

#ifndef O_CREAT
#define O_CREAT 00000100
#endif
#ifndef O_WRONLY
#define O_WRONLY 00000001
#endif
#ifndef O_RDWR
#define O_RDWR 00000002
#endif

struct file_event_t {
    __u32 pid;
    int flags;
    char comm[TASK_COMM_LEN];
    char filename[NAME_MAX];
};

BPF_PERF_OUTPUT(file_events);

int trace_sys_enter_openat(struct pt_regs *ctx)
{
    struct file_event_t ev = {};
    int dfd = (int)PT_REGS_PARM1(ctx);
    const char __user *filename = (const char __user *)PT_REGS_PARM2(ctx);
    int flags = (int)PT_REGS_PARM3(ctx);

    ev.pid = bpf_get_current_pid_tgid() >> 32;
    ev.flags = flags;
    bpf_get_current_comm(&ev.comm, sizeof(ev.comm));
    bpf_probe_read_user_str(&ev.filename, sizeof(ev.filename), (void *)filename);
    ev.filename[NAME_MAX - 1] = '\0';

    file_events.perf_submit(ctx, &ev, sizeof(ev));
    return 0;
}
