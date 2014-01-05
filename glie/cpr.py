#
# Compact Position Reporting
# Copyright (c) 2013 Pete Zaitcev <zaitcev@yahoo.com>
#
# See Annex 10 Chapter IV for generics.
# Doc 9871 (DO-260B) has packet layouts and formulas.

import math
from glie import btoi
from glie import AppError

## pi = 3.14159265359
#NZ = 15
#for NL in range(2, 4*NZ):
#    lat = 180.0/math.pi * math.acos(
#                           math.sqrt((1.0 - math.cos(math.pi/(2*NZ)))/
#                                     (1.0 - math.cos((2*math.pi)/NL))))
#    print NL, lat
zonetab = [
  -1.0,
  90.0,          #  1 zone from 87.000001 to the pole
  87.0,          #  2 zones up to and including 87.0
  86.5353699751, #  3
  85.7554162094, #  4
  84.891661907,  #  5
  83.9917356298, #  6
  83.0719944472, #  7
  82.1395698051, #  8
  81.1980134927, #  9
  80.2492321328, # 10
  79.2942822546, # 11
  78.3337408292, # 12
  77.3678946133, # 13
  76.3968439079, # 14
  75.4205625665, # 15
  74.4389341573, # 16
  73.4517744167, # 17
  72.4588454473, # 18
  71.4598647303, # 19
  70.4545107499, # 20
  69.4424263114, # 21
  68.4232202208, # 22
  67.3964677408, # 23
  66.3617100838, # 24
  65.3184530968, # 25
  64.2661652257, # 26
  63.2042747938, # 27
  62.1321665921, # 28
  61.0491777425, # 29
  59.9545927669, # 30
  58.8476377615, # 31
  57.7274735387, # 32
  56.5931875621, # 33
  55.443784445,  # 34
  54.2781747227, # 35
  53.095161528,  # 36
  51.8934246917, # 37
  50.6715016555, # 38
  49.4277643926, # 39
  48.160391281,  # 40
  46.867332525,  # 41
  45.5462672266, # 42
  44.1945495142, # 43
  42.8091401224, # 44
  41.3865183226, # 45
  39.9225668433, # 46
  38.4124189241, # 47
  36.8502510759, # 48
  35.228995978,  # 49
  33.539934363,  # 50
  31.7720970768, # 51
  29.9113568573, # 52
  27.9389871012, # 53
  25.8292470706, # 54
  23.5450448656, # 55
  21.029394926,  # 56
  18.1862635707, # 57
  14.8281743687, # 58
  10.4704713 ]   # 59 zones in the equatorial band
assert(len(zonetab) == 60)

def NL(lat):
    # Do abs() outside... maybe?
    if lat < 0:
        return 0
    for n in range(59,2,-1):
        if zonetab[n] >= lat:
            return n
    return 1

# see Doc 9871 C.2.6, p238

def cpr_decode_lat(oddstr, cprstr, ourlat):
    """
    :param oddstr: odd/even flag as 1-char bitstr
    :param cprstr: the CPR of target latitude
    :param ourlat: the latitude of the station in float degrees
    :returns: the target latitude in float degrees
    """
    Nb = 17  # 17 for airborne, 14 for ground/intent, 12 for TIS-B.
    NZ = 15  # Doc 9871 C.2.6.2

    if len(cprstr) != Nb:
        raise AppError("Latitude bit string size is not 17: %d" %
            len(cprstr))
    if oddstr != '0' and oddstr != '1':
        raise AppError("Invalid odd/even: %d" % oddstr)

    lat_s = ourlat
    i = btoi(oddstr)
    # Formulas only use the arc fraction, so convert YZ to fraction right away.
    YZf = float(btoi(cprstr))/(1<<Nb)
    # Dlat_i is either 6.0 or 360/59==6.1016949152
    Dlat_i = 360.0 / (4.0 * NZ - i)
    # Zone index number
    j = math.floor(lat_s/Dlat_i) + \
        math.floor(0.5 + (lat_s % Dlat_i)/Dlat_i - YZf)
    Rlat = Dlat_i * (j + YZf)
    return Rlat

def cpr_decode_lon(oddstr, cprstr, tgtlat, ourlon):
    Nb = 17  # 17 for airborne, 14 for ground/intent, 12 for TIS-B.

    if len(cprstr) != 17:
        raise AppError("Longitude bit string size is not 17: %d" % len(cprstr))
    if oddstr != '0' and oddstr != '1':
        raise AppError("Invalid odd/even: %d" % oddstr)

    Rlat = tgtlat
    lon_s = ourlon
    i = btoi(oddstr)
    XZf = float(btoi(cprstr))/(1<<Nb)
    # NL() defined in AppC.2.6.2.d Note 5
    nl = NL(Rlat)
    if nl - i == 0:
        Dlon_i = 360.0
    else:
        Dlon_i = 360.0/(nl - i)
    m = math.floor(lon_s/Dlon_i) + \
        math.floor(0.5 + (lon_s % Dlon_i)/Dlon_i - XZf)
    Rlon_i = Dlon_i * (m + XZf)
    return Rlon_i
