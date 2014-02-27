#
# Run this simply with nosetests.

import unittest
import glie.xpdr
import tools.xponder_gentab

class TestTransponder(unittest.TestCase):

    def test_lookup(self):
        alt = -1200
        for codestr in tools.xponder_gentab.all_d():
            alt_x = glie.xpdr.code_to_alt(codestr)
            self.assertEquals(alt, alt_x)
            alt += 100
        self.assertEquals(alt, 126800)

    def test_invalid(self):
        self.assertRaises(ValueError, glie.xpdr.code_to_alt, "")
        self.assertRaises(ValueError, glie.xpdr.code_to_alt, "@")
        self.assertRaises(ValueError, glie.xpdr.code_to_alt, "00000000000")
        self.assertRaises(ValueError, glie.xpdr.code_to_alt, "11111111111")
