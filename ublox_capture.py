#!/usr/bin/env python

import ublox, sys

from optparse import OptionParser

parser = OptionParser("ublox_capture.py [options]")
parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=115200)
parser.add_option("--log", help="log file", default=None)
parser.add_option("--append", action='store_true', default=False, help='append to log file')
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--show", action='store_true', default=False, help='show messages while capturing')
parser.add_option("--dynModel", type='int', default=-1, help='set dynamic navigation model')
parser.add_option("--usePPP", action='store_true', default=False, help='enable precise point positioning')
parser.add_option("--dots", action='store_true', default=False, help='print a dot on each message')


(opts, args) = parser.parse_args()

dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
dev.set_logfile(opts.log, append=opts.append)
dev.set_binary()
dev.configure_poll_port()
dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAV5)
dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)
dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
dev.configure_port(port=ublox.PORT_SERIAL1, inMask=1, outMask=0)
dev.configure_port(port=ublox.PORT_USB, inMask=1, outMask=1)
dev.configure_port(port=ublox.PORT_SERIAL2, inMask=1, outMask=0)
dev.configure_poll_port()
dev.configure_poll_port(ublox.PORT_SERIAL1)
dev.configure_poll_port(ublox.PORT_SERIAL2)
dev.configure_poll_port(ublox.PORT_USB)
dev.configure_solution_rate(rate_ms=200)

dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_STATUS, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_ALM, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_EPH, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_TIMEGPS, 5)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_CLOCK, 5)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS, 5)

while True:
    msg = dev.receive_message()
    if msg is None:
        if opts.reopen:
            dev.close()
            dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
            dev.set_logfile(opts.log, append=opts.append)
            continue
        break
    if opts.show:
        print(str(msg))
        sys.stdout.flush()
    elif opts.dots:
        sys.stdout.write('.')
        sys.stdout.flush()
    if opts.dynModel != -1 and msg.name() == 'CFG_NAV5':
        msg.unpack()
        if msg.dynModel != opts.dynModel:
            msg.unpack()
            msg.dynModel = opts.dynModel
            msg.pack()
            dev.send(msg)
            dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAV5)
    if msg.name() == 'CFG_NAVX5':
        msg.unpack()
        if msg.usePPP != int(opts.usePPP):
            msg.usePPP = int(opts.usePPP)
            msg.mask = 1<<13
            msg.pack()
            dev.send(msg)
            dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)

