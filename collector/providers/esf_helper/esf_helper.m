/*
 * ESF helper: subscribes to Endpoint Security events and writes JSON lines
 * to a Unix domain socket. Requires root and com.apple.developer.endpoint-security.client.
 *
 * Usage: esf_helper <socket_path>
 */

#import <EndpointSecurity/EndpointSecurity.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <bsm/libbsm.h>
#import <errno.h>
#import <signal.h>
#import <string.h>
#import <sys/socket.h>
#import <sys/stat.h>
#import <sys/un.h>
#import <time.h>
#import <unistd.h>

static es_client_t *g_client = NULL;
static int g_sock = -1;
static volatile sig_atomic_t g_running = 1;

static void write_timestamp(char *buf, size_t bufsz) {
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    strftime(buf, bufsz, "%Y-%m-%dT%H:%M:%SZ", &tm);
}

static void escape_json_str(const char *in, size_t len, char *out, size_t outsz) {
    size_t j = 0;
    for (size_t i = 0; i < len && j < outsz - 2; i++) {
        char c = in[i];
        if (c == '"' || c == '\\') {
            if (j + 2 >= outsz) break;
            out[j++] = '\\';
            out[j++] = c;
        } else if (c >= 0x20 && c < 0x7f) {
            out[j++] = c;
        } else if (c == '\n') {
            if (j + 2 >= outsz) break;
            out[j++] = '\\';
            out[j++] = 'n';
        } else if (c == '\t') {
            if (j + 2 >= outsz) break;
            out[j++] = '\\';
            out[j++] = 't';
        }
    }
    out[j] = '\0';
}

static const char *find_last_slash(const char *data, size_t len) {
    const char *p = data + len;
    while (p > data) {
        p--;
        if (*p == '/') return p + 1;
    }
    return data;
}

static void write_line(const char *line) {
    size_t len = strlen(line);
    if (len == 0) return;
    ssize_t n = write(g_sock, line, len);
    if (n < 0) {
        fprintf(stderr, "esf_helper: write failed: %s\n", strerror(errno));
    }
    n = write(g_sock, "\n", 1);
    if (n < 0) {
        fprintf(stderr, "esf_helper: write newline failed: %s\n", strerror(errno));
    }
}

static void handle_exec(const es_message_t *msg) {
    char ts[32];
    write_timestamp(ts, sizeof(ts));

    const es_process_t *proc = msg->event.exec.target;
    if (!proc || !proc->executable) return;

    const es_string_token_t *path_tok = &proc->executable->path;
    char path_buf[4096];
    size_t path_len = path_tok->length < sizeof(path_buf) - 1 ? path_tok->length : sizeof(path_buf) - 1;
    memcpy(path_buf, path_tok->data, path_len);
    path_buf[path_len] = '\0';

    char path_esc[8192];
    escape_json_str(path_buf, path_len, path_esc, sizeof(path_esc));

    const char *name = find_last_slash(path_buf, path_len);
    char name_esc[1024];
    escape_json_str(name, strlen(name), name_esc, sizeof(name_esc));

    char cmdline_buf[8192];
    cmdline_buf[0] = '\0';
    size_t total = 0;
    uint32_t argc = es_exec_arg_count(&msg->event.exec);
    for (uint32_t i = 0; i < argc && total < sizeof(cmdline_buf) - 1; i++) {
        es_string_token_t arg = es_exec_arg(&msg->event.exec, i);
        if (arg.length > 0 && arg.data) {
            size_t copy = arg.length;
            if (copy + total + 2 > sizeof(cmdline_buf)) copy = sizeof(cmdline_buf) - total - 2;
            if (total > 0) cmdline_buf[total++] = ' ';
            memcpy(cmdline_buf + total, arg.data, copy);
            total += copy;
            cmdline_buf[total] = '\0';
        }
    }

    char cmdline_esc[16384];
    escape_json_str(cmdline_buf, total, cmdline_esc, sizeof(cmdline_esc));

    char codesigning_buf[256];
    snprintf(codesigning_buf, sizeof(codesigning_buf), "0x%x", proc->codesigning_flags);

    pid_t pid = audit_token_to_pid(proc->audit_token);

    char buf[32768];
    snprintf(buf, sizeof(buf),
        "{\"type\":\"exec\",\"pid\":%d,\"ppid\":%d,\"name\":\"%s\",\"cmdline\":\"%s\","
        "\"username\":\"\",\"binary_path\":\"%s\",\"codesigning\":\"%s\",\"timestamp\":\"%s\"}",
        pid, proc->ppid, name_esc, cmdline_esc, path_esc, codesigning_buf, ts);
    write_line(buf);
}

