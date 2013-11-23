# glied

import os
import select
import sys
import termios

from glie import btoi
from glie import AppError
import glie.cpr
import glie.crc
import glie.xpdr

TAG="glied"

# Global state (I'm sorry, Dad)
# XXX replace with an App class
our_lat = None      # None means unset
our_lon = None      # None means unset
our_alt = None      # None means unset

# Param

class ParamError(Exception):
    pass

class Param:
    def __init__(self, argv):
        skip = 0;  # Do skip=1 for full argv.
        #: GPS device path (no default, but commonly /dev/ttyS0 or /dev/gps)
        self.gps_dev_path = None
        #: GPS tty baud rate, default 4800
        self.gps_dev_speed = 4800
        #: Path to the rtl_adsb executible
        self.rtl_adsb_path = "/usr/bin/rtl_adsb"
        speed = 0
        for i in range(len(argv)):
            if skip:
                skip = 0
                continue
            arg = argv[i]
            if len(arg) != 0 and arg[0] == '-':
                if arg == "-g":
                    if i+1 == len(argv):
                        raise ParamError("Parameter -g needs an argument")
                    self.gps_dev_path = argv[i+1];
                    skip = 1;
                elif arg == "-r":
                    if i+1 == len(argv):
                        raise ParamError("Parameter -r needs an argument")
                    self.rtl_adsb_path = argv[i+1];
                    skip = 1;
                elif arg == "-s":
                    if i+1 == len(argv):
                        raise ParamError("Parameter -s needs an argument")
                    speed = argv[i+1];
                    skip = 1;
                else:
                    raise ParamError("Unknown parameter " + arg)
            else:
                raise ParamError("Parameters start with dashes")
        if self.gps_dev_path == None:
            raise ParamError("Mandatory parameter -g is missing")
        if self.rtl_adsb_path == None:
            raise ParamError("Mandatory parameter -r is missing")
        if speed != 0:
            try:
                self.gps_dev_speed = int(speed)
            except ValueError:
                raise ParamError("Invalid argument of parameter -s")

## Packing by hand is mega annoying, but oh well.
#def write_pidfile(fname):
#    try:
#        fd = os.open(fname, os.O_WRONLY|os.O_CREAT, stat.S_IRUSR|stat.S_IWUSR)
#    except OSError, e:
#        raise AppError(str(e))
#    flockb = struct.pack('hhllhh', fcntl.F_WRLCK, 0, 0, 0, 0, 0)
#    try:
#        fcntl.fcntl(fd, fcntl.F_SETLK, flockb)
#    except IOError:
#        # EAGAIN is a specific code for already-locked, but whatever.
#        raise AppError("Cannot lock %s" % fname)
#    if os.write(fd, "%u\n" % os.getpid()) < 1:
#        raise AppError("Cannot write %s" % fname)
#    try:
#        os.fsync(fd)
#    except IOError:
#        raise AppError("Cannot fsync %s" % fname)
#    # not closing the fd, keep the lock
#    return fd

def scatter_bits(hex_chunk):
    nibble_decoder_tab = {
        '0': '0000',
        '1': '0001',
        '2': '0010',
        '3': '0011',
        '4': '0100',
        '5': '0101',
        '6': '0110',
        '7': '0111',
        '8': '1000',
        '9': '1001',
        'a': '1010',
        'b': '1011',
        'c': '1100',
        'd': '1101',
        'e': '1110',
        'f': '1111'
    }
    ret_bits = ''
    while len(hex_chunk):
        nibble = hex_chunk[:1]
        try:
            ret_bits += nibble_decoder_tab[nibble]
        except KeyError:
            raise AppError("Invalid nibble '%s'" % nibble)
        hex_chunk = hex_chunk[1:]
    return ret_bits

# Connection

# Congratulations, you hand-rolled a yet another STEM dispatcher class.
# Surely there must be a standard way to do this (evetlet?) XXX.
class Connection:
    def __init__(self, sock):
        """
        :param sock: Notionally a socket, but maybe a file-like or anything,
                     as long as `recv_event` knows how to read from it.
        """
        self.sock = sock           #: sock from instance parameter
        self.state = 0
        self.mbufs = []
        self.rcvd = 0
    #def mark_login(self, username):
    #    self.state = 1
    #    self.user = username
    def mark_dead(self):
        self.state = 2
    def hup_proc(self):  # TODO
        raise NotImplementedError

