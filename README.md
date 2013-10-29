glie
====

An experiment in ADS-B traffic for the cockpit
----------------------------------------------

Glie is a service that has accepts two inputs: ADS-B Extended Squitter
packet stream and GPS position reports, then produces a traffic awareness
presentation. The package stream comes in the familar asterisk-HEXDIGITS-
semicolon format. The GPS positions come in NMEA format. The output is
a web page with a picture in it, which can be displayed by basically
anything from laptop to cellphone.

Plans exist to package Glie into a largely self-contained box.
But currently it requires a Linux computer, a 1090ES receiver,
and a GPS.

TODO:
* find a better receiver than rtl_adsb (dump1090, hardare)
* correct 1-bit errors by flipping every bit and re-checking CRC
