from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional

from chia.protocols.protocol_message_types import ProtocolMessageTypes
from chia.util.ints import uint8, uint16
from chia.util.streamable import Streamable, streamable

class NodeType(IntEnum):
    FULL_NODE = 1
    HARVESTER = 2
    FARMER = 3
    TIMELORD = 4
    INTRODUCER = 5
    WALLET = 6

@dataclass(frozen=True)
@streamable
class Message(Streamable):
    type: uint8  # one of ProtocolMessageTypes
    # message id
    id: Optional[uint16]
    # Message data for that type
    data: bytes


def make_msg(msg_type: ProtocolMessageTypes, data: Any) -> Message:
    return Message(uint8(msg_type.value), None, bytes(data))
