# glie-server
# Copyright (c) 2010-2012 OpenStack Foundation
# Copyright (c) 2013 Pete Zaitcev <zaitcev@yahoo.com>

from __future__ import print_function

import array
import errno
import io
import json
import math
import png  # the dj11's pypng
import sys
import time

#from six.moves.BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
# <--- "No module named 'six.moves.BaseHTTPServer'; six.moves is not a package"
try:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from ConfigParser import ConfigParser, NoSectionError, NoOptionError
except ImportError:
    from configparser import ConfigParser, NoSectionError, NoOptionError

from glie.utils import drop_privileges

W = 500
H = 500
#R = 20  # nm, so the drawn circle R=10nm
R = 40

#class NullLogger():
#    """A no-op logger for eventlet wsgi."""
#
#    def write(self, *args):
#        #"Logs" the args to nowhere
#        pass

class ConfigError(Exception):
    pass

def run_wrapper(conf_file, app_section):
    try:
        conf = loadconf(conf_file, app_section)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        return 1

    server_address = (conf.get('bind_host', '0.0.0.0'),
                      int(conf.get('bind_port', '80')))

    username = conf.get('user', 'glie')
    state_file = conf.get('state_file', '/tmp/glie-out.json')
    # max_clients = int(conf.get('max_clients', '1024'))
    # backlog = int(conf.get('backlog', '4096'))

    # sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    # if hasattr(socket, 'TCP_KEEPIDLE'):
    #     sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 600)

    httpd = Server(server_address, Handler,
                   username=username, state_file=state_file)
    httpd.serve_forever()

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
        return [safestr(str(e)), "\r\n"]
    except App400Error as e:
        start_response("400 Bad Request", [('Content-type', 'text/plain')])
        return [safestr("400 Bad Request: %s\r\n" % str(e))]
    except App404Error as e:
        start_response("404 Not Found", [('Content-type', 'text/plain')])
        return [safestr(str(e)), "\r\n"]
    except AppGetError as e:
        start_response("405 Method Not Allowed",
                       [('Content-type', 'text/plain'), ('Allow', 'GET')])
        return [safestr("405 Method `%s' not allowed\r\n" % str(e))]

def do_root(environ, start_response):
    method = environ['REQUEST_METHOD']
    if method != 'GET':
        raise AppGetError(method)

    start_response("200 OK", [('Content-type', 'text/plain')])
    return [safestr("Glie\r\n")]

def do_display(environ, start_response):
    canvas = refresh_canvas(W, H, environ)

    fp = io.BytesIO()
    # b = fp.getvalue() -- specific method of BytesIO

    writer = png.Writer(canvas.w, canvas.h)
    writer.write(fp, canvas.c)

    fp.seek(0)
    start_response("200 OK", [('Content-type', 'image/png')])
    return fp

class Server(HTTPServer):
    allow_reuse_address = 1

    def __init__(self, server_address, RequestHandlerClass, **kwargs):
        self.username = kwargs['username']
        self.state_file = kwargs['state_file']
        del kwargs['username']
        del kwargs['state_file']
        HTTPServer.__init__(self, server_address, RequestHandlerClass, **kwargs)

    def server_activate(self):
        HTTPServer.server_activate(self)
        drop_privileges(self.username)

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # We emulate WSGI in case we ever decide to go back.

        resp = [500, "Internal Error", {'Content-Type': "text/plain"}]

        def start_response(_status, _headers):
            _status_list = _status.split(' ', 1)
            resp[0] = int(_status_list[0])
            if len(_status_list) > 1:
                resp[1] = _status_list[1]
            else:
                resp[1] = None
            resp[2] = _headers

        environ = { 'REQUEST_METHOD': 'GET', 'PATH_INFO': self.path,
                    'glie.state_file': self.server.state_file }

        body = application(environ, start_response)

        status, message, headers = resp
        if message:
            self.send_response(status, message)
        else:
            self.send_response(status)
        for header in headers:
            self.send_header(header[0], header[1])
        self.end_headers()
        for chunk in body:
            self.wfile.write(chunk)

class Canvas(object):
    def __init__(self, width, height):
        c = list()
        for i in range(height):
            row = list()
            for j in range(width):
                row.append(0)
                row.append(0)
                row.append(0)
            r = array.array('H')
            r.fromlist(row)
            c.append(r)
        self.c = c
        self.w = width
        self.h = height

