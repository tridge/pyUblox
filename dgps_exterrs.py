#!/usr/bin/env python
'''
two receiver DGPS test code
'''

import ublox, sys, time, struct
import ephemeris, util
import RTCMv2

from optparse import OptionParser

parser = OptionParser("dgps_test.py [options]")
parser.add_option("--port1", help="serial port 1", default='/dev/ttyACM0')
parser.add_option("--port2", help="serial port 2", default='/dev/ttyACM1')
parser.add_option("--port3", help="serial port 3", default=None)
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=115200)
parser.add_option("--log1", help="log file1", default=None)
parser.add_option("--log2", help="log file2", default=None)
parser.add_option("--log3", help="log file3", default=None)
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--nortcm", action='store_true', default=False, help="don't send RTCM to receiver2")
parser.add_option("--usePPP", type='int', default=1, help="usePPP on recv1")
parser.add_option("--dynmodel1", type='int', default=ublox.DYNAMIC_MODEL_STATIONARY, help="dynamic model for recv1")
parser.add_option("--dynmodel2", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv2")
parser.add_option("--dynmodel3", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv3")
parser.add_option("--module-reset", action='store_true', help="cold start all the modules")

(opts, args) = parser.parse_args()

def setup_port(port, log, append=False):
    dev = ublox.UBlox(port, baudrate=opts.baudrate, timeout=0.01)
    dev.set_logfile(log, append=append)
    dev.set_binary()
    dev.configure_poll_port()
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
    dev.configure_poll(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_VER)
    dev.configure_port(port=ublox.PORT_SERIAL1, inMask=0x7, outMask=1)
    dev.configure_port(port=ublox.PORT_USB, inMask=0x7, outMask=1)
    dev.configure_port(port=ublox.PORT_SERIAL2, inMask=0x7, outMask=1)
    dev.configure_poll_port()
    dev.configure_poll_port(ublox.PORT_SERIAL1)
    dev.configure_poll_port(ublox.PORT_SERIAL2)
    dev.configure_poll_port(ublox.PORT_USB)
    return dev

dev1 = setup_port(opts.port1, opts.log1)
dev2 = setup_port(opts.port2, opts.log2)

if opts.port3 is not None:
    dev3 = setup_port(opts.port3, opts.log3)
else:
    dev3 = None

if opts.module_reset:
    dev1.module_reset(ublox.RESET_COLD, ublox.RESET_HW)
    dev2.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    if dev3 is not None:
        dev3.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    time.sleep(1)
    dev1.close()
    dev2.close()

    if dev3 is not None:
        dev3.close()

    time.sleep(1)

    dev1 = setup_port(opts.port1, opts.log1)
    dev2 = setup_port(opts.port2, opts.log2)

    if opts.port3 is not None:
        dev3 = setup_port(opts.port3, opts.log3)
    else:
        dev3 = None



dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
dev1.configure_solution_rate(rate_ms=1000)


dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
dev2.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
dev2.configure_solution_rate(rate_ms=1000)

if dev3 is not None:
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
    dev3.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
    dev3.configure_solution_rate(rate_ms=1000)

# we want the ground station to use a stationary model, and the roving
# GPS to use a highly dynamic model
dev1.set_preferred_dynamic_model(opts.dynmodel1)
dev2.set_preferred_dynamic_model(opts.dynmodel2)
if dev3 is not None:
    dev3.set_preferred_dynamic_model(opts.dynmodel3)
dev2.set_preferred_dgps_timeout(60)

# enable PPP on the ground side if we can
dev1.set_preferred_usePPP(opts.usePPP)
dev2.set_preferred_usePPP(False)
if dev3 is not None:
    dev3.set_preferred_usePPP(False)

rtcmfile = open('rtcm2.dat', mode='wb')

rtcm_gen = RTCMv2.RTCMBits()

itow = 0
week = 0
rx1_pos = util.PosVector(0,0,0)
rx2_pos = util.PosVector(0,0,0)
rx3_pos = util.PosVector(0,0,0)

svid_seen = {}
svid_iode = {}


def svinfo_to_rtcm(svinfo):

    resid = {}

    for i in range(msg.numCh):
        sv = msg.recs[i].svid
        tnow = time.time()
        if not sv in svid_seen or tnow > svid_seen[sv]+30:
            dev1.configure_poll(ublox.CLASS_AID, ublox.MSG_AID_EPH, struct.pack('<B', sv))
            svid_seen[sv] = tnow

    for rec in svinfo.recs:
        resid[rec.svid] = -rec.prRes / 100.

    if week == 0:
        return

    rtcm = rtcm_gen.RTCMType1_ext(resid, itow, week, svid_iode)
    if len(rtcm) != 0:
        print("generated type 1")
        rtcmfile.write(rtcm)
        if not opts.nortcm:
            dev2.write(rtcm)

    rtcm = rtcm_gen.RTCMType3_ext(itow, week, rx1_pos)
    if len(rtcm) != 0:
        print("generated type 3")
        rtcmfile.write(rtcm)
        if not opts.nortcm:
            dev2.write(rtcm)
    

last_msg1_time = time.time()
last_msg2_time = time.time()
last_msg3_time = time.time()

def handle_device1(msg):
    '''handle message from reference GPS'''
    global messages, satinfo, itow, week, rx1_pos, svid_seen

    if msg.name() in ['NAV_SVINFO', 'NAV_SOL', 'AID_EPH']:
        try:
            msg.unpack()
        except ublox.UBloxError as e:
            print(e)

    if msg.name() == 'NAV_SVINFO':
        svinfo_to_rtcm(msg)
    elif msg.name() == 'NAV_SOL':
        itow = msg.iTOW * 0.001
        week = msg.week
        rx1_pos = util.PosVector(msg.ecefX / 100., msg.ecefY / 100., msg.ecefZ / 100.)
    elif msg.name() == 'AID_EPH':
        eph = ephemeris.EphemerisData(msg)
        if eph.valid:
            svid_iode[eph.svid] = eph.iode

errlog = open('errlog.txt', mode='w')
errlog.write("normal DGPS normal-XY DGPS-XY\n")

def display_diff(name, pos1, pos2):
    print("%13s err: %6.2f errXY: %6.2f pos=%s" % (name, pos1.distance(pos2), pos1.distanceXY(pos2), pos1.ToLLH()))

def handle_device2(msg):
    '''handle message from rover GPS'''
    if msg.name() == 'NAV_DGPS':
        msg.unpack()
        print("DGPS: age=%u numCh=%u" % (msg.age, msg.numCh))
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        rx2_pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)

        print("-----------------")
        display_diff("RECV1<->RECV2", rx1_pos, rx2_pos)
        
        if dev3 is not None:
            display_diff("RECV1<->RECV3", rx1_pos, rx3_pos)
            errlog.write("%f %f %f %f\n" % (
                rx1_pos.distance(rx3_pos),
                rx1_pos.distance(rx2_pos),
                rx1_pos.distanceXY(rx3_pos),
                rx1_pos.distanceXY(rx2_pos)))
            errlog.flush()

def handle_device3(msg):
    global rx3_pos
    '''handle message from uncorrected rover GPS'''
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
        rx3_pos = pos
                                            

while True:
    # get a message from the reference GPS
    msg = dev1.receive_message_noerror()
    if msg is not None:
        handle_device1(msg)
        last_msg1_time = time.time()

    msg = dev2.receive_message_noerror()
    if msg is not None:
        handle_device2(msg)
        last_msg2_time = time.time()

    if dev3 is not None:
        msg = dev3.receive_message_noerror()
        if msg is not None:
            handle_device3(msg)
            last_msg3_time = time.time()

    if opts.reopen and time.time() > last_msg1_time + 5:
        dev1.close()
        dev1 = setup_port(opts.port1, opts.log1, append=True)
        last_msg1_time = time.time()
        sys.stdout.write('R1')

    if opts.reopen and time.time() > last_msg2_time + 5:
        dev2.close()
        dev2 = setup_port(opts.port2, opts.log2, append=True)
        last_msg2_time = time.time()
        sys.stdout.write('R2')

    if dev3 is not None and opts.reopen and time.time() > last_msg3_time + 5:
        dev3.close()
        dev3 = setup_port(opts.port3, opts.log3, append=True)
        last_msg3_time = time.time()
        sys.stdout.write('R3')

    sys.stdout.flush()
