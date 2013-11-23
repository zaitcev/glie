How to install and run Glie
===========================

First, you need a computer with Linux. Windows or OSX may work, but
using those is left to excercise of the reader. Also, you need a source
of position information and an ADS-B receiver. Try a generic GPS with
NMEA output. It's hard to be more specific due to built-in variety
of NMEA standard. Problems are likely; please report them to Glie
developers.

For ADS-B, you need something that provides a general Extended Squitter
stream. Its messages look like this: "*8dabd3c758c036b338d471661ef6;".
The easiest way to obtain that is by an SDR receiver from Realtek (RTL)
and run rtl_adsb or dump1090. See the "RTL-SDR" Wiki:
 http://sdr.osmocom.org/trac/wiki/rtl-sdr

Unfortunately, UAT receivers are not supported.

Software installation
---------------------

Create a user 'glie'. Either do it by hand or run this:

 # useradd -r -s /sbin/nologin glie

You still have to run everything as a root, but Glie's daemons are going
to drop privileges to user 'glie'.

Open the TCP port 80. This is highly system dependent. On Fedora 19,
do this:

 # firewall-cmd --permanent --add-port=80/tcp

Running
-------

To run in-place, change to the top of Glie tree and do this:

# PYTHONPATH=$(pwd) bin/glied -g /dev/ttyUSB0 \
   -r /home/zaitcev/radio/rtl_adsb.sh -s 9600
# PYTHONPATH=$(pwd) bin/glie-server
