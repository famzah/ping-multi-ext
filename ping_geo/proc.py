from multiprocessing import Process
import os
import sys
import shlex
import prctl
import time
import signal
import select
import re

class Workflow:
    def __init__(self, hosts_data):
        self.debug = False
        self.hosts_data = hosts_data

    def child_process(self, cmdline, pipe_w, ppid):
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

    def start_process(self, cmdline):
        (pipe_r, pipe_w) = os.pipe()
        parent_pid = os.getpid()

        # Python runs only one thread at a time
        # so we should be safe to execute fork().
        # Once a process fork()'ed, by definition
        # parent threads are not inherited.
        pid = os.fork()
        if pid == 0:
            os.close(pipe_r)
            self.child_process(cmdline, pipe_w, parent_pid)
        else:
            os.close(pipe_w)

        return pid, pipe_r

    def start_all_processes(self):
        self.fd_lookup = {}

        for hostname in self.hosts_data:
            data = self.hosts_data[hostname]
            pid, pipe_r = self.start_process(data['proc']['cmdline'])
            data['proc']['pid'] = pid
            data['proc']['out_fd'] = pipe_r
            self.fd_lookup[pipe_r] = hostname

        self.exited_hosts = []

    def parse_line(self, line):
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

    def handle_pipes(self):
        fdlist = list(self.fd_lookup.keys())

        if not len(fdlist):
            time.sleep(0.05)
            if self.debug:
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
                self.exited_hosts.append(self.fd_lookup[fd])
            else:
                terminated = False
                s = s.decode('ascii', 'replace')

            all_s_parts = s.split('\n')

            s_ends_newline = s.endswith('\n')
            if s_ends_newline:
                all_s_parts.pop() # remove this empty line which shows that "s" ends in "\n"

            data = self.hosts_data[self.fd_lookup[fd]]
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
                        if self.debug:
                            print(data['raw'][-1])

                        if not terminated:
                            pd = self.parse_line(data['raw'][-1])
                            if pd is not None:
                                data['parsed'].append(pd)
                                if self.debug:
                                    print(f'PARSED: "{pd}"')

    def handle_exited_hosts(self):
        done_hostnames = []
        for hostname in self.exited_hosts:
            data = self.hosts_data[hostname]
            
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
                if self.debug:
                    print(data['raw'][-1])

        for hostname in done_hostnames:
            self.exited_hosts.remove(hostname)

    def update_hosts_data(self):
        self.handle_pipes()
        self.handle_exited_hosts()
