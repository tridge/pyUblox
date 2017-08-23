#!/usr/bin/env python

import ublox, sys, time, struct
import ephemeris

from optparse import OptionParser

parser = OptionParser("ublox_capture_raw.py [options]")
parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=115200)
parser.add_option("--log", help="log file", default=None)
parser.add_option("--append", action='store_true', default=False, help='append to log file')
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--show", action='store_true', default=False, help='show messages while capturing')
parser.add_option("--dynModel", type='int', default=None, help='set dynamic navigation model')
parser.add_option("--usePPP", action='store_true', default=False, help='enable precise point positioning')
parser.add_option("--dots", action='store_true', default=False, help='print a dot on each message')


(opts, args) = parser.parse_args()

dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
dev.set_logfile(opts.log, append=opts.append)
dev.set_binary()
dev.configure_poll_port()
dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
dev.configure_port(port=ublox.PORT_SERIAL1, inMask=1, outMask=0)
dev.configure_port(port=ublox.PORT_USB, inMask=1, outMask=1)
dev.configure_port(port=ublox.PORT_SERIAL2, inMask=1, outMask=0)
dev.configure_poll_port()
dev.configure_poll_port(ublox.PORT_SERIAL1)
dev.configure_poll_port(ublox.PORT_SERIAL2)
dev.configure_poll_port(ublox.PORT_USB)
dev.configure_solution_rate(rate_ms=1000)

dev.set_preferred_dynamic_model(opts.dynModel)
dev.set_preferred_usePPP(opts.usePPP)

dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)

# which SV IDs we have seen
svid_seen = {}
svid_ephemeris = {}

def handle_rxm_raw(msg):
    '''handle a RXM_RAW message'''
    global svid_seen, svid_ephemeris

    for i in range(msg.numSV):
        sv = msg.recs[i].sv
        tnow = time.time()
        if not sv in svid_seen or tnow > svid_seen[sv]+30:
            if sv in svid_ephemeris and svid_ephemeris[sv].timereceived+1800 < tnow:
                continue
            dev.configure_poll(ublox.CLASS_AID, ublox.MSG_AID_EPH, struct.pack('<B', sv))
            svid_seen[sv] = tnow

while True:
    msg = dev.receive_message()
    if msg is None:
        if opts.reopen:
            dev.close()
            dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
            dev.set_logfile(opts.log, append=True)
            continue
        break
    if opts.show:
        try:
            print(str(msg))
            sys.stdout.flush()
        except ublox.UBloxError as e:
            print(e)
    elif opts.dots:
        sys.stdout.write('.')
        sys.stdout.flush()
    if msg.name() == 'RXM_RAW':
        msg.unpack()
        handle_rxm_raw(msg)
    if msg.name() == 'AID_EPH':
        try:
            msg.unpack()
            svid_ephemeris[msg.svid] = ephemeris.EphemerisData(msg)
        except ublox.UBloxError as e:
            print(e)
