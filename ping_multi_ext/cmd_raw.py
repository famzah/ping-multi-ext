import ping_multi_ext.lib
import ping_multi_ext.core

def parse_argv():
    parser = ping_multi_ext.lib.argv_parser_base(
        'Execute multiple external ping commands at once.'
    )

    # non-required first

    dval = 1
    parser.add_argument('--timeout', type=float, default=dval,
        help=f'ping reply timeout in seconds; default={dval}')

    # required

    parser.add_argument('--ping', nargs=2, metavar=('UNIQUE_NAME', 'COMMAND'),
        action='append', required=True,
        help='each command must be specified by an arbitrary unique name and the command itself; ' +\
             'you can specify this option many times'
    )

    return vars(parser.parse_args())

def main():
    ping_multi_ext.core.main(parse_argv())
