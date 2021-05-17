import csv
import json

import logging
import os
import pathlib
import subprocess

import redis
from flask import Flask, request, jsonify, Response, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr

import geo_lookup
from Node import Node
from cache_key import CACHE_KEY

app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_ipaddr,
    storage_uri='redis://127.0.0.1:6379',
    default_limits=["60 per minute"],
    retry_after='3000'
)
cache = redis.Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
logging.basicConfig(level=logging.INFO)
isWindows = os.name == 'nt'
TTL_TIME = 5 * 60  # 5 Min


@app.route('/', methods=['GET'])
def get_index():
    return send_file('table.html')


@app.route('/nodes', methods=['GET'])
def get_nodes():
    is_include_block_height = request.args.get('block_height')
    is_include_geo = request.args.get('geoip')

    if is_include_block_height is None:
        is_include_block_height = False
    elif is_include_block_height == 'true' and is_include_geo != 'true':
        is_include_block_height = True
        is_include_geo = False
    elif is_include_block_height == 'true' and is_include_geo == 'true':
        is_include_block_height = True
        is_include_geo = True

    nodes = cache.smembers(CACHE_KEY['NODES_SET'])
    validated_at = cache.get(CACHE_KEY['LAST_VALIDATE'])
    nodes = list(nodes)

    if is_include_block_height == 'false':
        cached_result = cache.get(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'])
        if cached_result is None:
            cache.set(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'], json.dumps({'nodes': nodes,
                                                                      'validated_at': validated_at}))
            cache.expire(CACHE_KEY['NO_BLOCK_HEIGHT_CACHE'], TTL_TIME)
            return jsonify({
                'nodes': nodes,
                'validated_at': validated_at
            }), 200
        return Response(cached_result, mimetype='application/json')
    else:
        if is_include_geo:
            cached_result = cache.get(CACHE_KEY['BLOCK_HEIGHT_AND_GEO_CACHE'])
        else:
            cached_result = cache.get(CACHE_KEY['BLOCK_HEIGHT_CACHE'])
        if cached_result is None:
            updated_node_list = []
            for node in nodes:
                block_height = cache.get(CACHE_KEY['IP_CACHE'] + node.split(':')[0])
                current_node = Node(node.split(':')[0], int(node.split(':')[1]), block_height)
                node_dict = {
                    'ip': current_node.ip,
                    'port': str(current_node.port),
                    'block_height': str(current_node.block_height),
                }
                if is_include_geo:
                    geo_result = geo_lookup.lookup_node_country(current_node)
                    if geo_result is None:
                        node_dict['geo'] = {
                            'country': None,
                            'country_iso': None,
                            'continent': None,
                        }
                    else:
                        node_dict['geo'] = {
                            'country_iso': geo_result.country.iso_code,
                            'country': geo_result.country.name,
                            'continent': geo_result.continent.name
                        }
                updated_node_list.append(node_dict)

            cache.expire(CACHE_KEY['BLOCK_HEIGHT_CACHE'], TTL_TIME)
            if is_include_geo:
                cache.set(CACHE_KEY['BLOCK_HEIGHT_AND_GEO_CACHE'], json.dumps({'nodes': updated_node_list,
                                                                               'validated_at': validated_at}))
                cache.expire(CACHE_KEY['BLOCK_HEIGHT_AND_GEO_CACHE'], TTL_TIME)
            else:
                cache.set(CACHE_KEY['BLOCK_HEIGHT_CACHE'], json.dumps({'nodes': updated_node_list,
                                                                       'validated_at': validated_at}))
                cache.expire(CACHE_KEY['BLOCK_HEIGHT_CACHE'], TTL_TIME)
            return jsonify({
                'nodes': updated_node_list,
                'validated_at': validated_at
            }), 200
        return Response(cached_result, mimetype='application/json')


@app.route('/heatmap', methods=['GET'])
def get_node_heatmap():
    cached_result = cache.get(CACHE_KEY['BLOCK_HEIGHT_AND_GEO_CACHE'])
    heatmap_file = pathlib.Path('heatmap.png')
    if cached_result is None or not heatmap_file.exists():
        nodes = cache.smembers(CACHE_KEY['NODES_SET'])
        with open('geo_cache.csv', 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for node in nodes:
                current_node = Node(node.split(':')[0], int(node.split(':')[1]), 0)
                geo_result = geo_lookup.lookup_node_country(current_node)
                if geo_result is None:
                    continue
                country_lat_long = geo_lookup.convert_cc_to_latlong(geo_result.country.iso_code)
                csv_writer.writerow([country_lat_long['lat'], country_lat_long['long']])
            csvfile.close()
            if isWindows:
                sts = subprocess.Popen(
                    'venv/Scripts/python.exe heatmap/heatmap.py --filetype csv -o heatmap.png -k gaussian --osm '
                    '--zoom 3 -d 0.1 -B 0.4 '
                    'geo_cache.csv').wait()
            else:
                sts = subprocess.Popen('venv/bin/python heatmap/heatmap.py --filetype csv -k gaussian -o heatmap.png '
                                       '-d 0.1 -B 0.4 --osm --zoom '
                                       '3  geo_cache.csv', shell=True).wait()
            if sts != 0:
                return '', 204
    return send_file('heatmap.png')


@app.route('/node', methods=['POST'])
@limiter.limit("3/minute")
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


@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify(error="rate limit exceeded"), 429


if __name__ == '__main__':
    app.run()
