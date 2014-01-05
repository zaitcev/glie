#
# This program takes no arguments and simply calculates a table of
# transponder values, then dumps it to the standard output.
#

from __future__ import print_function

TAG="xponder_gentab"

import sys

tab_c = [ "001", "011", "010", "110", "100" ]
tab_a = [ "000", "001", "011", "010", "110", "111", "101", "100" ]
tab_d = [ "00", "01", "11", "10" ]

def all_c(back):
    if back:
        for cx in range(len(tab_c), 0, -1):
            yield tab_c[cx-1]
    else:
        for cx in range(len(tab_c)):
            yield tab_c[cx]

def all_b(back):
    if back:
        for bx in range(len(tab_a), 0, -1):
            for c_str in all_c(bx % 2):
                yield tab_a[bx-1] + c_str
    else:
        for bx in range(len(tab_a)):
            for c_str in all_c(bx % 2):
                yield tab_a[bx] + c_str

def all_a(back):
    if back:
        for ax in range(len(tab_a), 0, -1):
            for b_str in all_b(ax % 2):
                yield tab_a[ax-1] + b_str
    else:
        for ax in range(len(tab_a)):
            for b_str in all_b(ax % 2):
                yield tab_a[ax] + b_str

def all_d():
    for dx in range(len(tab_d)):
        for a_str in all_a(dx % 2):
            yield tab_d[dx] + a_str

def main(args):
    argc = len(args)
    if argc != 1:
        print("Usage: "+TAG, file=sys.stderr)
        sys.exit(1)

    alt = -1200
    for val in all_d():
        # Bit order is D2,D4, A1,A2,A4, B1,B2,B4, C1,C2,C4.
        print("%6s" % str(alt), val[0:2], val[2:5], val[5:8], val[8:11])
        alt += 100

if __name__ == '__main__':
    main(sys.argv)
