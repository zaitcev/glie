#
# Run this simply with nosetests.

from __future__ import print_function

import testtools
import glie.crc

class TestCRC(testtools.TestCase):

    def test_crc(self):

        def test(msg, poly, known):
            fcs = glie.crc.crc(msg, poly)
            if fcs == known:
                print('poly', poly, 'message', msg, 'CRC', fcs, ': OK')
                return True
            print('poly', poly, 'message', msg,
                  'computed CRC', fcs, 'known CRC', known, ': FAIL')
            return False

        result = True

        # Test by Shankar, UMD
        msg = '101110'
        tpoly = '1001'
        known = '011'
        result = test(msg, tpoly, known) and result

        # Test by Tanenbaum, Vrije U.
        msg = '1101011011'
        tpoly = '10011'
        known = '1110'
        result = test(msg, tpoly, known) and result

        ## Test from DF11 paper -- fails
        ## 20dab505:5ad35a
        #msg = '00100000'+'00000000'+'00000000'+'00000000'
        #msg = '00100000'+'11011010'+'10110101'+'00000101'
        #tpoly = glie.crc.sqpoly
        #known = '01011010'+'11010011'+'01011010'
        #result = test(msg, tpoly, known) and result

        # Test by Jetvision, 56 bits
        # 5D 3C6614 => C315D2
        msg = '01011101001111000110011000010100'
        tpoly = glie.crc.sqpoly
        known = '110000110001010111010010'
        result = test(msg, tpoly, known) and result

        # 8F 45AC52 60BDF348222A58 => B98284
        # Test by Jetvision, 112 bits
        msg = '10001111010001011010110001010010011000001011110111110011' + \
              '01001000001000100010101001011000'
        tpoly = glie.crc.sqpoly
        known = '101110011000001010000100'
        result = test(msg, tpoly, known) and result

        # Self-captured off air
        msg = '10001101101001101010011111011100010110001011100110000011' + \
              '00101010011110101010111010100000'
        tpoly = glie.crc.sqpoly
        known = '010000100110110101010010'
        result = test(msg, tpoly, known) and result

        self.assertTrue(result)
