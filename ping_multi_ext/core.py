from blessings import Terminal
import time
import threading
import sys
import curtsies
import signal
import random
import string
import math
import ping_multi_ext.proc
import ping_multi_ext.lib
from collections import deque
import os

gvars = {}

class TermCtrl:
    def __init__(self, key):
        self.code = getattr(gvars['term'], key)

def _compose_printed_str(data_row, t_width):
    printed_str = ''
    pstr_len = 0

    for part_idx, part_value in enumerate(data_row):
        if isinstance(part_value, TermCtrl):
            printed_str += part_value.code
        elif isinstance(part_value, str):
            if pstr_len + len(part_value) <= t_width:
                printed_str += part_value
                pstr_len += len(part_value)
            else: # we are going to exceed the width
                cut_value = part_value[0:(t_width - pstr_len)]

                printed_str += cut_value
                pstr_len += len(cut_value)

                break # stop processing the input data
        else:
            raise NotImplementedError(part_value)

    if pstr_len > t_width:
        raise Exception(f'Assertion failed: "{printed_str}"')

    return printed_str

def _sanity_check_data_row(data_row, i):
    for part_idx, part_value in enumerate(data_row):
        part_str_id = f'Screen data row with index {i} part {part_idx}'

        if not isinstance(part_value, str) and not isinstance(part_value, TermCtrl):
            raise ValueError(f'{part_str_id} is not "str" nor "TermCtrl"')
        if isinstance(part_value, str):
            for c in ['\n', '\r', '\t']:
                if c in part_value:
                    raise ValueError(
                        f'{part_str_id} cannot contain the ASCII character {ord(c)}: "{part_value}"'
                    )

def ui_print(term, data):
    # get it every time, so that we react if the terminal changes (ie. if it gets resized)
    t_height = term.height
    t_width = term.width

    term_size_changed = False
    if 'ui_old_size' not in gvars \
      or t_height != gvars['ui_old_size']['height'] or t_width != gvars['ui_old_size']['width']:
        #
        term_size_changed = True
        gvars['ui_old_size'] = {
            'height': t_height,
            'width': t_width,
        }

    if term_size_changed:
        print(term.clear(), end='', flush=True)
        if 'ui_old_screen' in gvars:
            del gvars['ui_old_screen']

    if 'ui_old_screen' not in gvars:
        gvars['ui_old_screen'] = {}
    old_screen = gvars['ui_old_screen']

    screen_changed = False
    for i in range(0, t_height):
        if i not in old_screen: # first initialization of "old_screen"
            old_screen[i] = None

        try:
            data_row = data[i]
        except IndexError:
            data_row = ['']

        _sanity_check_data_row(data_row, i)

        printed_str = _compose_printed_str(data_row, t_width)

        if printed_str != old_screen[i]: # this could be optimized to draw only a part of the line
            old_screen[i] = printed_str
            screen_changed = True
            # always restore the color to "normal" in case we cut this in _compose_printed_str()
            # always clear the line until the end in case we're printing something shorter now
            print(term.move(i, 0) + printed_str + term.normal + term.clear_eol, end='', flush=False)

    if screen_changed:
        sys.stdout.flush()

    return term_size_changed, t_height, t_width

def _get_display_value(raw_value):
    value_meta = set()
    if gvars['time_scale'][0] == 'success' or gvars['time_scale'][0] == 'numbered':
        try:
            int_v = int(raw_value)
        except:
            value_meta.add('error')
            added_value = raw_value.strip()[0:1] # get only the first character
            if added_value == '*': # timeout
                value_meta.add('timeout')
                if gvars['time_scale'][0] == 'success':
                    added_value = 'X'
                if gvars['time_scale'][0] == 'numbered':
                    added_value = '-'
            else:
                pass # use the symbol without modifications
        else:
            if gvars['time_scale'][0] == 'success':
                if int_v < gvars['cmd_args']['timeout'] * 1000:
                    added_value = '.'
                else:
                    added_value = 'X'
                    value_meta.add('timeout')
            elif gvars['time_scale'][0] == 'numbered':
                if int_v >= gvars['cmd_args']['timeout'] * 1000:
                    added_value = '-' # timeout
                    value_meta.add('timeout')
                elif int_v < 1000:
                    added_value = math.floor(int_v / 100)
                else:
                    added_value = '>' # unable to visualize with 0..9
            else:
                raise ValueError(gvars['time_scale'][0])
    elif gvars['time_scale'][0] == 'raw':
        if type(raw_value) is int:
            if raw_value >= gvars['cmd_args']['timeout'] * 1000:
                added_value = '*' # timeout
                value_meta.add('timeout')
            else:
                added_value = raw_value # normal value
        else: # non-int, which is an error
            added_value = raw_value
            value_meta.add('error')

        added_value = '{:>4} '.format(added_value)
    else:
        raise ValueError(gvars['time_scale'][0])

    added_value = str(added_value)

    return (added_value, value_meta)

