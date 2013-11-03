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
        conn = FakeConn(['*','8d','a6','ee','56','58','a4','87','2d',
                         '164e3c8ec356;\r\n'])
        buf = glie.glied.recv_event_adsb_parse(conn)
        self.assertEquals(str(buf), '8da6ee5658a4872d164e3c8ec356')
