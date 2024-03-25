import ping_multi_ext.lib
import ping_multi_ext.core

def parse_argv():
    parser = ping_multi_ext.lib.argv_parser_base(
        'Ping all hosts from FILE and HOSTs.'
    )

    dval = 1
    parser.add_argument('-W,--wait', dest='wait', metavar='SECS', type=float, default=dval,
        help=f'timeout in seconds to wait for a ping reply; default={dval}')

    dval = 1
    parser.add_argument('-i,--interval', dest='interval', metavar='SECS', type=float, default=dval,
        help=f'time in seconds between sending each request; default={dval}')

    parser.add_argument('-f,--file', dest='file', metavar='FILE',
        help=f'read list of hosts from file')

    dval = 0
    parser.add_argument('--hosts-max-width', type=int, default=dval,
        help=f'maximum width of the hosts column; default={dval}')

    parser.add_argument('-s,--stat', dest='dstat', choices=['last', 'loss', 'avg', 'min', 'max', 'stdev', 'rx_cnt', 'tx_cnt', 'xx_cnt'],
        help=f'statistic to initially display')

    parser.add_argument('host', nargs='*',
        help='host to ping; you can specify this option many times')

    args = vars(parser.parse_args())

    if args['wait'] > args['interval']:
        parser.error('Argument "--wait={:.1f}" cannot be bigger than "--interval={:.1f}"'.format(
            args['wait'], args['interval']
        ))

    hosts = args['host'].copy()

    if args['file'] is not None:
        with open(args['file']) as f:
            for line in f:
                line = line.strip()

                if not len(line) or line.startswith('#'):
                    continue

                hosts.append(line)

    if not len(hosts):
        parser.error('No hosts were specified')

    ping_args = []
    for host in hosts:
        ping_args.append((
            ping_multi_ext.lib.remove_ssh_user(host),
            ping_multi_ext.lib.compose_ping_cmd(host, args),
        ))

    return {
        'timeout': args['wait'],
        'hosts_max_width': args['hosts_max_width'],
        'ping': ping_args,
        'dstat': args['dstat']
    }

def main():
    ping_multi_ext.core.main(parse_argv())
