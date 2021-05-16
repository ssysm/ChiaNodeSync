import json

import logging
import redis
from flask import Flask, request, jsonify, Response

from cache_key import CACHE_KEY

app = Flask(__name__)
cache = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
logging.basicConfig(level=logging.INFO)
TTL_TIME = 10 * 60  # 10 Min

@app.route('/nodes', methods=['GET'])
def get_nodes():
    is_include_block_height = request.args.get('block_height')
    if is_include_block_height is None:
        is_include_block_height = False
    if is_include_block_height == 'true':
        is_include_block_height = True

    nodes = cache.smembers(CACHE_KEY['NODES_SET'])
    nodes = list(nodes)

    if is_include_block_height == 'false':
        cached_result = cache.get(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'])
        if cached_result is None:
            cache.set(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'], json.dumps({'nodes': nodes}))
            cache.expire(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'], TTL_TIME)
            return jsonify({
                'nodes': nodes
            }), 200
        return Response(cached_result, mimetype='application/json')
    else:
        cached_result = cache.get(CACHE_KEY['BLOCK_HEIGHT_CACHE'])
        if cached_result is None:
            updated_node_list = []
            for node in nodes:
                block_height = cache.get(CACHE_KEY['IP_CACHE'] + node.split(':')[0])
                updated_node_list.append({
                    'ip': node.split(':')[0],
                    'port': node.split(':')[1],
                    'block_height': str(block_height)
                })
            cache.set(CACHE_KEY['BLOCK_HEIGHT_CACHE'], json.dumps({'nodes': updated_node_list}))
            cache.expire(CACHE_KEY['BLOCK_HEIGHT_CACHE'], TTL_TIME)
            return jsonify({
                'nodes': updated_node_list
            }), 200
        return Response(cached_result, mimetype='application/json')


@app.route('/node', methods=['POST'])
def add_nodes():
    json_data = request.json
    if json_data['nodes'] is None:
        return jsonify(err='No Nodes'), 400

    for node in json_data['nodes']:
        if node['ip'] is None or node['port'] is None:
            return jsonify(err='No IP or port'), 400
        cache.sadd(CACHE_KEY['NODES_SET'], node['ip'] + ':' + str(node['port']))
        if node['block_height']:
            cache.set(CACHE_KEY['IP_CACHE'] + node['ip'], node['block_height'])

    return jsonify(err='No Error'), 200


if __name__ == '__main__':
    app.run()
