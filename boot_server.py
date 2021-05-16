from gevent.pywsgi import WSGIServer
from server import app
if __name__ == '__main__':
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()