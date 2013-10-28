#
# Compute the Annex 10 extended squitter CRC
#
from glie import AppError, AppTraceback

# See Annex 10, v.4, 3.1.2.3.3.1.2 for the official squitter polynomial.
# (25 bits of poly for 24 bits of checksum)
sqpoly = "1111111111111010000001001"

def esq_crc(msgstr):
    """
    Compute the Anex 10 CRC

    :param msgstr: The message as a text bit string
    :returns: The CRC as a text bit string
    """
    return crc(msgstr, sqpoly)

# This is the slowest posssible way to calculate CRC.
def crc(msgstr, poly):
    if poly[0:1] != '1':
        raise AppError("poly %s does not start with '1'" % poly)
    if len(poly) < 2:
        raise AppError("length of poly %s is less than 2" % poly)
    if len(msgstr) < 1:
        raise AppError("length of message %s is less than 1" % msgstr)
    plength = len(poly)
    # Quotient is discarded. We may collect it for debugging
    #quotient = ""
    rem = msgstr[0:plength-1]
    msgstr = msgstr[plength-1:] + '0'*(plength-1)
    ## P3
    #print 'initial rem', rem, 'rest', msgstr
    for i in xrange(0,len(msgstr)):
        accum = rem + msgstr[i:i+1]
        ## P3
        #print 'acc', accum
        rem = xor(poly, accum)
        if rem[0:1] == '1':
            #quotient += '0'
            rem = accum[1:plength]
        else:
            #quotient += '1'
            rem = rem[1:plength]
        ## P3
        #print "  rem", rem[1:plength]
    ## P3
    #print 'quot', quotient
    return rem

# This operates on our usual strings with attendant conversions. Nasty.
# Maybe one day we'll recode the whole thing with proper arrays.
def xor(a, b):
    zero = bytearray('0')
    length = len(a)
    if length != len(b):
        raise AppTraceback('xor on unequal length arguments')
    av = bytearray(a)
    bv = bytearray(b)
    result = bytearray(length)
    for i in xrange(0,length):
        result[i] = (av[i] ^ bv[i]) + zero[0]
    ret = result.decode('latin-1')
    if isinstance(ret, unicode):
        ret = ret.encode('ascii')
    return ret
