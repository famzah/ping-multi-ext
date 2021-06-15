from multiprocessing import Process
import os
import sys
import shlex
from ctypes import cdll
import time
import signal
import select
import re
import traceback
import statistics

# /usr/include/linux/prctl.h
PR_SET_PDEATHSIG = 1

class Workflow:
    def __init__(self, hosts_data, timeout):
        self.debug = False
        self.hosts_data = hosts_data
        self.timeout = timeout

    def child_process(self, cmdline, ppid):
        # no effect for setuid or binaries with capabilities!
        errno = cdll['libc.so.6'].prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
        if errno != 0:
            raise Exception(f'prctl() failed with errno={errno}')
        if os.getppid() != ppid:
            raise Exception('Parent already terminated')

        os.close(0) # stdin

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
            # Make sure that we don't print anything to stdout/err from this uncontrolled child
            # because it confuses the fullscreen terminal.
            try:
                # Therefore, ensure that we first redirect stdout/err to the pipe.
                os.dup2(pipe_w, 1) # stdout
                os.dup2(pipe_w, 2) # stderr
                os.close(pipe_r)
            except:
                os._exit(254)
            # stdout/err are redirected; we can safely print() anything now
            try:
                # Only the following function must be in this try..except block
                # because we always peek 2 tracebacks back upon exception.
                self.child_process(cmdline, parent_pid)
            except:
                ex_type, ex_value, ex_traceback = sys.exc_info()
                (tb_file, tb_line, tb_func, tb_text) = traceback.extract_tb(ex_traceback)[2]
                print(f'Fatal error: {tb_func}(): {ex_type.__name__}: {ex_value}')
                os._exit(255)
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
        self.select_fdlist = list(self.fd_lookup.keys())

    def parse_time(self, line):
        line = line.strip()
        if not len(line):
            return None

        if re.search(r'^PING\s.+((bytes of data)|(data bytes))', line):
            return None

        m = re.search(r'^\d+\sbytes\sfrom\s.+\sttl=\d+\s+time=([\d\.]+)\sms$', line)
        if not m:
            res = '???'
        else:
            res = m.group(1)
            try:
                res = float(res)
                res = round(res)
            except:
                res = 'ERR' # this should never happen

        return res

    def parse_seq(self, line):
        m = re.search(r'\sicmp_seq=(\d+)(\s|$)', line)
        if m:
            return int(m.group(1))
        else:
            return None

    def parse_timeout(self, line):
        return re.search(r'^no answer yet for icmp_seq=\d+$', line)

    def handle_pipes(self, timeout):
        if not len(self.select_fdlist):
            time.sleep(0.05)
            if self.debug:
                print('== No active processes')
                time.sleep(1)
            return

        (fds_read_ready, _, _) = select.select(self.select_fdlist, [], [], timeout)
        for fd in fds_read_ready:
            s = os.read(fd, 1024 * 1024)

            if not len(s): # EOF
                terminated = True
                s = '\nCommand terminated.\n'
                self.select_fdlist.remove(fd)
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
                            seq = self.parse_seq(data['raw'][-1])

                            if seq is not None:
                                if data['seen_rx_seq'].get(seq):
                                    pd = self.parse_time(data['raw'][-1])
                                    if pd:
                                        # display the raw "time" value in the "Last" stats
                                        # even if it was marked as a timeout already
                                        data['stats']['Last'] = pd
                                    continue # we have already handled this "seq"
                                else:
                                    data['seen_rx_seq'][seq] = True

                            if seq is not None and seq > data['stats']['TX_cnt']:
                                data['stats']['TX_cnt'] = seq

                            is_timeout = self.parse_timeout(data['raw'][-1])

                            if is_timeout:
                                pd = '*'
                            else:
                                pd = self.parse_time(data['raw'][-1])

                            data['stats']['Last'] = pd
                            if pd is not None:
                                data['parsed'].append(pd)
                                if self.debug:
                                    print(f'PARSED: "{pd}"')

                            if type(pd) is int and pd < self.timeout * 1000:
                                data['stats']['RX_cnt'] += 1
                            data['stats']['XX_cnt'] = \
                                data['stats']['TX_cnt'] - data['stats']['RX_cnt']

                            if data['stats']['TX_cnt'] > 0:
                                data['stats']['Loss%'] = '{:.0f}%'.format(
                                    (1 - data['stats']['RX_cnt'] / data['stats']['TX_cnt']) * 100
                                )

                            points = list(filter(lambda x: type(x) is int, data['parsed']))
                            if len(points):
                                data['stats']['StDev'] = '{:.1f}'.format(statistics.pstdev(points))
                                data['stats']['Max'] = max(points)
                                data['stats']['Min'] = min(points)
                                data['stats']['Avg'] = round(sum(points) / len(points))

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
                data['proc']['pid'] = None
                data['raw'].append(f'== Process {term_reason}')
                data['parsed'].append('EXIT')
                if self.debug:
                    print(data['raw'][-1])

        for hostname in done_hostnames:
            self.exited_hosts.remove(hostname)

    def update_hosts_data(self, timeout):
        self.handle_pipes(timeout)
        self.handle_exited_hosts()
