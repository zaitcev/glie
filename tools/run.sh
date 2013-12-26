#!/bin/sh
#
# Start the whole enchilada on niphredil
#

## PYTHONPATH
# We run the non-installed code from a development tree.
# If running packaged code, no need for PYTHONPATH at all.
export PYTHONPATH
PYTHONPATH=/q/zaitcev/radio/glie/glie-work

## The location of the dumping script.
export RTL1090

# The /q/zaitcev/radio/dump1090.sh contains:
#   /q/zaitcev/radio/dump1090/dump1090-wk/dump1090 --no-fix --raw
#RTL1090=/q/zaitcev/radio/dump1090.sh

# The /q/zaitcev/radio/rtl_adsb.sh contains:
#   /usr/bin/rtl_adsb
#RTL1090=/q/zaitcev/radio/dump1090.sh

# The simplest mode is to run the rtl_adsb binary with all defaults:
RTL1090=/usr/bin/rtl_adsb

## The GPS device.
# A recommended device is BU-353, which is merely a receiver and a PL-2303.
export GPSDEV
GPSDEV=/dev/ttyUSB0

## The output location. On embedded systems this ought to go into tmpfs,
## or else glied wears out the flash by writing all the time.
export GLIEOUT
GLIEOUT=/tmp/glie-out.json

# Start the main daemon:
/q/zaitcev/radio/glie/glie-work/bin/glied -g $GPSDEV -r $RTL1090 -o $GLIEOUT &
glied_pid=$!

# Write out webserver configuration:
# cat <<EOF >>/tmp/glie-server.conf
# EOF

# Start the webserver:
#/q/zaitcev/radio/glie/glie-work /tmp/glie-server.conf
