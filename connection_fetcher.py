import argparse
import logging
import os
import re
import requests
import subprocess
import time
from datetime import timedelta

from Node import Node

logging.basicConfig(level=logging.INFO)

LOG_REGEX = r'FULL_NODE\s((?:[0-9]{1,3}\.){3}[0-9]{1,3})\s*\d+\/(\d+).*?Height:\s*(\d+)'
BIN_ARGS = 'show --connections'


def fetch_connections(bin_folder, bin_exc_name):
    connections_table = subprocess.check_output(bin_folder + bin_exc_name + ' ' + BIN_ARGS, shell=True)
    output = str(connections_table)

    logging.debug('connections: ' + output)
    grouped_output = re.findall(LOG_REGEX, output)

    nodes = []
    for node_value in grouped_output:
        nodes.append(Node(node_value[0],
                          int(node_value[1]),
                          int(node_value[2])))
    logging.info('Got nodes: ' + str(nodes))
    return nodes
    pass


def post_validated_node_to_server(nodes, hostname):
    nodes_array = []
    for node in nodes:
        nodes_array.append({
            'ip': node.ip,
            'port': node.port,
            'block_height': node.block_height
        })
    try:
        req = requests.post(hostname + '/node', json={'nodes': nodes_array})
        if req.status_code != 200:
            logging.warning('Submit to upstream failed')
        else:
            logging.info('submitted to upstream')
    except requests.exceptions.ConnectTimeout as e:
        logging.error('connection timed out when submitting to upstream')
    except requests.exceptions.ConnectionError as e:
        logging.error('connection errored when submitting to upstream')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Chia node connection fetcher')
    parser.add_argument('--bin-folder', metavar='bin_folder', type=str,
                        help='Folder location of chia.exe/chia.', required=True)
    parser.add_argument('--server', metavar='server', type=str,
                        help='Upstream Server', required=True)
    parser.add_argument('--interval', metavar='interval', type=int,
                        help='Connection refresh interval in minutes', default=1)
    args = parser.parse_args()
    isWindows = os.name == 'nt'
    bin_name = '\\chia.exe' if isWindows else './chia'

    nodes = []

    while True:
        nodes = fetch_connections(args.bin_folder, bin_name)
        if len(nodes) != 0:
            post_validated_node_to_server(nodes, args.server)
        time.sleep(timedelta(minutes=args.interval).total_seconds())
