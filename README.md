glie
====

An experiment in ADS-B traffic for the cockpit
----------------------------------------------

Glie is a service that accepts two inputs: an ADS-B packet stream (either
1090ES or UAT) and GPS position reports, then produces a traffic awareness
presentation. The package stream comes in the familar marker-HEXDIGITS-
semicolon format. The GPS positions come in NMEA format. The output is
a web page with a picture in it, which can be displayed by basically
anything from laptop to cellphone.

Plans exist to package Glie into a largely self-contained box.
But currently it requires a Linux computer, a 1090ES receiver,
and a GPS.

Any user of Glie assumes full responsibility for the consequences.
Glie is not a substitute for See and Avoid practices. Glie can only
display aircraft and obstructions that participate in ADS-B system.

Running
-------

Glie consists of 2 processes currently:
1. the daemon that reads the input stream and maintains the state,
2. the webserver, which allows clients to display the state.

You run the daemon like so (if not installed on the system):

  # cat <<EOF > /q/zaitcev/radio/dump1090.sh
  #!/bin/sh
  /q/zaitcev/radio/dump1090/dump1090-wk/dump1090 --no-fix --raw
  EOF
  # PYTHONPATH=/q/zaitcev/radio/glie/glie-work \
   /q/zaitcev/radio/glie/glie-work/bin/glied -g /dev/ttyUSB0 \
   -r /q/zaitcev/radio/dump1090.sh -s 4800

You run the webserver like so (if not installed on the system):

  # PYTHONPATH=/q/zaitcev/radio/glie/glie-work \
   /q/zaitcev/radio/glie/glie-work/bin/glie-server \
   /q/zaitcev/radio/glie-server.conf

A sample glie-server.conf is supplied.

Both of these require root privileges usually. The daemon has to spawn
a service process that reads from privileged devices, and the webserver
needs to listen on a privileged port.

TODO
----

* correct 1-bit errors by flipping every bit and re-checking CRC
* collect stats about types of ignored packets
* add tests for NMEA GPS inputs
* add tests for CPR inputs
* display relative motion by either
  - dump all-relative positions in cb{} histories, or
  - save a number of our historic locations with timestamps
