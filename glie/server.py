# glie-server
# Copyright (c) 2010-2012 OpenStack Foundation
# Copyright (c) 2013 Pete Zaitcev <zaitcev@yahoo.com>

import array
import errno
import io
import json
import math
import png
import sys
import time

import eventlet
from eventlet import GreenPool, sleep, wsgi, listen
from eventlet.green import socket

from ConfigParser import ConfigParser, NoSectionError, NoOptionError

from glie.utils import drop_privileges

W = 500
H = 500
#R = 20  # nm, so the drawn circle R=10nm
R = 40

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

#class NullLogger():
#    """A no-op logger for eventlet wsgi."""
#
#    def write(self, *args):
#        #"Logs" the args to nowhere
#        pass

class ConfigError(Exception):
    pass

def run_wsgi(conf_file, app_section):
    try:
        conf = loadconf(conf_file)
    except ConfigError as e:
        print >>sys.stderr, str(e)
        return 1

    sock = get_socket(conf)
    drop_privileges(conf.get('user', 'glie'))

    run_server(conf, sock)
    return 0

# This can be called directly, or after os.fork(), which we don't do yet.
def run_server(conf, sock):

    # eventlet.hubs.use_hub('select')
    eventlet.patcher.monkey_patch(all=False, socket=True)

    app = application

    env = { 'glie.state_file': conf.get('state_file', '/tmp/glie-out.json') }

    max_clients = int(conf.get('max_clients', '1024'))
    pool = RestrictedGreenPool(size=max_clients)
    try:
        #wsgi.server(sock, app, log=NullLogger(), custom_pool=pool)
        wsgi.server(sock, app, environ=env, custom_pool=pool)
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
        elif path == "/display.png":
            output = do_display(environ, start_response)
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

def do_display(environ, start_response):
    canvas = refresh_canvas(W, H, environ)

    fp = io.BytesIO()
    # b = fp.getvalue() -- specific method of BytesIO

    writer = png.Writer(W, H)
    writer.write(fp, canvas)

    fp.seek(0)
    start_response("200 OK", [('Content-type', 'image/png')])
    return fp

def refresh_canvas(width, height, environ):
    """
    Return the display canvas as a list of iteratables for PNG dumping.
    XXX You do know that Python has 2-dimentional arrays, don't you?
    """
    c = black_canvas(width, height)
    draw_white_circle(c, width/2, height/2, width/4)

    ## P3
    #draw_test_diamonds(c)

    read_state(c, width, height, environ['glie.state_file'])
    return c

def black_canvas(width, height):
    c = list()
    for i in xrange(height):
        row = list()
        for j in xrange(width):
            row.append(0)
            row.append(0)
            row.append(0)
        r = array.array('H')
        r.fromlist(row)
        c.append(r)
    return c

def read_state(c, width, height, state_file):
    """
    The main function: read the state dump and update the canvas.

    :param c: the canvas into which to render the situation
    :param state_file: the filename of the state dump
    """
    sfp = open(state_file, 'r')
    state = json.load(sfp)
    sfp.close()

    if 'alt' in state and 'lat' in state and 'lon' in state:
        draw_white_cross(c, width/2, height/2)
        draw_targets(c, width, height, state)
    else:
        draw_red_X(c, width/2, height/2)

def draw_targets(c, w, h, state):
    lat0 = state['lat']
    lon0 = state['lon']
    craftbase = state['cb']  # a dict, keys are addresses
    for addr in craftbase:
        tgt = craftbase[addr]
        locv = tgt['locv']   # a list, we rely on the order
        # In theory, the purging inside glied gets rid of targets if their
        # location lists shrink to nothing, but there's no harm in checking.
        if len(locv) == 0:
            continue
        loc = locv[0]
        trail = locv[1:]

        draw_target_diamond(c, w, h, state['alt'], lat0, lon0, loc)

        # Just a bunch of green dots for now. This is not awesome because
        # the targets do not seem to transmit at regular intervals and so
        # the density of dots does not correspond to the target's speed.
        for tloc in trail:
            y, x = loc_to_pix(h, w, lat0, lon0, tloc['lat'], tloc['lon'])
            if (0 <= y < h) and (0 <= x < w):
                color = (40, 255, 10)
                cy = c[y]
                cy[x*3 + 0] = color[0]
                cy[x*3 + 1] = color[1]
                cy[x*3 + 2] = color[2]

def draw_target_diamond(c, w, h, alt0, lat0, lon0, loc):
    """
    :param c: canvas
    :param w: width of canvas
    :param h: height of canvas
    :param alt0: our altitude in feet
    :param lat0: our latitude in degrees
    :param lon0: our longitude in degrees
    :param loc: target location dictionary with 'alt', 'lat', and 'lon'
    """
    y1, x1 = loc_to_pix(h, w, lat0, lon0, loc['lat'], loc['lon'])
    blt_sprite(c, w, h, x1 - diamond_0_ptx, y1 - diamond_0_pty,
               diamond_0_fig, diamond_0_width, (255, 180, 0))

