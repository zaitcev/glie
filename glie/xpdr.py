#
# Look up transponder altitude code and return the altitude.
#

# A Gray group of bits A (A1, A2, A4). Same table is for group B.
hash_a = {
    "000": 0,
    "001": 1,
    "011": 2,
    "010": 3,
    "110": 4,
    "111": 5,
    "101": 6,
    "100": 7
}

# Gray group for C1,C2,C4. Only has 5 elements (to address 2*500 ft).
hash_c = {
    "001": 0,
    "011": 1,
    "010": 2,
    "110": 3,
    "100": 4
}

# Gray group for D2,D4.
hash_d = {
    "00": 0,
    "01": 1,
    "11": 2,
    "10": 3
}

def code_to_alt(codestr):
    # :param codestr: A string of 11 text digits '0' and '1' in the transponder
    #                 order of D2,D4,A1,A2,A4,B1,B2,B4,C1,C2,C4
    # :returns: Integer for altitude in feet
    dx = hash_d[codestr[0:2]]
    if dx % 2:
        ax = len(hash_a)-1 - hash_a[codestr[2:5]]
    else:
        ax = hash_a[codestr[2:5]]
    if ax % 2:
        bx = len(hash_a)-1 - hash_a[codestr[5:8]]
    else:
        bx = hash_a[codestr[5:8]]
    if bx % 2:
        cx = len(hash_c)-1 - hash_c[codestr[8:11]]
    else:
        cx = hash_c[codestr[8:11]]
    print dx, ax, bx, cx
    return dx * 32000 + ax * 4000 + bx * 500 + cx * 100 - 1200