def _compose_host_data_parsed_str(hostname, host_data, t_width, selected):
    row_parts = []
    row_parts_str_len = 0

    if selected:
        row_parts.append(TermCtrl('bold'))

    host_id_str = ('{:<' + str(gvars['config']['max_host_id_len']) + 's} ').format(
        hostname[0:gvars['config']['max_host_id_len']]
    )
    row_parts.append(TermCtrl('white')) # we will replace this on error
    row_parts_host_color_id = len(row_parts) - 1
    row_parts.append(host_id_str)
    row_parts.append(TermCtrl('white'))
    row_parts_str_len += len(host_id_str)

    s = ''
    with host_data['lock']:
        stats_val = host_data['stats'][gvars['stats_show'][0]]
        if stats_val is None:
            stats_val = ''

        stats_str = ('{:>6}  '.format(stats_val))
        row_parts.append(stats_str)
        row_parts_str_len += len(stats_str)

        for v_idx in range(1, len(host_data['parsed']) + 1):
            (added_value, value_meta) = _get_display_value(host_data['parsed'][-v_idx])

            if v_idx == 1 and 'error' in value_meta and len(added_value):
                row_parts[row_parts_host_color_id] = TermCtrl('red')

            if len(s) + len(added_value) > t_width - row_parts_str_len:
                break

            s += added_value
    row_parts.append(s)

    return row_parts

def _ui_render_all_hosts_data(
        screen_rows, all_hosts, host_data_type,
        min_idx, max_idx, sel_idx, sel_hostname, t_width
    ):
        if host_data_type == 'parsed':
            for idx, hostname in enumerate(list(gvars['hosts_print_order'])):
                if idx < min_idx:
                    continue
                if idx > max_idx:
                    continue

                screen_rows.append(_compose_host_data_parsed_str(
                    hostname, all_hosts[hostname],
                    t_width, sel_idx == idx
                ))
        elif host_data_type == 'raw':
            for idx, data_row in enumerate(list(all_hosts[sel_hostname]['raw'])):
                if idx < min_idx:
                    continue
                if idx > max_idx:
                    continue
                
                safe_s = str(data_row)
                for c in ['\n', '\r', '\t']:
                    safe_s = safe_s.replace(c, ' ')
                screen_rows.append(safe_s)
        else:
            raise NotImplementedError(host_data_type)

def _ui_render_header(screen_rows, cmd_err, host_data_type, sel_hostname):
    first_row = [
        'Keys: ',
    ]

    if host_data_type == 'parsed':
        first_row.extend([
            TermCtrl('bold'), '↑', TermCtrl('normal'),
            '/',
            TermCtrl('bold'), '↓', TermCtrl('normal'),
            '/',
            TermCtrl('bold'), 'Enter', TermCtrl('normal'),
            '/',
        ])

    first_row.extend([
        TermCtrl('bold'), 'PgUp', TermCtrl('normal'),
        '/',
        TermCtrl('bold'), 'PgDn', TermCtrl('normal'),
    ])

    if host_data_type == 'raw':
        first_row.extend([
            '/',
            TermCtrl('bold'), 'Home', TermCtrl('normal'),
            '/',
            TermCtrl('bold'), 'End', TermCtrl('normal'),
            '/',
            TermCtrl('bold'), 'ESC', TermCtrl('normal'),
        ])

    if host_data_type == 'parsed':
        first_row.extend([
            ' | ',
            TermCtrl('bold'), 'S', TermCtrl('normal'),
            'tats | ',
            TermCtrl('bold'), 'T', TermCtrl('normal'),
            'ime scale',
        ])

    first_row.extend([
        ' | ',
        TermCtrl('bold'), 'Q', TermCtrl('normal'), 'uit',
    ])

    screen_rows.append(first_row)

    if host_data_type == 'parsed':
        if gvars['time_scale'][0] == 'success':
            res_header = ['Ping results', TermCtrl('normal'), ' (success, newest first)']
        elif gvars['time_scale'][0] == 'numbered':
            res_header = ['Ping results', TermCtrl('normal'), ' (scaled per 100 ms, newest first)']
        elif gvars['time_scale'][0] == 'raw':
            res_header = ['Ping results', TermCtrl('normal'), ' (RTT, newest first)']
        else:
            raise ValueError(gvars['time_scale'][0])
        screen_rows.append(
            [
                TermCtrl('bold'),
                ('{:<' + str(gvars['config']['max_host_id_len']) + 's} ').format('Hostname'),
                ('{:>6s}  ').format(gvars['stats_show'][0])
            ] +\
            res_header
        )
    elif host_data_type == 'raw':
        screen_rows.append([TermCtrl('bold'), f'Raw ping results for "{sel_hostname}"'])
    else:
        raise NotImplementedError(host_data_type)

    # insert as second row (moving any other existing headers next)
    screen_rows.insert(1, cmd_err)

