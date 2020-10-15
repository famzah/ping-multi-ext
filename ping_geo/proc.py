from multiprocessing import Process
import os
import sys
import shlex
import prctl
import time
import signal
import select
import re

debug = False

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

def parse_line(line):
    line = line.strip()
    if not len(line):
        return None

    if re.search(r'^PING\s.+bytes of data', line):
        return None

    m = re.search(r'^\d+\sbytes\sfrom\s.+\sttl=\d+\s+time=([\d\.]+)\sms$', line)
    if not m:
        res = '???'
    else:
        res = m.group(1)

    return '{:>4}'.format(res)

def handle_pipes(hosts_data, fd_lookup, fdlist, exited_hosts):
    if not len(fdlist):
        time.sleep(0.05)
        if debug:
            print('== No active processes')
            time.sleep(1)
        return

    (fds_read_ready, _, _) = select.select(fdlist, [], [], 0.05)
    for fd in fds_read_ready:
        s = os.read(fd, 1024 * 1024)

        if not len(s): # EOF
            terminated = True
            s = '\nCommand terminated.\n'
            fdlist.remove(fd)
            exited_hosts.append(fd_lookup[fd])
        else:
            terminated = False
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

                if newline:
                    if debug:
                        print(data['raw'][-1])

                    if not terminated:
                        pd = parse_line(data['raw'][-1])
                        if pd is not None:
                            data['parsed'].append(pd)
                            if debug:
                                print(f'PARSED: "{pd}"')

def handle_exited_hosts(exited_hosts, hosts_data):
    done_hostnames = []
    for hostname in exited_hosts:
        data = hosts_data[hostname]
        
        einfo = os.waitid(os.P_PID, data['proc']['pid'], os.WEXITED | os.WNOHANG)
        if einfo is None: # child not completely exited, yet
            continue

        done_hostnames.append(hostname)

        if einfo.si_code == os.CLD_EXITED:
            term_reason = f'exited with status {einfo.si_status}'
        else:
            term_reason = f'killed by signal {einfo.si_status}' # (si_code={einfo.si_code})

        with data['lock']:
            data['raw'].append(f'== Process {term_reason}')
            data['parsed'].append('EXIT')
            if debug:
                print(data['raw'][-1])

    for hostname in done_hostnames:
        exited_hosts.remove(hostname)

def update_hosts_data(hosts_data, fd_lookup):
    fdlist = list(fd_lookup.keys())
    exited_hosts = []

    while True:
        handle_pipes(hosts_data, fd_lookup, fdlist, exited_hosts)
        handle_exited_hosts(exited_hosts, hosts_data)