# skb
# XXX split off into a module

def skb_pull_copy(mbufs, size):
    """
    Copy a bytearray of `size` bytes out of the list of strings `mbufs`.
    List remains unchanged.

    For now, do not requiest the size that is larger than the size available.

    :param mbufs: The list from which to pull
    :param size: How much to pull
    :returns: The pulled bytearray
    """
    v = bytearray(size)
    mx = 0
    x = 0
    done = 0
    while done < size:
       mbuf = mbufs[mx]
       steplen = size - done
       if len(mbuf) < steplen:
           steplen = len(mbuf)
       v[done:done+steplen] = mbuf[x:x+steplen]
       done += steplen
       x += steplen
       if x >= len(mbuf):
           x = 0
           mx += 1
    return v

def skb_pull(mbufs, size):
    """
    Pull the buffer of length `size` at the start of the list `mbufs`
    and remove the pulled buffer in order to permit repeated pull calls.

    :param mbufs: The list from which to pull
    :param size: How much to pull
    :returns: The pulled bytearray
    """
    v = bytearray(size)
    x = 0
    done = 0
    while done < size:
       mbuf = mbufs[0]
       steplen = size - done
       if len(mbuf) < steplen:
           steplen = len(mbuf)
       v[done:done+steplen] = mbuf[x:x+steplen]
       done += steplen
       x += steplen
       if x >= len(mbuf):
           x = 0
           mbufs.pop(0)
    if x != 0:
       mbuf = mbufs[0]	# unnecessary but feels safer
       mbufs[0] = mbuf[x:]
    return v

# event ADS-B

def recv_msg_adsb(msghex):
    msglen = len(msghex)
    if msglen != 14 and msglen != 28:
        print >>sys.stderr, TAG+": bad message length", msglen
        return

    msg = scatter_bits(msghex)

    df = msg[0:5]
    if df == '10001':      # DF17
        addr = msg[8:32]

        c_crc = glie.crc.esq_crc(msg[0:-24])
        a_crc = msg[-24:]
        if c_crc == a_crc:
            crc_status = "OK"
        else:
            x_crc = glie.crc.xor(addr, c_crc)
            if x_crc == a_crc:
                crc_status = "aOK"
            else:
                crc_status = "Error"

        ca = msg[5:8]
        if ca == '101':    # CA5
            typ = btoi(msg[32:37])
            if 9 <= typ <= 18:     # Airborne Position with barometric altitude
                qbit, alt = adsb_get_alt(msg)
                if alt is None:
                    alt = -1
                lat, lon = adsb_get_pos(msg)
                print "addr %x alt (Q=%d) %d lat %f lon %f CRC:%s" % \
                       (btoi(addr), qbit, alt, lat, lon, crc_status)
            elif typ == 19:        # Airborne Velocity
                # P3
                print " DF17 CA5 Type 19 CRC:%s" % (crc_status,)
            else:
                # P3
                print " DF17 CA5 Type", typ, "CRC:%s" % (crc_status,)
        else:
            # P3
            print " DF17 CA", btoi(ca), "CRC:%s" % (crc_status,)
    else:
        # P3
        print " DF", df, btoi(df)
    #print "message", msghex

# See Doc.9871 C.2.7 (Fig.C-1) at p247
def adsb_get_alt(msg):
    """
    :param msg: bit string of extended squitter for DF17
    :returns: tuple of integers (qbit, altitude), altitude is in feet;
              altitude may be None if msg is invalid
    """
    qbit = btoi(msg[47])
    if qbit:
        # [20:26][27:33] (bits M and Q removed)
        altstr = msg[40:47]+msg[48:52]
        alt = btoi(altstr) * 25 - 1000
    else:
        # Swap bits around, see Annex 10, 3.1.1.7.12.2.3
        # Squitter bit order:
        #    C1 A1 C2 A2 C4 A4 [no-M] B1 Q  B2 D2 B4 D4
        #    40 41 42 43 44 45        46 47 48 49 50 51
        # Transponder bit order:
        #    D2 D4 A1 A2 A4 B1 B2 B4 C1 C2 C4

        altstr = msg[49]+msg[51] + msg[41]+msg[43]+msg[45] + \
                 msg[46]+msg[48]+msg[50] + msg[40]+msg[42]+msg[44]
        try:
            alt = glie.xpdr.code_to_alt(altstr)
        except ValueError:
            return (0, None)
    return (qbit, alt)

