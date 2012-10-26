#!/usr/bin/env python

import ublox

from optparse import OptionParser

parser = OptionParser("ublox_capture.py [options]")
parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
parser.add_option("--baudrate", dest="baudrate", type='int',
                  help="serial baud rate", default=38400)


(opts, args) = parser.parse_args()

dev = ublox.UBlox(opts.port, baudrate=opts.baudrate)
dev.set_binary()
#dev.configure_poll_port()
dev.configure_port(port=ublox.PORT_SERIAL1)
dev.configure_port(port=ublox.PORT_USB)
dev.configure_solution_rate(rate_ms=200)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_POSLLH, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_STATUS, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_SOL, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_VELNED, 1)

while True:
    msg = dev.receive_message()
    print("GOT MSG: %s" % msg)

