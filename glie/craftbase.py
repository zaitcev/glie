#
# The list of known aircraft
# Copyright (c) 2013 Pete Zaitcev <zaitcev@yahoo.com>
#

import time

# Location tuple is:
#  (timestamp,   # seconds, float
#   altitude,    # feet, integer
#   latitude,    # degrees, float
#   longitude)   # degrees, float (west is negative)

# One aircraft. Or possibly an obstruction.
class Target(object):

    def __init__(self, addr):
        self.addr = addr      #: bitstr -- XXX is self-tagging even needed?
        self.locv = list()    #: sorted newest first

    def locadd(self, loc):
        tstamp = loc[0]
        x = 0
        print "loc", loc
        while x < len(self.locv):
            tstamp_x = self.locv[x][0]
            # With timestamps being floats, a comparison for equal is not
            # likely to fire, but let us be safe.
            if tstamp_x == tstamp:
                self.locv[x] = loc
                return
            if tstamp_x < tstamp:
                break
            x += 1
        # self.locv[x:x] = loc  # absolutely not: interpolates the tuple
        self.locv.insert(x, loc)
        return

    def locprune(self, duration):
        tstamp = time.time() - duration
        x = 0
        while x < len(self.locv):
            tstamp_x = self.locv[x][0]
            if self.locv[x][0] <= tstamp:
                self.locv = self.locv[0:x]
                break
            x += 1

    def loctop(self):
        if len(self.locv) == 0:  return None
        return self.locv[0]

# List of all Target-s.
class CraftBase(object):

    def __init__(self):
        self.a = dict()

    def update(self, addr, loc):
        # :param addr: bitstr
        # :param loc: (tstamp, alt, lat, lon)
        tgt = self.a.get(addr)
        if not tgt:
            tgt = Target(addr)
            self.a[addr] = tgt
        tgt.locadd(loc)

    def prune(self):
        raise NotImplementedError

    def dump(self):
        raise NotImplementedError
