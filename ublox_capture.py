#!/usr/bin/env python

import ublox, sys

from optparse import OptionParser

parser = OptionParser("ublox_capture.py [options]")
parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=38400)
parser.add_option("--log", help="log file", default=None)
parser.add_option("--append", action='store_true', default=False, help='append to log file')


(opts, args) = parser.parse_args()

dev = ublox.UBlox(opts.port, baudrate=opts.baudrate)
dev.set_logfile(opts.log, append=opts.append)
dev.set_binary()
dev.configure_poll_port()
dev.configure_poll_port(ublox.PORT_DDC)
dev.configure_poll_port(ublox.PORT_SERIAL1)
dev.configure_poll_port(ublox.PORT_SERIAL2)
dev.configure_poll_port(ublox.PORT_USB)
dev.configure_poll_port(ublox.PORT_SPI)
dev.configure_port(port=ublox.PORT_SERIAL1, inMask=3, outMask=3)
dev.configure_port(port=ublox.PORT_USB, inMask=1, outMask=1)
dev.configure_poll_usb()
dev.configure_solution_rate(rate_ms=200)

dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_STATUS, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 1)

while True:
    msg = dev.receive_message()
    if msg is None:
        break
    print(str(msg))
    sys.stdout.flush()