# Doc.9871 A.2.3.2.3: Lat/Long take 2*17 bits, CPR-encoded per C.2.6 at p233
# 10s timer for combining odd/even
def adsb_get_pos(msg):
    if our_lat is None:
        return (0.0, 0.0)  # XXX return a proper sentiel or raise
    lat = glie.cpr.cpr_decode_lat(msg[53], msg[54:71], our_lat)
    lon = glie.cpr.cpr_decode_lon(msg[53], msg[71:88], lat, our_lon)
    return (lat, lon)

# Okay, this seems a little ad-hoc, but:
#  returns:
#    None - no more data to form any kind of packet
#    ""   - may be more data
#    buf  - parsed something and there may be more data
# Not sure how to code this pattern in an elegant way. Nested loops?
def recv_event_adsb_parse(conn):

    # Try to find a 56-bit packet first.
    if conn.rcvd < 16:
        return None
    buf = skb_pull_copy(conn.mbufs, 16)
    x = rtl_adsb_parser_find_start(buf)
    if x == -1:
        # Discard whole buffer
        buf = skb_pull(conn.mbufs, 16)
        conn.rcvd -= len(buf)
        return ""
    # Discard until the packet start
    if x != 0:
        buf = skb_pull(conn.mbufs, x)
        conn.rcvd -= len(buf)

    if conn.rcvd < 16:
        return None
    buf = skb_pull_copy(conn.mbufs, 16)
    x = rtl_adsb_parser_find_end(buf)
    if x != -1:
        buf = skb_pull(conn.mbufs, x)
        conn.rcvd -= len(buf)
        return buf[1:]

    # Well, 112 bits it is, then.
    if conn.rcvd < 31:
        return None
    buf = skb_pull_copy(conn.mbufs, 31)
    x = rtl_adsb_parser_find_end(buf)
    if x != -1:
        buf = skb_pull(conn.mbufs, x)
        conn.rcvd -= len(buf)
        return buf[1:]

    buf = skb_pull(conn.mbufs, 31)
    conn.rcvd -= len(buf)
    return ""

def rtl_adsb_parser_find_start(buf):
    p = str(buf)
    x = p.find("*")
    if x == -1:
        return -1
    if x != 0 and p[x-1] != '\n':  # ok for '\r\n' line terminators as well
        return -1
    return x

def rtl_adsb_parser_find_end(buf):
    p = str(buf)
    return p.find(";")

class AdsbConnection(Connection):

    # Receive an ADS-B message, using the low-level framing of "*xxxxxxxx;".
    def recv_event(self):
        conn = self
        # Always receive the socket data, or else the poll would loop.

        # Except that real sockets do not support .read(), thank you Guido
        #mbuf = self.sock.recv(4096)
        # Reading 4K does not return until filled
        #mbuf = self.sock.read(4096)
        # No size is even worse: never returns anything!
        #mbuf = self.sock.read()
        # A viable workaround: readline is responsive, albeit reading 1 byte at
        # a time through the OS interface. Of course it blocks until the whole
        # line is received.
        #mbuf = self.sock.readline()
        # Time to be brutal: just bypass the whole sorry bug-infested pile.
        mbuf = os.read(self.sock.fileno(), 4096)
        if mbuf == None:
            # This should not happen if poll() works correctly.
            raise AppError("Received None")
        if len(mbuf) == 0:
            # EOF - we do nothing and hope for a proper event in the main loop.
            return
        self.mbufs.append(mbuf)
        self.rcvd += len(mbuf)
        ## P3
        #print "mbuf %d rcvd %d" % (len(mbuf), self.rcvd)

        while 1:
            buf = recv_event_adsb_parse(self)
            if buf is None:
                break
            if len(buf) != 0:
                recv_msg_adsb(str(buf))

