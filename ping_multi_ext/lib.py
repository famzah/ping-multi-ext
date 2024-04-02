import argparse
import shlex
import ping_multi_ext # version

def statistics_list():
    return ['Last', 'Loss%', 'Avg', 'Min', 'Max', 'StDev', 'RX_cnt', 'TX_cnt', 'XX_cnt']

def argv_parser_base(prog_desc):
    parser = argparse.ArgumentParser(
        description=prog_desc
    )

    vstr = '{} {} | {}'.format(
        '%(prog)s', ping_multi_ext.version,
        'https://github.com/famzah/ping-multi-ext'
    )
    parser.add_argument('--version', action='version', version=vstr)

    dval = 0
    parser.add_argument('--hosts-max-width', type=int, default=dval,
        help=f'maximum width of the hosts column; default={dval}')

    dval = statistics_list()[0]
    parser.add_argument('-s,--stat', dest='stats_show_initially', choices=statistics_list(),
        default=dval,
        help=f'statistic to display initially; default={dval}')

    return parser

def remove_ssh_user(host):
    parts = host.split('@', 2)
    
    if len(parts) == 3:
        parts.pop(1)

    return '@'.join(parts)

def compose_ping_cmd(host, cmd_args):
    parts = host.split('@', 1)

    ping_cmd = 'ping -O -W {} -i {} {}'.format(
        shlex.quote(str(cmd_args['wait'])),
        shlex.quote(str(cmd_args['interval'])),
        shlex.quote(parts[0])
    )

    if len(parts) > 1:
        return 'ssh -o BatchMode=yes {} {}'.format(
            shlex.quote(parts[1]),
            shlex.quote(ping_cmd)
        )
    else:
        return ping_cmd
