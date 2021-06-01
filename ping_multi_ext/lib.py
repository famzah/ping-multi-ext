import argparse
import shlex
import ping_multi_ext # version

def argv_parser_base(prog_desc):
    parser = argparse.ArgumentParser(
        description=prog_desc
    )
    vstr = '{} {} | {}'.format(
        '%(prog)s', ping_multi_ext.version,
        'https://github.com/famzah/ping-multi-ext'
    )
    parser.add_argument('--version', action='version', version=vstr)

    return parser

def compose_ping_cmd(host, cmd_args):
    return 'ping -O -i {} {}'.format(
        shlex.quote(str(cmd_args['interval'])),
        shlex.quote(host)
    )