static void handle_open(const es_message_t *msg) {
    char ts[32];
    write_timestamp(ts, sizeof(ts));

    const es_event_open_t *ev = &msg->event.open;
    if (!ev->file) return;

    const es_string_token_t *path_tok = &ev->file->path;
    char path_buf[4096];
    size_t path_len = path_tok->length < sizeof(path_buf) - 1 ? path_tok->length : sizeof(path_buf) - 1;
    memcpy(path_buf, path_tok->data, path_len);
    path_buf[path_len] = '\0';

    char path_esc[8192];
    escape_json_str(path_buf, path_len, path_esc, sizeof(path_esc));

    const es_process_t *proc = msg->process;
    const char *pname = NULL;
    size_t pname_len = 0;
    if (proc && proc->executable && proc->executable->path.data) {
        pname = find_last_slash(proc->executable->path.data, proc->executable->path.length);
        pname_len = (const char *)proc->executable->path.data + proc->executable->path.length - pname;
    }
    char pname_esc[1024];
    if (pname) {
        escape_json_str(pname, pname_len, pname_esc, sizeof(pname_esc));
    } else {
        pname_esc[0] = '\0';
    }

    pid_t pid = proc ? audit_token_to_pid(proc->audit_token) : 0;

    char buf[16384];
    snprintf(buf, sizeof(buf),
        "{\"type\":\"open\",\"path\":\"%s\",\"flags\":%d,\"pid\":%d,\"process_name\":\"%s\",\"timestamp\":\"%s\"}",
        path_esc, ev->fflag, pid, pname_esc, ts);
    write_line(buf);
}

