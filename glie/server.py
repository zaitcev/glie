# glie-server
# Copyright (c) 2010-2012 OpenStack Foundation
# Copyright (c) 2013 Pete Zaitcev <zaitcev@yahoo.com>

import errno
import time

import eventlet
from eventlet import GreenPool, sleep, wsgi, listen
from eventlet.green import socket

from glie.utils import drop_privileges


class RestrictedGreenPool(GreenPool):
    """
    Works the same as GreenPool, but if the size is specified as one, then the
    spawn_n() method will invoke waitall() before returning to prevent the
    caller from doing any other work (like calling accept()).
    """
    def __init__(self, size=1024):
        super(RestrictedGreenPool, self).__init__(size=size)
        self._rgp_do_wait = (size == 1)

    def spawn_n(self, *args, **kwargs):
        super(RestrictedGreenPool, self).spawn_n(*args, **kwargs)
        if self._rgp_do_wait:
            self.waitall()


class NullLogger():
    """A no-op logger for eventlet wsgi."""

    def write(self, *args):
        #"Logs" the args to nowhere
        pass


def run_wsgi(conf_file, app_section):

    # It's pretty much inevitable that we'll need a configuration eventually.
    # Leave a stub for now.
    # conf = appconfig(conf_file, name=app_section)
    conf = {}

    sock = get_socket(conf)
    drop_privileges(conf.get('user', 'glie'))

    run_server(conf, sock)
    return 0

# This can be called directly, or after os.fork(), which we don't do yet.
def run_server(conf, sock):

    # eventlet.hubs.use_hub('select')
    eventlet.patcher.monkey_patch(all=False, socket=True)

    app = application

    max_clients = int(conf.get('max_clients', '1024'))
    pool = RestrictedGreenPool(size=max_clients)
    try:
        #wsgi.server(sock, app, log=NullLogger(), custom_pool=pool)
        wsgi.server(sock, app, custom_pool=pool)
    except socket.error as err:
        if err[0] != errno.EINVAL:
            raise
    pool.waitall()

class AppError(Exception):
    pass
class App400Error(Exception):
    pass
class App404Error(Exception):
    pass
class AppGetError(Exception):
    pass

def application(environ, start_response):
    path = environ['PATH_INFO']

    try:
        if path == None or path == "" or path == "/":
            output = do_root(environ, start_response)
        else:
            # output = do_user(environ, start_response, path)
            raise App404Error("Only / exists")
        return output

    except AppError as e:
        start_response("500 Internal Error", [('Content-type', 'text/plain')])
        return [safestr(unicode(e)), "\r\n"]
    except App400Error as e:
        start_response("400 Bad Request", [('Content-type', 'text/plain')])
        return ["400 Bad Request: %s\r\n" % safestr(unicode(e))]
    except App404Error as e:
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return [safestr(unicode(e)), "\r\n"]
    except AppGetError as e:
        start_response("405 Method Not Allowed",
                       [('Content-type', 'text/plain'), ('Allow', 'GET')])
        return ["405 Method %s not allowed\r\n" % safestr(unicode(e))]

def do_root(environ, start_response):
    method = environ['REQUEST_METHOD']
    if method != 'GET':
        raise AppGetError(method)

    start_response("200 OK", [('Content-type', 'text/plain')])
    return ["Glie\r\n"]

def get_socket(conf, default_port='80'):
    """Bind socket to bind ip:port in conf

    :param conf: Configuration dict to read settings from
    :param default_port: port to use if not specified in conf

    :returns : a socket object as returned from socket.listen
    """
    bind_addr = (conf.get('bind_host', '0.0.0.0'),
                 int(conf.get('bind_port', default_port)))
    address_family = [addr[0] for addr in socket.getaddrinfo(
        bind_addr[0], bind_addr[1], socket.AF_UNSPEC, socket.SOCK_STREAM)
        if addr[0] in (socket.AF_INET, socket.AF_INET6)][0]
    sock = None
    bind_timeout = int(conf.get('bind_timeout', 30))
    retry_until = time.time() + bind_timeout
    while not sock and time.time() < retry_until:
        try:
            sock = listen(bind_addr, backlog=int(conf.get('backlog', '4096')),
                          family=address_family)
        except socket.error as err:
            if err.args[0] != errno.EADDRINUSE:
                raise
            sleep(0.1)
    if not sock:
        raise Exception(_('Could not bind to %s:%s '
                          'after trying for %s seconds') % (
                              bind_addr[0], bind_addr[1], bind_timeout))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # in my experience, sockets can hang around forever without keepalive
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    if hasattr(socket, 'TCP_KEEPIDLE'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 600)
    return sock

def safestr(u):
    if isinstance(u, unicode):
        return u.encode('utf-8')
    return u
