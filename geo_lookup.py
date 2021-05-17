import json

import geoip2.database
import geoip2.errors

from Node import Node

CC_LUT = json.loads(open('country_latlong_lut.json').read())

def lookup_node_country(node: Node):
    try:
        with geoip2.database.Reader('GeoLite2-Country.mmdb') as reader:
            response = reader.country(node.ip)
            return response
    except FileNotFoundError as e:
        return None
    except geoip2.errors.AddressNotFoundError as e:
        return None


def convert_cc_to_latlong(country_iso: str):
    normalized_name = country_iso.lower()
    return CC_LUT[normalized_name]