class DataScroller:
    def __init__(self, hosts_print_order, tail_mode_cap):
        self.hosts_print_order = hosts_print_order
        self.initialized = False
        self.tail_mode_cap = tail_mode_cap
    
    def set_data_items_count(self, n):
        self.data_items_count = n

    def set_avail_term_rows(self, n):
        self.avail_term_rows = n
        self.scroll_by = max(1, int(n / 2.0))

    def update_max_id(self):
        self.max_idx = min(
            self.min_idx + self.avail_term_rows - 1,
            self.data_items_count - 1
        )

    def reset(self):
        self.initialized = True
        self.in_tail_mode = self.tail_mode_cap

        self.min_idx = 0
        self.sel_idx = None
        self.update_max_id()

    def key_down(self):
        self.in_tail_mode = False
        if self.sel_idx is not None:
            self.sel_idx += 1
        if self.sel_idx is None or self.sel_idx > self.max_idx:
            self.sel_idx = self.min_idx

    def key_up(self):
        self.in_tail_mode = False
        if self.sel_idx is not None:
            self.sel_idx -= 1
        if self.sel_idx is None or self.sel_idx < self.min_idx:
            self.sel_idx = self.max_idx

    def key_pageup(self):
        self.in_tail_mode = False
        if self.min_idx > 0:
            self.min_idx -= self.scroll_by
            self.min_idx = self._align_value_to(self.min_idx, self.scroll_by)

            self.update_max_id()
            self.sel_idx = None

    def key_pagedown(self):
        self.in_tail_mode = False
        if self.max_idx < self.data_items_count - 1:
            self.min_idx += self.scroll_by
            self.update_max_id()
            self.sel_idx = None

        if self.max_idx == self.data_items_count - 1: # we're already at the very end
            if self.tail_mode_cap:
                self.in_tail_mode = True

    def key_home(self):
        self.reset()
        self.in_tail_mode = False

    def key_end(self):
        if self.tail_mode_cap:
            self.in_tail_mode = True

        self.max_idx = self.data_items_count - 1

        self.min_idx = max(0, self.max_idx - self.avail_term_rows + 1)
        self.min_idx = self._align_value_to(self.min_idx, self.scroll_by)

        self.update_max_id()
        self.sel_idx = None

    def tail(self):
        if not self.in_tail_mode:
            return

        self.max_idx = self.data_items_count - 1
        self.min_idx = max(0, self.max_idx - self.avail_term_rows + 1)
        self.sel_idx = None

    def key_enter(self):
        if self.sel_idx is None:
            return None

        self.in_tail_mode = False
        return self.hosts_print_order[self.sel_idx]

    def _align_value_to(self, src_value, aligned_to_value):
        return int(math.ceil(src_value / (aligned_to_value * 1.0)) * aligned_to_value)

