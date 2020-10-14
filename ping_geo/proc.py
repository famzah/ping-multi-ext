from multiprocessing import Process
import os
import sys
import shlex
import prctl
import time
import signal
import select

def child_process(cmdline, pipe_w, ppid):
    prctl.set_pdeathsig(signal.SIGTERM) # no effect for setuid or binaries with capabilities!
    if os.getppid() != ppid:
        print('ERROR: Parent already terminated', file=sys.stderr, flush=True)
        os._exit(255)

    os.close(0) # stdin
    os.dup2(pipe_w, 1) # stdout
    os.dup2(pipe_w, 2) # stderr

    args = shlex.split(cmdline)
    os.execvp(args[0], args)
    # never returns

def start_process(cmdline):
    (pipe_r, pipe_w) = os.pipe()
    parent_pid = os.getpid()

    # Python runs only one thread at a time
    # so we should be safe to execute fork().
    # Once a process fork()'ed, by definition
    # parent threads are not inherited.
    pid = os.fork()
    if pid == 0:
        os.close(pipe_r)
        child_process(cmdline, pipe_w, parent_pid)
    else:
        os.close(pipe_w)

    return pid, pipe_r

def start_all_processes(hosts_data):
    fd_lookup = {}
    for hostname in hosts_data:
        data = hosts_data[hostname]
        pid, pipe_r = start_process(data['proc']['cmdline'])
        data['proc']['pid'] = pid
        data['proc']['out_fd'] = pipe_r
        fd_lookup[pipe_r] = hostname
    return fd_lookup

def handle_pipes(hosts_data, fd_lookup, fdlist, exited_hosts):
    (fds_read_ready, _, _) = select.select(fdlist, [], [], 0.05)
    for fd in fds_read_ready:
        s = os.read(fd, 1024 * 1024)
        if not len(s): # EOF
            s = '\nCommand terminated.\n'
            fdlist.remove(fd)
            exited_hosts.append(fd_lookup[fd])
        else:
            s = s.decode('ascii', 'replace')

        all_s_parts = s.split('\n')

        s_ends_newline = s.endswith('\n')
        if s_ends_newline:
            all_s_parts.pop() # remove this empty line which shows that "s" ends in "\n"

        data = hosts_data[fd_lookup[fd]]
        with data['lock']:
            for idx, part in enumerate(all_s_parts): # all we have left here is real data
                if idx != len(all_s_parts) - 1: # not last element
                    newline = True # all non-last elements ended in "\n" and were split
                else: # last element
                    newline = s_ends_newline

                if not data['raw_complete']: # last line didn't end with "\n"
                    data['raw'][-1] += part # append to the existing line
                else: # last line was ended with "\n"
                    data['raw'].append(part) # start a new line

                data['raw_complete'] = newline

def update_hosts_data(hosts_data, fd_lookup):
    fdlist = list(fd_lookup.keys())
    exited_hosts = []

    while True:
        handle_pipes(hosts_data, fd_lookup, fdlist, exited_hosts)