def refresh_canvas(width, height, environ):
    """
    Return the display canvas as a list of iteratables for PNG dumping.
    XXX You do know that Python has 2-dimentional arrays, don't you?
    """
    c = Canvas(width, height)
    draw_white_circle(c, width//2, height//2, width//4)

    #draw_test_diamonds(c)

    read_state(c, width, height, environ['glie.state_file'])
    return c

def read_state(c, width, height, state_file):
    """
    The main function: read the state dump and update the canvas.

    :param c: the canvas into which to render the situation
    :param state_file: the filename of the state dump
    """
    try:
        sfp = open(state_file, 'r')
    except IOError:
        draw_red_X(c, width//2, height//2)
        return
    state = json.load(sfp)
    sfp.close()

    if 'alt' in state and 'lat' in state and 'lon' in state:
        draw_white_cross(c, width//2, height//2)
        draw_targets(c, state)
    else:
        draw_red_X(c, width//2, height//2)

def draw_targets(canvas, state):
    w = canvas.w
    h = canvas.h
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

        # Just a bunch of green dots for now. This is not awesome because
        # the targets do not seem to transmit at regular intervals and so
        # the density of dots does not correspond to the target's speed.
        for tloc in trail:
            y, x = loc_to_pix(h, w, lat0, lon0, tloc['lat'], tloc['lon'])
            if (0 <= y < h) and (0 <= x < w):
                color = (40, 255, 10)
                cy = canvas.c[y]
                cy[x*3 + 0] = color[0]
                cy[x*3 + 1] = color[1]
                cy[x*3 + 2] = color[2]

        # Drawing a ghost with the same diamond for simplicity.
        if float(loc['ts']) >= float(state['now']) - 5.0:
            color = (255, 180, 0)
        else:
            color = (40, 255, 10)
        draw_target_diamond(canvas, state['alt'], lat0, lon0, loc, color)

def draw_target_diamond(canvas, alt0, lat0, lon0, loc, color):
    """
    :param canvas: canvas into which to draw
    :param alt0: our altitude in feet
    :param lat0: our latitude in degrees
    :param lon0: our longitude in degrees
    :param loc: target location dictionary with 'alt', 'lat', and 'lon'
    """

    alt = loc['alt']
    if alt0 - 1100 <= alt <= alt0 + 1100:
        diamond_fig = diamond_3_fig
        diamond_width = diamond_3_width
    elif alt0 - 3000 <= alt < alt0:
        diamond_fig = diamond_2_fig
        diamond_width = diamond_2_width
    elif alt < alt0:
        diamond_fig = diamond_1_fig
        diamond_width = diamond_1_width
    elif alt0 < alt <= alt0 + 3000:
        diamond_fig = diamond_4_fig
        diamond_width = diamond_4_width
    else:
        diamond_fig = diamond_5_fig
        diamond_width = diamond_5_width

    y1, x1 = loc_to_pix(canvas.h, canvas.w, lat0, lon0, loc['lat'], loc['lon'])

    blt_sprite(canvas, x1 - diamond_ptx, y1 - diamond_pty,
               diamond_fig, diamond_width, color)

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

def draw_white_cross(canvas, x0, y0):
    color = (243, 243, 243)
    cy = canvas.c[y0]
    for i in range(40):
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]
    for i in range(40):
        cy = canvas.c[y0 + i - 20]
        cy[x0*3 + 0] = color[0]
        cy[x0*3 + 1] = color[1]
        cy[x0*3 + 2] = color[2]

def draw_red_X(canvas, x0, y0):
    color = (255, 5, 5)
    for i in range(40):
        cy = canvas.c[y0 + i - 20]
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]
    for i in range(40):
        cy = canvas.c[y0 + 20 - i]
        cy[(x0 + i - 20)*3 + 0] = color[0]
        cy[(x0 + i - 20)*3 + 1] = color[1]
        cy[(x0 + i - 20)*3 + 2] = color[2]

def draw_white_circle(canvas, x0, y0, r):
    c = canvas.c
    phy = 0
    # We place dots at each 2 degrees because a denser line looks awful
    # without a proper anti-aliasing.
    for i in range(180):
        phy = (float(i)/180.0) * (math.pi*2)
        x = x0 + int(r * math.sin(phy))
        y = y0 + int(r * math.cos(phy))
        if 0 <= x < len(c[0])//3 and 0 <= y < len(c):
            cy = c[y]
            cy[x*3 + 0] = 255
            cy[x*3 + 1] = 255
            cy[x*3 + 2] = 255
    return

# All diamonds have a common center point.
diamond_ptx = 3
diamond_pty = 6

# Much lower
diamond_1_width = 7
diamond_1_fig = [
     [16] , [16] , [40] , [40] , [68] , [68] , [130] ,
     [130] , [68] , [68] , [56] , [56] , [16] , [16]
]

# Below
diamond_2_width = 7
diamond_2_fig = [
     [16] , [16] , [40] , [40] , [68] , [68] , [130] ,
     [130] , [124] , [124] , [56] , [40] , [16] , [16]
]

# Coalt
diamond_3_width = 7
diamond_3_fig = [
     [16] , [16] , [40] , [56] , [124] , [124] , [254] ,
     [254] , [124] , [124] , [56] , [40] , [16] , [16]
]

# Above
diamond_4_width = 7
diamond_4_fig = [
     [16] , [16] , [40] , [56] , [124] , [124] , [130] ,
     [130] , [68] , [68] , [40] , [40] , [16] , [16]
]

# Much higher
diamond_5_width = 7
diamond_5_fig = [
     [16] , [16] , [56] , [56] , [68] , [68] , [130] ,
     [130] , [68] , [68] , [40] , [40] , [16] , [16]
]

#def draw_test_diamonds(c):
#    blt_sprite(c, 10, 10, diamond_1_fig, diamond_1_width, (255,255,255))
#    blt_sprite(c, 30, 10, diamond_2_fig, diamond_2_width, (255,255,255))
#    blt_sprite(c, 50, 10, diamond_3_fig, diamond_3_width, (255,255,255))
#    blt_sprite(c, 70, 10, diamond_4_fig, diamond_4_width, (255,255,255))
#    blt_sprite(c, 90, 10, diamond_5_fig, diamond_5_width, (255,255,255))

def blt_sprite(canvas, x0, y0, sprite, sprite_width, color):
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

                if (0 <= y0 + dy < canvas.h) and (0 <= x0 + dx < canvas.w):
                    rv, gv, bv = set_color
                    cy = canvas.c[y0 + dy]
                    cy[(x0 + dx)*3 + 0] = rv
                    cy[(x0 + dx)*3 + 1] = gv
                    cy[(x0 + dx)*3 + 2] = bv

                dx += 1
        dy += 1

def loadconf(conf_file, section):
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

def safestr(u):
    try:
        if isinstance(u, unicode):
            return u.encode('utf-8')
    except NameError:
        # Python 3
        if isinstance(u, str):
            return u.encode('utf-8')
    return u