def ui_renderer(all_hosts):
    term = gvars['term']

    if term.number_of_colors < 8:
        raise Exception('Your terminal does not support colors')

    with gvars['exit_fullscreen_lock']:
        gvars['exited_fullscreen'] = False
        print(term.enter_fullscreen())

    screen_rows = []
    cmd_err = ['']
    host_data_type = 'parsed'
    sel_hostname = None
    scroller_registry = {
        'parsed': DataScroller(gvars['hosts_print_order'], False),
        'raw': DataScroller(None, True),
    }
    switched_host_data_type = False

    with term.hidden_cursor():
        while not gvars['stop_run']:
            term_size_changed, t_height, t_width = ui_print(term, screen_rows)

            if not term_size_changed:
                time.sleep(0.05)

            screen_rows = []

            _ui_render_header(screen_rows, cmd_err, host_data_type, sel_hostname)

            scroller = scroller_registry[host_data_type]

            if host_data_type == 'parsed':
                scroller.set_data_items_count(len(gvars['hosts_print_order']))
            elif host_data_type == 'raw':
                scroller.set_data_items_count(len(all_hosts[sel_hostname]['raw']))
            else:
                raise NotImplementedError(host_data_type)

            if term_size_changed or not scroller.initialized:
                scroller.set_avail_term_rows(t_height - len(screen_rows)) # skip the header rows
                scroller.reset()

            if switched_host_data_type and host_data_type == 'raw':
                scroller.reset()

            scroller.update_max_id()

            switched_host_data_type = False
            with gvars['keys_pressed_lock']:
                while len(gvars['keys_pressed_list']):
                    key = gvars['keys_pressed_list'].pop(0)
                    cmd_err = ['']

                    min_idx_updated = False
                    if key == '<DOWN>' and host_data_type == 'parsed':
                        scroller.key_down()
                    elif key == '<UP>' and host_data_type == 'parsed':
                        scroller.key_up()
                    elif key == '<PAGEUP>':
                        scroller.key_pageup()
                    elif key == '<PAGEDOWN>':
                        scroller.key_pagedown()
                    elif key == '<HOME>':
                        scroller.key_home()
                    elif key == '<END>':
                        scroller.key_end()
                    elif key == '<ENTER>' and host_data_type == 'parsed':
                        sel_hostname = scroller.key_enter()
                        if sel_hostname is None:
                            cmd_err = [
                                TermCtrl('bold'), TermCtrl('red'),
                                'You need to select a row with the up and down arrows first',
                            ]
                        else:
                            host_data_type = 'raw'

                            switched_host_data_type = True
                            break # mandatory restart
                    elif key == '<ESC>':
                        if host_data_type == 'raw':
                            host_data_type = 'parsed'

                            switched_host_data_type = True
                            break # mandatory restart
                        else:
                            scroller.sel_idx = None
                    elif key == 's' and host_data_type == 'parsed':
                        gvars['stats_show'].rotate(-1)
                    elif key == 'S' and host_data_type == 'parsed':
                        gvars['stats_show'].rotate(1)
                    elif key == 't' and host_data_type == 'parsed':
                        gvars['time_scale'].rotate(-1)
                    elif key == 'T' and host_data_type == 'parsed':
                        gvars['time_scale'].rotate(1)
                    elif key.lower() == 'q':
                        gvars['stop_run'] = True
                    else:
                        if not all(c in string.printable for c in key):
                            # key = '0x' + binascii.hexlify(key.encode('ascii')).decode('ascii')
                            key = ''
                        else:
                            key = f' "{key}"'
                        cmd_err = [TermCtrl('bold'), TermCtrl('red'), f'Unknown key command{key}']

            if switched_host_data_type:
                continue # mandatory restart

            if host_data_type == 'raw':
                scroller.tail()

            if scroller.max_idx < 0:
                # terminal is so small that it doesn't have any space for data, or there
                # is no data
                continue

            _ui_render_all_hosts_data(
                screen_rows, all_hosts, host_data_type,
                scroller.min_idx, scroller.max_idx,
                scroller.sel_idx, sel_hostname, t_width
            )

    # only this thread and Exceptions print any info
    # therefore, it's this thread's task to exit full screen
    exit_fullscreen()

def _exit_fullscreen():
    if not gvars['exited_fullscreen']:
        gvars['exited_fullscreen'] = True
        print(gvars['term'].exit_fullscreen(), end='', flush=True)

def exit_fullscreen():
    if threading.current_thread() != gvars['ui_renderer_thread']: # avoid deadlock
        with gvars['exit_fullscreen_lock']:
            _exit_fullscreen()
    else: # ui_renderer_thread (the only thread which can set "exited_fullscreen = False"
        _exit_fullscreen()

def thread_runner(*args):
    try:
        func = args[0]
        func(*args[1:])
    except:
        gvars['stop_run'] = True

        if threading.current_thread() != gvars['ui_renderer_thread']:
            # this thread must exit very soon, because of the gvars['stop_run'] == False
            # wait for it to call exit_fullscreen(), so that we can successfully
            # print() the exception info
            gvars['ui_renderer_thread'].join(5) # best effort

        exit_fullscreen()
        raise # and print() the exception info

