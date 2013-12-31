#!/usr/bin/env python
'''
two receiver DGPS test code
'''

import ublox, sys, time, struct
import ephemeris, util, positionEstimate, satelliteData
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
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)
parser.add_option("--ecef-reference", help="reference position (X,Y,Z)")
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--nortcm", action='store_true', default=False, help="don't send RTCM to receiver2")
parser.add_option("--usePPP", type='int', default=1, help="usePPP on recv1")
parser.add_option("--dynmodel1", type='int', default=ublox.DYNAMIC_MODEL_STATIONARY, help="dynamic model for recv1")
parser.add_option("--dynmodel2", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv2")
parser.add_option("--dynmodel3", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv3")
parser.add_option("--minelevation", type='float', default=10.0, help="minimum satellite elevation")
parser.add_option("--minquality", type='int', default=6, help="minimum satellite quality")
parser.add_option("--append", action='store_true', default=False, help='append to log file')
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

dev1 = setup_port(opts.port1, opts.log1, append=opts.append)
dev2 = setup_port(opts.port2, opts.log2, append=opts.append)

if opts.port3 is not None:
    dev3 = setup_port(opts.port3, opts.log3, append=opts.append)
else:
    dev3 = None


if opts.module_reset:
    dev2.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    if dev3 is not None:
        dev3.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    time.sleep(1)
    dev2.close()

    if dev3 is not None:
        dev3.close()

    time.sleep(1)

    dev2 = setup_port(opts.port2, opts.log2)

    if opts.port3 is not None:
        dev3 = setup_port(opts.port3, opts.log3)
    else:
        dev3 = None


dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)
dev1.configure_message_rate(ublox.CLASS_AID, ublox.MSG_AID_EPH, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
dev1.configure_solution_rate(rate_ms=200)


dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
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

if opts.append:
    rtcmfile = open('rtcm2.dat', mode='ab')
else:
    rtcmfile = open('rtcm2.dat', mode='wb')

logfile = time.strftime('satlog-local-%y%m%d-%H%M.txt')
satlog = None
def save_satlog(t, errset):
    global satlog
    if satlog is None:
        satlog = open(logfile, 'w')

    eset = [ str(errset.get(s,'0')) for s in range(33) ]

    satlog.write(str(t) + "," + ",".join(eset) + "\n")
    satlog.flush()

def position_estimate(messages, satinfo):
    '''process raw messages to calculate position
    '''

    rxm_raw   = messages['RXM_RAW']

    pos = positionEstimate.positionEstimate(satinfo)
    if pos is None:
        # not enough information for a fix
        return

    rtcm = RTCMv2.generateRTCM2_Message1(satinfo)
    if len(rtcm) != 0:
        print("generated type 1")
        rtcmfile.write(rtcm)
        if not opts.nortcm:
            dev2.write(rtcm)

    rtcm = RTCMv2.generateRTCM2_Message3(satinfo)
    if len(rtcm) != 0:
        print("generated type 3")
        rtcmfile.write(rtcm)
        if not opts.nortcm:
            dev2.write(rtcm)
    
    errset = {}
    for svid in satinfo.rtcm_bits.error_history:
        errset[svid] = satinfo.rtcm_bits.error_history[svid][-1]

    save_satlog(rxm_raw.iTOW, errset)

    return pos

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
            dev1.configure_poll(ublox.CLASS_AID, ublox.MSG_AID_EPH, struct.pack('<B', sv))
            svid_seen[sv] = tnow

last_msg1_time = time.time()
last_msg2_time = time.time()
last_msg3_time = time.time()

messages = {}
satinfo = satelliteData.SatelliteData()

if opts.reference is not None:
    satinfo.reference_position = util.ParseLLH(opts.reference).ToECEF()
elif opts.ecef_reference is not None:
    satinfo.reference_position = util.PosVector(*opts.ecef_reference.split(','))
else:
    satinfo.reference_position = None


satinfo.min_elevation = opts.minelevation
satinfo.min_quality = opts.minquality

def handle_device1(msg):
    '''handle message from reference GPS'''
    global messages, satinfo
    
    if msg.name() in [ 'RXM_RAW', 'NAV_POSECEF', 'RXM_SFRB', 'RXM_RAW', 'AID_EPH', 'NAV_POSECEF' ]:
        try:
            msg.unpack()
            messages[msg.name()] = msg
            satinfo.add_message(msg)
        except ublox.UBloxError as e:
            print(e)
    if msg.name() == 'RXM_RAW':
        handle_rxm_raw(msg)
        position_estimate(messages, satinfo)

if opts.append:
    errlog = open(time.strftime('errlog-%y%m%d-%H%M.txt'), mode='a')
else:
    errlog = open(time.strftime('errlog-%y%m%d-%H%M.txt'), mode='w')
    errlog.write("normal DGPS normal-XY DGPS-XY\n")

def display_diff(name, pos1, pos2):
    print("%13s err: %6.2f errXY: %6.2f pos=%s" % (name, pos1.distance(pos2), pos1.distanceXY(pos2), pos1.ToLLH()))

pos_count = 0

def handle_device2(msg):
    '''handle message from rover GPS'''
    global pos_count
    if msg.name() == 'NAV_DGPS':
        msg.unpack()
        print("DGPS: age=%u numCh=%u pos_count=%u" % (msg.age, msg.numCh, pos_count))
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
        satinfo.recv2_position = pos
        if satinfo.average_position is None or satinfo.position_estimate is None:
            return
        print("-----------------")
        display_diff("RECV1<->RECV2", satinfo.receiver_position, pos)
        display_diff("RECV2<->AVG",   satinfo.receiver_position, satinfo.average_position)
        display_diff("AVG<->RECV1",   satinfo.average_position, satinfo.receiver_position)
        display_diff("AVG<->RECV2",   satinfo.average_position, pos)
        if satinfo.reference_position is not None:
            display_diff("REF<->AVG",   satinfo.reference_position, satinfo.average_position)
            display_diff("POS<->REF",   satinfo.position_estimate, satinfo.reference_position)
            if satinfo.rtcm_position is not None:
                display_diff("RTCM<->REF", satinfo.rtcm_position, satinfo.reference_position)                
                display_diff("RTCM<->RECV2", satinfo.rtcm_position, satinfo.recv2_position)                
            display_diff("RECV1<->REF", satinfo.receiver_position, satinfo.reference_position)
            display_diff("RECV2<->REF", satinfo.recv2_position, satinfo.reference_position)
            pos_count += 1
            if satinfo.recv3_position is not None:
                display_diff("RECV3<->REF", satinfo.recv3_position, satinfo.reference_position)
                errlog.write("%f %f %f %f\n" % (
                    satinfo.reference_position.distance(satinfo.recv3_position),
                    satinfo.reference_position.distance(satinfo.recv2_position),
                    satinfo.reference_position.distanceXY(satinfo.recv3_position),
                    satinfo.reference_position.distanceXY(satinfo.recv2_position)))
                errlog.flush()
            else:
                errlog.write("%f %f %f %f\n" % (
                    satinfo.reference_position.distance(satinfo.receiver_position),
                    satinfo.reference_position.distance(satinfo.recv2_position),
                    satinfo.reference_position.distanceXY(satinfo.receiver_position),
                    satinfo.reference_position.distanceXY(satinfo.recv2_position)))
                errlog.flush()

def handle_device3(msg):
    '''handle message from uncorrected rover GPS'''
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
        satinfo.recv3_position = pos
                                            

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