def loc_to_pix(h, w, lat0, lon0, lat, lon):
    """
    :returns: tuple (y, x) for zero in upper left corner, integers
    """

    # Linear approximation works okay at the ranges of our application.
    # Same goes for meridian not being a circle.
    # equatorial circumference = 21638 nm
    # meridian circumference = 21602 nm

    dy = (lat - lat0) * 21602.0 / 360
    dx = (lon - lon0) * 21638.0 / 360
    dx *= math.cos(abs(lat0) * math.pi/180)

    # R is not a radius of any scale circle, but half of picture width.

    y = (dy / R) * -1.0 * (h/2) + h/2
    x = (dx / R) * (w/2) + w/2

    return (int(y), int(x))

def draw_white_cross(c, x0, y0):
    color = (243, 243, 243)
    cy = c[y0]
    for i in xrange(40):
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]
    for i in xrange(40):
        cy = c[y0 + i - 20]
        cy[x0*3 + 0] = color[0]
        cy[x0*3 + 1] = color[1]
        cy[x0*3 + 2] = color[2]

def draw_red_X(c, x0, y0):
    color = (255, 5, 5)
    for i in xrange(40):
        cy = c[y0 + i - 20]
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]
    for i in xrange(40):
        cy = c[y0 + 20 - i]
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]

def draw_white_circle(c, x0, y0, r):
    phy = 0
    # We place dots at each 2 degrees because a denser line looks awful
    # without a proper anti-aliasing.
    for i in xrange(180):
        phy = (float(i)/180.0) * (math.pi*2)
        x = x0 + int(r * math.sin(phy))
        y = y0 + int(r * math.cos(phy))
        if 0 <= x < len(c[0])/3 and 0 <= y < len(c):
            c[y][x*3 + 0] = 255
            c[y][x*3 + 1] = 255
            c[y][x*3 + 2] = 255
    return

# 0: empty diamond
# fig_height = 14
diamond_0_ptx = 3
diamond_0_pty = 6
diamond_0_width = 7
diamond_0_fig = [
     [16] ,
     [16] ,
     [40] ,
     [40] ,
     [68] ,
     [68] ,
     [130] ,
     [130] ,
     [68] ,
     [68] ,
     [40] ,
     [40] ,
     [16] ,
     [16]
]

## 1: bottom filled 2/5 diamond
## fig_height = 14
#diamond_1_width = 7
#diamond_1_fig = [
#     [16] ,
#     [16] ,
#     [40] ,
#     [40] ,
#     [68] ,
#     [68] ,
#     [130] ,
#     [130] ,
#     [68] ,
#     [124] ,
#     [56] ,
#     [56] ,
#     [16] ,
#     [16]
#]

#def draw_test_diamonds(c):
#    blt_sprite(c, W, H, 10, 10, diamond_0_fig, diamond_0_width, (255,255,255))
#    blt_sprite(c, W, H, 30, 10, diamond_1_fig, diamond_1_width, (255,255,255))
#    blt_sprite(c, W, H, -2, 17, diamond_1_fig, diamond_1_width, (30,30,255))
#    blt_sprite(c, W, H, 50, -3, diamond_0_fig, diamond_1_width, (30,30,255))

def blt_sprite(c, w, h, x0, y0, sprite, sprite_width, color):
    """
    Draw a sprite, using our "byte-packed" format. This is safe against
    drawing outside of the canvas, and can draw clipped as appropriate.

    :param sprite: list of lists of bytes, each byte of 8 bits
    """
    dy = 0
    for ll in sprite:
        dx = 0
        for byte in ll:
            for n in range(8):
                if dx >= sprite_width:
                    break
                if byte & 128:
                    set_color = color
                else:
                    set_color = (0, 0, 0)
                byte <<= 1

                if (0 <= y0 + dy < h) and (0 <= x0 + dx < w):
                    rv, gv, bv = set_color
                    cy = c[y0 + dy]
                    cy[(x0 + dx)*3 + 0] = rv
                    cy[(x0 + dx)*3 + 1] = gv
                    cy[(x0 + dx)*3 + 2] = bv

                dx += 1
        dy += 1

def loadconf(conf_file):
    section = 'DEFAULT'
    cfgpr = ConfigParser()
    try:
        cfp = open(conf_file, 'r')
    except IOError:
        raise ConfigError("Unable to open `%s'" % conf_file)
    try:
        cfgpr.readfp(cfp)
        ilist = cfgpr.items(section)
    except NoSectionError:
        raise ConfigError("Unable to read or find section `%s'" % section)
    except NoOptionError as e:
        raise ConfigError(str(e))
    conf = dict()
    for name, value in ilist:
        conf[name] = value
    return conf

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