# event NMEA

def recv_msg_nmea(linestr):
    global our_alt, our_lat, our_lon

    words = linestr.split(',')
    # The first character is actually a framing protocol, most of the time '$'.
    # First two characters of the sentence tag form a "talker ID".
    # We assume 'GP' for now. Cound be 'IN' for panel GPS, or 'GN' for GLONASS.
    if words[0] == '$GPGGA':
        # The word looks like a float number, but it has degrees and minutes,
        # with degrees multiplied by 100. E.g. "3501.78" means 35 degrees,
        # 1 minute, and some seconds. The number of digits varies with GPS,
        # so we convert it like a float for simplicity, then use math.
        try:
            lat = float(words[2])
        except ValueError:
            return
        lat_deg = int(lat / 100.0)
        lat_min = lat % 100.0
        latf = float(lat_deg) + (lat_min / 60.0)
        if words[3] != 'N':
            latf *= -1

        try:
            lon = float(words[4])
        except ValueError:
            return
        lonf = float(int(lon / 100.0)) + ((lon % 100.0) / 60.0)
        if words[5] == 'W': lonf *= -1

        try:
            alt = float(words[9])
        except ValueError:
            return
        if words[10] == 'M':
            alt *= 3.28084

        our_alt = int(alt)
        our_lat = latf
        our_lon = lonf
    #elif words[0] == '$GPRMC':
    else:
        pass

class NmeaConnection(Connection):

    # Receive an NMEA message
    def recv_event(self):
        mbuf = os.read(self.sock.fileno(), 4096)
        # XXX sometimes throws:
        # OSError: [Errno 11] Resource temporarily unavailable
        if mbuf == None:
            raise AppError("Received None from GPS")
        if len(mbuf) == 0:
            return
        self.mbufs.append(mbuf)
        self.rcvd += len(mbuf)

        while 1:
            # This is correct if we assume that one pull splits an mbuf once.
            if len(self.mbufs) == 0:
                break
            mbuf = self.mbufs[-1]
            nlx = mbuf.find('\n')
            if nlx == -1:
                break
            line_length = self.rcvd - len(mbuf) + nlx + 1
            buf = skb_pull(self.mbufs, line_length)
            self.rcvd -= len(buf)
            ## P3
            #print "nmea line", buf
            recv_msg_nmea(str(buf))

        ## P3
        #print our_alt, our_lat, our_lon

# main()

def open_gps_tty(tty_path, tty_speed):
    if tty_speed == 4800:
        speed = termios.B4800
    elif tty_speed == 9600:
        speed = termios.B9600
    elif tty_speed == 115200:
        # Nobody should be crazy enough to run onboard RS-422 this fast.
        # We allow this because AV8OR has a firmware bug that makes it
        # clock 115200 after a sleep-resume. This way we don't need to
        # reboot the GPS each time a debugging sessing starts.
        speed = termios.B115200
    else:
        raise AppError("Speed %s is invalid" % str(tty_speed))
    # Must open with os.O_NONBLOCK in case DTR is not connected.
    fd = os.open(tty_path, os.O_RDONLY|os.O_NONBLOCK)
    # The parameters are a little convoluted, so we fetch an example,
    # then modify it to suit. We don't know an equivalent of cfmakeraw()
    # exists in Python (e.g. if tty.setraw() does everything necessary).
    # In any case, NMEA protocol is such that cooked mode suits us just fine.
    # Let's just kill echo, in case.
    ttyb = termios.tcgetattr(fd)
    ttyb[2] |= termios.CLOCAL
    ttyb[3] &= ~termios.ECHO
    ttyb[4] = ttyb[5] = speed
    termios.tcsetattr(fd, termios.TCSAFLUSH, ttyb)
    #  (void) fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) & ~O_NONBLOCK);
    return os.fdopen(fd, 'rb', 0)

