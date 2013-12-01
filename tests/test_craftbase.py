#
# Run this simply with nosetests.

import testtools
import glie.craftbase

class TestCraftBase(testtools.TestCase):

    def test_target_basic(self):
        addr = "000100010001000100010001"
        tgt = glie.craftbase.Target(addr)
        tgt.locadd((0.1, 1, 0.0, 0.0))
        tgt.locadd((0.2, 2, 0.0, 0.0))
        self.assertEquals(len(tgt.locv), 2)
        self.assertEquals(tgt.loctop()[1], 2)

    def test_target_inverted(self):
        addr = "000100010001000100010001"
        tgt = glie.craftbase.Target(addr)
        tgt.locadd((0.2, 2, 0.0, 0.0))
        tgt.locadd((0.1, 1, 0.0, 0.0))
        self.assertEquals(len(tgt.locv), 2)
        self.assertEquals(tgt.loctop()[1], 2)

    def test_target_dedup(self):
        addr = "000100010001000100010001"
        tgt = glie.craftbase.Target(addr)
        tgt.locadd((0.0, 1, 0.0, 0.0))
        tgt.locadd((0.0, 2, 0.0, 0.0))
        self.assertEquals(len(tgt.locv), 1)