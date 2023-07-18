import argparse

from tornado.httpserver import HTTPServer
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop

from zvms.misc import logger
from zvms import app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=4000)
    args = parser.parse_args()

    wsgi = WSGIContainer(app)
    server = HTTPServer(wsgi)
    server.listen(args.port)
    logger.info('Server started')
    IOLoop.instance().start()