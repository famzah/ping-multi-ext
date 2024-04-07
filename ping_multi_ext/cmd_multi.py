import ping_multi_ext.lib
import ping_multi_ext.core

def parse_argv():
    parser = ping_multi_ext.lib.argv_parser_base(
        'Ping all hosts from FILE and HOSTs.'
    )

    dval = 1
    parser.add_argument('-W', '--wait', dest='wait', metavar='SECS', type=float, default=dval,
        help=f'timeout in seconds to wait for a ping reply; default={dval}')

    dval = 1
    parser.add_argument('-i', '--interval', dest='interval', metavar='SECS', type=float, default=dval,
        help=f'time in seconds between sending each request; default={dval}')

    parser.add_argument('-f', '--file', dest='file', metavar='FILE',
        help=f'read list of hosts from file')

    dval = 600
    parser.add_argument('-L', '--count-limit', dest='count_limit', type=int, default=dval,
        help=f'limit the number of hosts; avoids unintended bulk actions; default={dval}')

    parser.add_argument('-C', '--cidr-debug', dest='cidr_debug', action='store_true',
        help=f'debug IPv4 CIDR expansion')

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

    hosts_new = []
    for host in hosts:
        try:
            hosts_new += ping_multi_ext.lib.expand_ipv4_network_to_hosts(host, args['cidr_debug'])
        except ping_multi_ext.lib.CidrDebugError as ex:
            parser.error('argument "{}": {}'.format(host, str(ex)))
    hosts = hosts_new
    del hosts_new

    if not len(hosts):
        parser.error('No hosts were specified')

    if len(hosts) > args['count_limit']:
        parser.error('Too many hosts specified ({}). You can increase the limit with -L/--count-limit.'.format(
            len(hosts)
        ))

    ping_args = []
    for host in hosts:
        ping_args.append((
            ping_multi_ext.lib.remove_ssh_user(host),
            ping_multi_ext.lib.compose_ping_cmd(host, args),
        ))

    return {
        'timeout': args['wait'],
        'hosts_max_width': args['hosts_max_width'],
        'stats_show_initially': args['stats_show_initially'],
        'ping': ping_args,
    }

def main():
    ping_multi_ext.core.main(parse_argv())