def fork_rtl_adsb(prog_path):
    # Unfortunately, rtl_adsb conflicts with DVB kernel modules.
    # Fortunately, it produces a good printout in such case.
    # On Fedora, do this:
    #  echo 'blacklist dvb_usb_rtl28xxu' > /etc/modprobe.d/blacklist-dvb.conf
    # Elsewhere, do this:
    #  rmmod dvb_usb_rtl28xxu
    # We may want to document this in the future.

    (pipe_r, pipe_w) = os.pipe()

    # Replace with os.spawnv(os.P_NOWAIT, srv_path, args) for Windows
    prog_pid = os.fork()
    if prog_pid == 0:
        zero_r = os.open("/dev/null", os.O_RDONLY)
        os.dup2(zero_r, 0)
        os.close(pipe_r)
        os.dup2(pipe_w, 1)
        os.execv(prog_path, [prog_path, ])
        # We're likely to receive an OSError at this point but it costs nothing.
        raise AppError("Exec failed for %s" % prog_path)

    # global prog_pid
    # XXX somewhere at exit maybe
    # import signal
    # os.kill(prog_pid, signal.SIGTERM)

    os.close(pipe_w)
    # What's strange, if we do the os.fdopen() like below, without
    # os.O_NONBLOCK, then the resulting file-like object produces
    # non-blocking reads (seen with strace). Magic.
    return os.fdopen(pipe_r, 'rb', 0)

def do(par):

    # it's not like we really need the pidfile under the Systemd
    #pidfd = write_pidfile(par.pidfile)

    connections = {}
    poller = select.poll()

    #lsock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    #lsock.bind(par.usock)
    #lsock.listen(5)
    #poller.register(lsock.fileno(), select.POLLIN|select.POLLERR)

    asock = open_gps_tty(par.gps_dev_path, par.gps_dev_speed)
    conn = NmeaConnection(asock)
    connections[asock.fileno()] = conn
    poller.register(asock.fileno(), select.POLLIN|select.POLLERR)

    asock = fork_rtl_adsb(par.rtl_adsb_path)
    conn = AdsbConnection(asock)
    connections[asock.fileno()] = conn
    poller.register(asock.fileno(), select.POLLIN|select.POLLERR)

    # XXX drop privileges

    while 1:
        # XXX exit here if no more sockets or rtl_adsb pipe is down (EOF)

        # [(fd, ev)]
        events = poller.poll()
        for event in events:
            #if event[0] == lsock.fileno():
            #    (csock, caddr) = lsock.accept()
            #    conn = Connection(csock, tcp_client_event)
            #    connections[csock.fileno()] = conn
            #    poller.register(csock.fileno(), select.POLLIN|select.POLLERR)
            #    send_challenge(conn)
            #    continue

            fd = event[0]
            if connections.has_key(fd):
                conn = connections[fd]
                if event[1] & select.POLLNVAL:
                    poller.unregister(fd)
                    connections[fd] = None
                elif event[1] & select.POLLHUP:
                    poller.unregister(fd)
                    connections[fd] = None
                elif event[1] & select.POLLERR:
                    poller.unregister(fd)
                    connections[fd] = None
                elif event[1] & select.POLLIN:
                    conn.recv_event()
                    if conn.state == 2:
                        # XXX Call conn.hup_proc() here and everywhere
                        poller.unregister(fd)
                        connections[fd] = None
                else:
                    poller.unregister(fd)
                    connections[fd] = None
            else:
                print >>sys.stderr, TAG+": polled unknown fd", fd
                os.close(fd)

def main(args):
    try:
        par = Param(args)
    except ParamError as e:
        print >>sys.stderr, TAG+": Error in arguments:", e
        print >>sys.stderr, "Usage:", TAG+" -g /dev/ttyUSB0 [-s 4800]"+\
            " -r /usr/bin/rtl_adsb"
        return 1

    try:
        do(par)
    except AppError, e:
        print >>sys.stderr, TAG+":", e
        return 1
    # except AppTraceback as e:  -- NO
    except KeyboardInterrupt:
        # The stock exit code is also 1 in case of signal, so we are not
        # making it any worse. Just stubbing the traceback.
        return 1

    return 0

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
