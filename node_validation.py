import asyncio
import logging
import traceback
from typing import Tuple

import websockets
import websockets.exceptions

from Node import Node
from chia.outbound_message import make_msg, NodeType, Message
from chia.protocols.protocol_message_types import ProtocolMessageTypes
from chia.protocols.shared_protocol import Handshake, protocol_version, Capability
from chia.ssl_context import ssl_context_for_server
from chia.util.ints import uint16, uint8


async def check_node_alive(node: Node) -> Tuple[bool, Node]:
    ssl_context = ssl_context_for_server('keys/chia_ca.crt', 'keys/chia_ca.key', 'keys/public_full_node.crt',
                                         'keys/public_full_node.key')
    try:
        # TODO: connect and timeout in one shot, don't do it in two connections
        await asyncio.wait_for(websockets.connect(node.get_websocket_url(), ssl=ssl_context), timeout=10)
        async with websockets.connect(node.get_websocket_url(), ssl=ssl_context) as websocket:
            handshake = make_msg(ProtocolMessageTypes.handshake, Handshake('mainnet',
                                                                           protocol_version,
                                                                           '0.0.0',
                                                                           uint16(8884),
                                                                           uint8(NodeType.INTRODUCER),
                                                                           [(uint16(Capability.BASE.value), '1')], ))
            encoded_handshake = bytes(handshake)
            await websocket.send(encoded_handshake)
            message = await websocket.recv()

            if message is None:
                logging.warning('Node ' + node.ip + ' did not return anything')
                return False, node
            full_message_loaded = Message.from_bytes(message)
            inbound_handshake = Handshake.from_bytes(full_message_loaded.data)
            await websocket.close()

            if inbound_handshake.network_id != 'mainnet':
                logging.warning('Node ' + node.ip + ' is not on main net but is on mainnet port!')
                return False, node

            logging.info('Node ' + node.ip + ' is up.')
            return True, node
    except websockets.exceptions.ConnectionClosed as e:
        logging.warning('Node closed the connection')
        return False, node
    except asyncio.exceptions.TimeoutError as e:
        logging.warning('Node timeout : ' + node.ip)
        return False, node
    except websockets.exceptions.InvalidMessage as e:
        return False, node
    except OSError as e:
        return False, node
    except Exception as e:
        logging.error(e)
        traceback.print_exc()
        return False, node


def validate_node_list(nodes):
    tasks = []
    for node_item in nodes:
        tasks.append(check_node_alive(node_item))

    loop = asyncio.get_event_loop()
    try:
        done = loop.run_until_complete(asyncio.gather(*tasks))
    except Exception as e:
        logging.error('validate failed')
        return None

    if done is None:
        logging.error('Validate loop finished but got nothing inside.')
        return None

    up_node = 0
    down_node = 0
    down_node_list = []
    for idx, (fut, node) in enumerate(done):
        if fut is False:
            down_node = down_node + 1
            down_node_list.append(node)
        else:
            up_node = up_node + 1
    for down_node_item in down_node_list:
        nodes.remove(down_node_item)
    logging.info('Up node: ' + str(up_node) + ', down node:' + str(down_node))
    logging.info('Validated up node:' + str(nodes))

    return nodes, down_node_list
