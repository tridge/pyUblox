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
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=115200)
parser.add_option("--log1", help="log file1", default=None)
parser.add_option("--log2", help="log file2", default=None)
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')


(opts, args) = parser.parse_args()

def setup_port(port, log, append=False):
    dev = ublox.UBlox(port, baudrate=opts.baudrate, timeout=0.2)
    dev.set_logfile(log, append=append)
    dev.set_binary()
    dev.configure_poll_port()
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
    dev.configure_poll(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_VER)
    dev.configure_port(port=ublox.PORT_SERIAL1, inMask=0xFFFF, outMask=1)
    dev.configure_port(port=ublox.PORT_USB, inMask=0xFFFF, outMask=1)
    dev.configure_port(port=ublox.PORT_SERIAL2, inMask=0xFFFF, outMask=1)
    dev.configure_poll_port()
    dev.configure_poll_port(ublox.PORT_SERIAL1)
    dev.configure_poll_port(ublox.PORT_SERIAL2)
    dev.configure_poll_port(ublox.PORT_USB)
    dev.configure_solution_rate(rate_ms=1000)
    return dev

dev1 = setup_port(opts.port1, opts.log1)
dev2 = setup_port(opts.port2, opts.log2)

dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)
dev1.configure_message_rate(ublox.CLASS_AID, ublox.MSG_AID_EPH, 1)



dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS, 1)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
dev2.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)

# we want the ground station to use a stationary model, and the roving
# GPS to use a highly dynamic model
dev1.set_preferred_dynamic_model(ublox.DYNAMIC_MODEL_STATIONARY)
dev2.set_preferred_dynamic_model(ublox.DYNAMIC_MODEL_AIRBORNE4G)
dev2.set_preferred_dgps_timeout(60)

# enable PPP on the ground side if we can
dev1.set_preferred_usePPP(True)
dev2.set_preferred_usePPP(False)

rtcmfile = open('rtcm2.dat', mode='wb')

def position_estimate(messages, satinfo):
    '''process raw messages to calculate position
    '''

    rxm_raw   = messages['RXM_RAW']

    pos = positionEstimate.positionEstimate(satinfo)
    if pos is None:
        # not enough information for a fix
        return

    rtcm = RTCMv2.generateRTCM2_Message1(satinfo)
    rtcmfile.write(rtcm)
    dev2.dev.write(rtcm)

    if satinfo.last_rtcm_msg3 + 30 < satinfo.raw.gps_time:
        print("generated type 3")
        rtcm = RTCMv2.generateRTCM2_Message3(satinfo)
        rtcmfile.write(rtcm)
        dev2.dev.write(rtcm)
        satinfo.last_rtcm_msg3 = satinfo.raw.gps_time
    
    print("pos=%s" % (pos.ToLLH()))
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

messages = {}
satinfo = satelliteData.SatelliteData()
if opts.reference:
    satinfo.reference_position = util.ParseLLH(opts.reference).ToECEF()

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


def handle_device2(msg):
    '''handle message from rover GPS'''
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
        if satinfo.average_position is not None:
            print("RECV1<->RECV2 error: %6.2f pos=%s" % (pos.distance(satinfo.receiver_position), satinfo.receiver_position.ToLLH()))
            print("RECV2<->AVG   error: %6.2f pos=%s" % (pos.distance(satinfo.average_position), pos.ToLLH()))
            print("AVG<->RECV1   error: %6.2f pos=%s" % (satinfo.receiver_position.distance(satinfo.average_position), satinfo.average_position.ToLLH()))
            print("AVG<->RECV2   error: %6.2f pos=%s" % (satinfo.average_position.distance(pos), satinfo.average_position.ToLLH()))
            if satinfo.reference_position is not None:
                print("REF<->RECV2   error: %6.2f pos=%s" % (satinfo.reference_position.distance(pos), satinfo.reference_position.ToLLH()))
                

while True:
    # get a message from the reference GPS
    msg = dev1.receive_message()
    if msg is not None:
        handle_device1(msg)
        last_msg1_time = time.time()

    msg = dev2.receive_message()
    if msg is not None:
        handle_device2(msg)
        last_msg2_time = time.time()

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

    sys.stdout.flush()
