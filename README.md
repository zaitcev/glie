glie
====

An experiment in ADS-B traffic for the cockpit
----------------------------------------------

Glie is a service that accepts two inputs: an ADS-B Extended Squitter
packet stream and GPS position reports, then produces a traffic awareness
presentation. The package stream comes in the familar asterisk-HEXDIGITS-
semicolon format. The GPS positions come in NMEA format. The output is
a web page with a picture in it, which can be displayed by basically
anything from laptop to cellphone.

Plans exist to package Glie into a largely self-contained box.
But currently it requires a Linux computer, a 1090ES receiver,
and a GPS.

Any user of Glie assumes full responsibility for the consequences.
Glie is not a substitute for See and Avoid practices. Glie can only
display aircraft and obstructions that participate in ADS-B system.

TODO:
* correct 1-bit errors by flipping every bit and re-checking CRC
* collect stats about types of ignored packets
* add tests for NMEA GPS inputs
* add tests for CPR inputs
* https://bugzilla.redhat.com/show_bug.cgi?id=810376  python-pypng review
* display relative motion by either
  - dump all-relative positions in cb{} histories, or
  - save a number of our historic locations with timestamps
* turn canvas into an object with height and width
