/*
 * net_trace.c: BPF program for TCP connect events.
 * Attaches to kprobe on tcp_v4_connect and tcp_v6_connect.
 * Captures: pid, remote addr (IPv4/IPv6), remote port, local port.
 */

#include <uapi/linux/ptrace.h>
#include <net/sock.h>

#define TASK_COMM_LEN 16

struct ipv4_net_event_t {
    __u32 pid;
    __u32 saddr;
    __u32 daddr;
    __u16 lport;
    __u16 dport;
    char task[TASK_COMM_LEN];
};

struct ipv6_net_event_t {
    __u32 pid;
    __u8 saddr[16];
    __u8 daddr[16];
    __u16 lport;
    __u16 dport;
    char task[TASK_COMM_LEN];
};

BPF_HASH(currsock, __u32, struct sock *);
BPF_PERF_OUTPUT(ipv4_events);
BPF_PERF_OUTPUT(ipv6_events);

int trace_connect_entry(struct pt_regs *ctx, struct sock *sk)
{
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 tid = (__u32)pid_tgid;

    currsock.update(&tid, &sk);
    return 0;
}

static int trace_connect_return(struct pt_regs *ctx, int ipver)
{
    int ret = PT_REGS_RC(ctx);
    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 pid = pid_tgid >> 32;
    __u32 tid = (__u32)pid_tgid;

    struct sock **skpp = currsock.lookup(&tid);
    if (!skpp)
        return 0;

    if (ret != 0) {
        currsock.delete(&tid);
        return 0;
    }

    struct sock *skp = *skpp;
    __u16 lport = skp->__sk_common.skc_num;
    __u16 dport = skp->__sk_common.skc_dport;

    if (ipver == 4) {
        struct ipv4_net_event_t ev4 = {};
        ev4.pid = pid;
        ev4.saddr = skp->__sk_common.skc_rcv_saddr;
        ev4.daddr = skp->__sk_common.skc_daddr;
        ev4.lport = lport;
        ev4.dport = ntohs(dport);
        bpf_get_current_comm(&ev4.task, sizeof(ev4.task));
        ipv4_events.perf_submit(ctx, &ev4, sizeof(ev4));
    } else {
        struct ipv6_net_event_t ev6 = {};
        ev6.pid = pid;
        bpf_probe_read_kernel(&ev6.saddr, sizeof(ev6.saddr),
            skp->__sk_common.skc_v6_rcv_saddr.in6_u.u6_addr32);
        bpf_probe_read_kernel(&ev6.daddr, sizeof(ev6.daddr),
            skp->__sk_common.skc_v6_daddr.in6_u.u6_addr32);
        ev6.lport = lport;
        ev6.dport = ntohs(dport);
        bpf_get_current_comm(&ev6.task, sizeof(ev6.task));
        ipv6_events.perf_submit(ctx, &ev6, sizeof(ev6));
    }

    currsock.delete(&tid);
    return 0;
}

int trace_connect_v4_return(struct pt_regs *ctx)
{
    return trace_connect_return(ctx, 4);
}

int trace_connect_v6_return(struct pt_regs *ctx)
{
    return trace_connect_return(ctx, 6);
}
