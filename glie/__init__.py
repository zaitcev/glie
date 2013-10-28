#

# The caught exception
class AppError(Exception):
    pass

# The uncaught exception
class AppTraceback(Exception):
    pass

#
def btoi(bitstr):
    return int(bitstr, base=2)
