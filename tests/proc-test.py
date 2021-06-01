#!/usr/bin/env python3

import ping_multi_ext.proc
import threading

hosts_data = {
    'aws.amazon.com': {
        'proc': {
            'cmdline': 'ssh root@dd ping -n aws.amazon.com',
        },
        'parsed': [''],
        'raw': [''],
        'raw_complete': False,
        'lock': threading.Lock(),
    },
    'google.com': {
        'proc': {
            'cmdline': 'ssh root@dd ping -n google.com',
        },
        'parsed': [''],
        'raw': [''],
        'raw_complete': False,
        'lock': threading.Lock(),
    },
    'google.com-typo': {
        'proc': {
            'cmdline': 'zssh root@dd ping -n google.comZZZ',
        },
        'parsed': [''],
        'raw': [''],
        'raw_complete': False,
        'lock': threading.Lock(),
    },
}

workflow = ping_multi_ext.proc.Workflow(hosts_data)
workflow.debug = True
workflow.start_all_processes()
while True:
    workflow.update_hosts_data(0.05)