static void handle_uipc_connect(const es_message_t *msg) {
    char ts[32];
    write_timestamp(ts, sizeof(ts));

    const es_event_uipc_connect_t *ev = &msg->event.uipc_connect;
    if (!ev->file) return;

    const es_string_token_t *path_tok = &ev->file->path;
    char path_buf[4096];
    size_t path_len = path_tok->length < sizeof(path_buf) - 1 ? path_tok->length : sizeof(path_buf) - 1;
    memcpy(path_buf, path_tok->data, path_len);
    path_buf[path_len] = '\0';

    char path_esc[8192];
    escape_json_str(path_buf, path_len, path_esc, sizeof(path_esc));

    const es_process_t *proc = msg->process;
    const char *pname = NULL;
    size_t pname_len = 0;
    if (proc && proc->executable && proc->executable->path.data) {
        pname = find_last_slash(proc->executable->path.data, proc->executable->path.length);
        pname_len = (const char *)proc->executable->path.data + proc->executable->path.length - pname;
    }
    char pname_esc[1024];
    if (pname) {
        escape_json_str(pname, pname_len, pname_esc, sizeof(pname_esc));
    } else {
        pname_esc[0] = '\0';
    }

    pid_t pid = proc ? audit_token_to_pid(proc->audit_token) : 0;

    const char *protocol = (ev->type == SOCK_STREAM) ? "tcp" : "udp";

    char buf[16384];
    snprintf(buf, sizeof(buf),
        "{\"type\":\"connect\",\"pid\":%d,\"process_name\":\"%s\",\"remote_addr\":\"%s\",\"remote_port\":0,\"protocol\":\"%s\",\"timestamp\":\"%s\"}",
        pid, pname_esc, path_esc, protocol, ts);
    write_line(buf);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <socket_path>\n", argv[0]);
        return 1;
    }

    const char *socket_path = argv[1];

    @autoreleasepool {
        es_new_client_result_t result = es_new_client(&g_client, ^(es_client_t *client, const es_message_t *msg) {
            (void)client;
            if (!g_running) return;

            switch (msg->event_type) {
                case ES_EVENT_TYPE_NOTIFY_EXEC:
                    handle_exec(msg);
                    break;
                case ES_EVENT_TYPE_NOTIFY_OPEN:
                    handle_open(msg);
                    break;
                case ES_EVENT_TYPE_NOTIFY_UIPC_CONNECT:
                    handle_uipc_connect(msg);
                    break;
                default:
                    break;
            }
        });

        if (result != ES_NEW_CLIENT_RESULT_SUCCESS) {
            fprintf(stderr, "esf_helper: es_new_client failed: %d\n", (int)result);
            return 1;
        }

        const es_event_type_t events[] = {
            ES_EVENT_TYPE_NOTIFY_EXEC,
            ES_EVENT_TYPE_NOTIFY_OPEN,
            ES_EVENT_TYPE_NOTIFY_UIPC_CONNECT,
        };
        if (es_subscribe(g_client, events, sizeof(events) / sizeof(events[0])) != ES_RETURN_SUCCESS) {
            fprintf(stderr, "esf_helper: es_subscribe failed\n");
            es_delete_client(g_client);
            g_client = NULL;
            return 1;
        }

        unlink(socket_path);

        g_sock = socket(AF_UNIX, SOCK_STREAM, 0);
        if (g_sock < 0) {
            fprintf(stderr, "esf_helper: socket failed: %s\n", strerror(errno));
            es_delete_client(g_client);
            g_client = NULL;
            return 1;
        }

        struct sockaddr_un addr;
        memset(&addr, 0, sizeof(addr));
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);

        if (bind(g_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
            fprintf(stderr, "esf_helper: bind failed: %s\n", strerror(errno));
            close(g_sock);
            g_sock = -1;
            es_delete_client(g_client);
            g_client = NULL;
            return 1;
        }

        if (listen(g_sock, 1) < 0) {
            fprintf(stderr, "esf_helper: listen failed: %s\n", strerror(errno));
            close(g_sock);
            unlink(socket_path);
            g_sock = -1;
            es_delete_client(g_client);
            g_client = NULL;
            return 1;
        }

        dispatch_source_t sig_src = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGTERM, 0, dispatch_get_main_queue());
        dispatch_source_set_event_handler(sig_src, ^{
            g_running = 0;
            CFRunLoopStop(CFRunLoopGetCurrent());
        });
        dispatch_resume(sig_src);
        signal(SIGTERM, SIG_IGN);

        dispatch_source_t sig2_src = dispatch_source_create(DISPATCH_SOURCE_TYPE_SIGNAL, SIGINT, 0, dispatch_get_main_queue());
        dispatch_source_set_event_handler(sig2_src, ^{
            g_running = 0;
            CFRunLoopStop(CFRunLoopGetCurrent());
        });
        dispatch_resume(sig2_src);
        signal(SIGINT, SIG_IGN);

        int conn = accept(g_sock, NULL, NULL);
        if (conn < 0) {
            fprintf(stderr, "esf_helper: accept failed: %s\n", strerror(errno));
            close(g_sock);
            unlink(socket_path);
            es_delete_client(g_client);
            g_client = NULL;
            return 1;
        }
        close(g_sock);
        g_sock = conn;
        unlink(socket_path);

        CFRunLoopRun();
    }

    if (g_sock >= 0) {
        close(g_sock);
        g_sock = -1;
    }
    if (g_client) {
        es_delete_client(g_client);
        g_client = NULL;
    }

    return 0;
}
