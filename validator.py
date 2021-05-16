import argparse
import time

import logging
import datetime

import redis

import node_validation
from Node import Node
from cache_key import CACHE_KEY

SKIP_FOR_DOWN_NODE = 5  # Skip interval 5 times, and rescan down node

cache = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
logging.basicConfig(level=logging.INFO)


def validate_nodes(validate_down_node=False):
    cache_nodes = cache.smembers(CACHE_KEY['NODES_SET'])
    cache_nodes = list(cache_nodes)

    constructed_nodes = []
    for node in cache_nodes:
        constructed_nodes.append(Node(node.split(':')[0],node.split(':')[1]))
    up_nodes, down_nodes = node_validation.validate_node_list(constructed_nodes)

    if validate_down_node:
        cache_down_nodes = cache.smembers(CACHE_KEY['DOWN_NODE_SET'])
        cache_down_nodes = list(cache_down_nodes)
        constructed_down_nodes = []
        for node in cache_down_nodes:
            constructed_down_nodes.append(Node(node.split(':')[0], node.split(':')[1]))
        revalidated_down_node, _ = node_validation.validate_node_list(constructed_down_nodes)
        merged_up_node = list(set(up_nodes) | set(revalidated_down_node))
        up_nodes = merged_up_node

    for node in down_nodes:
        cache.sadd(CACHE_KEY['DOWN_NODE_SET'], node.ip+':'+str(node.port))
        cache.srem(CACHE_KEY['NODES_SET'], node.ip+':'+str(node.port))
    for node in up_nodes:
        cache.sadd(CACHE_KEY['NODES_SET'], node.ip + ':' + str(node.port))
        cache.srem(CACHE_KEY['DOWN_NODE_SET'], node.ip+':'+str(node.port))
    st = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    cache.set(CACHE_KEY['LAST_VALIDATE'], st)
    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Chia node connection validator')
    parser.add_argument('--interval', metavar='interval', type=int,
                        help='Validation Interval. Default to 15min', default=15)
    args = parser.parse_args()
    INTERVAL = args.interval * 60
    loop = 0
    while True:
        loop = loop + 1
        if loop == 5:
            logging.info("revalidating down node again...")
            validate_nodes(True)
            loop = 0
        else:
            validate_nodes(False)
        time.sleep(INTERVAL)