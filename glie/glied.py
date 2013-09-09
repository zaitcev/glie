# glied

import os
import select
import sys

from glie import btoi
import glie.xpdr

TAG="glied"

class AppError(Exception):
    pass

# Param

class ParamError(Exception):
    pass

class Param:
    def __init__(self, argv):
        skip = 0;  # Do skip=1 for full argv.
        #: GPS device path (no default, but commonly /dev/ttyS0 or /dev/gps)
        self.gps_dev_path = None
        #: Path to the rtl_adsb executible
        self.rtl_adsb_path = "/usr/bin/rtl_adsb"
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
                else:
                    raise ParamError("Unknown parameter " + arg)
            else:
                raise ParamError("Parameters start with dashes")
        if self.rtl_adsb_path == None:
            raise ParamError("Mandatory parameter -g is missing")

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
            raise AppErrorNibble(nibble)
        hex_chunk = hex_chunk[1:]
    return ret_bits

# Connection

# Congratulations, you hand-rolled a yet another STEM dispatcher class.
# Surely there must be a standard way to do this (evetlet?) XXX.
class Connection:
    def __init__(self, sock, recv_proc):
        """
        :param sock: Notionally a socket, but maybe a file-like or anything,
                     as long as `recv_proc` knows how to read from it.
        :param recv_proc: The procedure to call upon a receive event.
        """
        #self.challenge = None
        self.sock = sock           #: sock from instance parameter
        self.recv_proc = recv_proc #: recv_proc from instance parameter
        self.hup_proc = None       #: XXX TODO
        self.state = 0
        #self.user = None
        self.mbufs = []
        self.rcvd = 0
    #def mark_login(self, username):
    #    self.state = 1
    #    self.user = username
    def mark_dead(self):
        self.state = 2

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

# events

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

def recv_msg_adsb(conn, msghex):
    msg = scatter_bits(msghex)

    df = msg[0:5]
    if df == '10001':      # DF17
        ca = msg[5:8]
        if ca == '101':    # CA5
            addr = msg[8:32]
            typ = btoi(msg[32:37])
            if 9 <= typ <= 18:     # Airborne Position with barometric altitude
                # P3
                print " airpos msg", msg
                # See Doc.9871 C.2.7 (Fig.C-1)
                qbit = btoi(msg[47])
                if qbit:
                    # [20:26][27:33] (bits M and Q removed)
                    altstr = msg[40:47]+msg[48:52]
                    alt = btoi(altstr) * 25 - 1000
                    print "addr %x alt(Q=1) %d" % (btoi(addr), alt)
                else:
                    # Swap bits around, see Annex, 3.1.1.7.12.2.3
                    # Squitter bit order:
                    #    C1 A1 C2 A2 C4 A4 [no-M] B1 Q  B2 D2 B4 D4
                    #    40 41 42 43 44 45        46 47 48 49 50 51
                    # Transponder bit order:
                    #    D2 D4 A1 A2 A4 B1 B2 B4 C1 C2 C4

                    altstr = msg[49]+msg[51] + msg[41]+msg[43]+msg[45] + \
                             msg[46]+msg[48]+msg[50] + msg[40]+msg[42]+msg[44]
                    # XXX Trap KeyError here in case broadcast is invalid
                    alt = glie.xpdr.code_to_alt(altstr)
                    print "addr %x alt(Q=0) %d" % (btoi(addr), alt)
            elif typ == 19:          # Airborne Velocity
                # P3
                print " DF17 CA5 Type 19"
            else:
                # P3
                print " DF17 CA5 Type", typ
        else:
            # P3
            print " DF17 CA", ca, btoi(ca)
    else:
        # P3
        print " DF", df, btoi(df)
    #print "message", msghex

