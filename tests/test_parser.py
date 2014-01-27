#
# Run this simply with nosetests.

import testtools
import glie.glied

class FakeConn(object):
    def __init__(self, mbufs):
        self.mbufs = mbufs
        self.rcvd = sum([len(mbuf) for mbuf in mbufs])

class TestParser(testtools.TestCase):

    def test_no1(self):
        conn = FakeConn([b'*',b'8d',b'a6',b'ee',b'56',b'58',b'a4',b'87',b'2d',
                         b'164e3c8ec356;\r\n'])
        buf = glie.glied.recv_event_adsb_parse(conn)
        self.assertEquals(buf, b'8da6ee5658a4872d164e3c8ec356')

    def test_no2(self):
        conn = FakeConn([b"bcfb8a39672738;\r\n",
                         b"*", b"c6", b"d5", b"af", b"36", b"4c", b"a2",
                         b"a44b4002141d747b;\r\n*8dab5e6c58b9"])
        buf = glie.glied.recv_event_adsb_parse(conn)
        self.assertEquals(buf, b'')
        buf = glie.glied.recv_event_adsb_parse(conn)
        self.assertEquals(buf, b'c6d5af364ca2a44b4002141d747b')
