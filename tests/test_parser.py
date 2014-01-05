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
