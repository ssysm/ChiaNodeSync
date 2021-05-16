class Node:
    def __init__(self, ip, port=8444, block_height=0):
        self.ip = ip
        self.port = port
        self.block_height = block_height

    def get_websocket_url(self):
        return 'wss://' + self.ip + ':' + str(self.port) + '/ws'

    def __repr__(self):
        return 'Node ' + self.ip + ':' + str(self.port) + '@' + str(self.block_height)