# Okay, this seems a little ad-hoc, but:
#  returns:
#    None - no more data to form any kind of packet
#    ""   - may be more data
#    buf  - parsed something and there may be more data
# Not sure how to code this pattern in an elegant way. Nested loops?
def recv_event_adsb_parse(conn):

    # Never seen a 56-bit packet thus far, but let's be prepared.
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
        return buf

    # Well, 112 bits it is, then.
    if conn.rcvd < 31:
        return None
    buf = skb_pull_copy(conn.mbufs, 31)
    x = rtl_adsb_parser_find_end(buf)
    if x != -1:
        buf = skb_pull(conn.mbufs, x)
        conn.rcvd -= len(buf)
        return buf

    buf = skb_pull(conn.mbufs, 31)
    conn.rcvd -= len(buf)
    # P3
    print "too long (%s)" % str(buf)
    return ""

# XXX do a class AdsbConnection(Connection): def recv_event(self), jeez
# Receive an ADS-B message, using the low-level framing of "*xxxxxxxx;".
def recv_event_adsb(conn):
    # Always receive the socket data, or else the poll would loop.
    # Except that real sockets do not support .read(), thank you Guido
    #mbuf = conn.sock.recv(4096)
    # Reading 4K does not return until filled
    #mbuf = conn.sock.read(4096)
    # No size is even worse: never returns anything!
    #mbuf = conn.sock.read()
    # A viable workaround: readline is responsive, albeit reading 1 byte at
    # a time through the OS interface.
    #mbuf = conn.sock.readline()
    # Time to be brutal: just bypass the whole sorry bug-infested pile.
    mbuf = os.read(conn.sock.fileno(), 4096)
    if mbuf == None:
        # Curious - does it happen? XXX
        raise AppError("Received None")
    if len(mbuf) == 0:
        # EOF - we do nothing and hope for a proper event in the main loop.
        return
    conn.mbufs.append(mbuf)
    conn.rcvd += len(mbuf)
    ## P3
    #print "mbuf %d rcvd %d" % (len(mbuf), conn.rcvd)

    while 1:
        buf = recv_event_adsb_parse(conn)
        if not buf:
            break
        recv_msg_adsb(conn, str(buf[1:-1]))

    return

def fork_rtl_adsb(prog_path):
    # XXX add rmmod

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

    # XXX drop privileges

    os.close(pipe_w)
    return os.fdopen(pipe_r, 'rb', 0)

# main()

def do(par):

    # it's not like we really need the pidfile under the Systemd
    #pidfd = write_pidfile(par.pidfile)

    connections = {}
    poller = select.poll()

    #lsock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    #lsock.bind(par.usock)
    #lsock.listen(5)
    #poller.register(lsock.fileno(), select.POLLIN|select.POLLERR)

    # XXX add GPS

    asock = fork_rtl_adsb(par.rtl_adsb_path)
    conn = Connection(asock, recv_event_adsb)
    connections[asock.fileno()] = conn
    poller.register(asock.fileno(), select.POLLIN|select.POLLERR)

    while 1:
        # XXX exit here is no more sockets or rtl_adsb pipe is down (EOF)

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
                    conn.recv_proc(conn)
                    if conn.state == 2:
                        # XXX Call conn.hup_proc() here and everywhere
                        poller.unregister(fd)
                        connections[fd] = None
                else:
                    poller.unregister(fd)
                    connections[fd] = None
            else:
                # P3
                print "UNKNOWN connection"

def main(args):
    try:
        par = Param(args)
    except ParamError as e:
        print >>sys.stderr, TAG+": Error in arguments:", e
        print >>sys.stderr, "Usage:", TAG+" -f image"
        sys.exit(1)

    try:
        do(par)
    except AppError, e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)
    except KeyboardInterrupt:
        # The stock exit code is also 1 in case of signal, so we are not
        # making it any worse. Just stubbing the traceback.
        sys.exit(1)

# http://utcc.utoronto.ca/~cks/space/blog/python/ImportableMain
if __name__ == "__main__":
    main(sys.argv[1:])