def stdin_processor():
    with curtsies.Input() as input_generator:
        while not gvars['stop_run']:
            e = input_generator.send(0.05)
            if e is None:
                continue # nothing pressed within the timeout period

            with gvars['keys_pressed_lock']:
                key = str(e)
                if key == '<Ctrl-j>':
                    key = '<ENTER>'

                gvars['keys_pressed_list'].append(key)

def sigint_handler(a, b):
    gvars['stop_run'] = True

def populate_hosts():
    ret = {}
    for hostname, cmd in gvars['cmd_args']['ping']:
        if hostname in ret:
            print(f'Error: Duplicate unique name: {hostname}', file=sys.stderr, flush=True)
            sys.exit(1)

        ret[hostname] = {
            'proc': {
                'cmdline': cmd,
                'pid': None,
            },
            'lock': threading.Lock(),
            'stats': {},
            'parsed': [''],
            'raw': [''],
            'raw_complete': False,
            'seen_rx_seq': {},
        }
        
        for k in gvars['stats_show']:
            if not k.endswith('_cnt'):
                ret[hostname]['stats'][k] = None
            else:
                ret[hostname]['stats'][k] = 0

        gvars['hosts_print_order'].append(hostname)

    max_hostname_len = len(max(gvars['hosts_print_order'], key=len))

    if gvars['config']['auto_max_host_id_len']: # fit as much as needed
        gvars['config']['max_host_id_len'] = max_hostname_len
    else:
        if max_hostname_len < gvars['config']['max_host_id_len']:
            # max len is within limits, so shrink limits
            gvars['config']['max_host_id_len'] = max_hostname_len

    if gvars['config']['max_host_id_len'] < len('Hostname'):
        gvars['config']['max_host_id_len'] = len('Hostname')

    return ret

def update_hosts_data():
    workflow = ping_multi_ext.proc.Workflow(gvars['proc_data'], gvars['cmd_args']['timeout'])
    workflow.start_all_processes()

    while not gvars['stop_run']:
        workflow.update_hosts_data(0.05)

def _global_pre_init():
    gvars['stats_show'] = deque(ping_multi_ext.lib.statistics_list())

    gvars['stats_show'].rotate(-1 * ping_multi_ext.lib.statistics_list().index(
        gvars['cmd_args']['stats_show_initially']
    ))

    gvars['config'] = {
        'auto_max_host_id_len': True,
        'max_host_id_len': 0,
    }

    if gvars['cmd_args']['hosts_max_width'] > 0:
        gvars['config']['auto_max_host_id_len'] = False
        gvars['config']['max_host_id_len'] = gvars['cmd_args']['hosts_max_width']

def _main():
    gvars['term'] = Terminal()

    gvars['stop_run'] = False

    gvars['keys_pressed_list'] = []
    gvars['keys_pressed_lock'] = threading.Lock()

    gvars['exited_fullscreen'] = True # by default we're not in this mode
    gvars['exit_fullscreen_lock'] = threading.Lock()

    gvars['time_scale'] = deque(['success', 'raw', 'numbered'])

    gvars['ui_renderer_thread'] = threading.Thread(name='ui_renderer', target=thread_runner, args=(
        ui_renderer, gvars['proc_data']
    ))

    thr_list = [
        gvars['ui_renderer_thread'],
        threading.Thread(name='stdin_processor', target=thread_runner, args=(stdin_processor,)),
        threading.Thread(name='update_hosts_data', target=thread_runner, args=(update_hosts_data,)),
    ]

    signal.signal(signal.SIGINT, sigint_handler) # CTRL+C

    for thr in thr_list:
        thr.start()

    while not gvars['stop_run']:
        time.sleep(0.05)

    while threading.active_count() > 1:
        for thr in thr_list:
            if thr.is_alive():
                thr.join()
        time.sleep(0.05)

    for host_data in gvars['proc_data'].values():
        if not host_data['proc']['pid']:
            continue
        try:
            os.kill(host_data['proc']['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass

def main(cmd_args):
    # Execute before we get into fullscreen mode.
    # This way we can easily print() anything and exit then.
    gvars['cmd_args'] = cmd_args
    gvars['hosts_print_order'] = []
    _global_pre_init()
    gvars['proc_data'] = populate_hosts()
    thread_runner(_main)
