#!/usr/bin/env python
'''
Locally-generated DGPS corrections, publish as UDP datagrams
'''

import ublox, sys, time, socket, struct
import ephemeris, util, positionEstimate, satelliteData
import RTCMv2

from optparse import OptionParser

parser = OptionParser("local_to_udp.py [options]")
parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=115200)
parser.add_option("--log", help="log file", default=None)
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)
parser.add_option("--ecef-reference", help="reference position (X,Y,Z)")
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--usePPP", type='int', default=1, help="usePPP on recv1")
parser.add_option("--dynmodel1", type='int', default=ublox.DYNAMIC_MODEL_STATIONARY, help="dynamic model for recv1")
parser.add_option("--minelevation", type='float', default=10.0, help="minimum satellite elevation")
parser.add_option("--minquality", type='int', default=6, help="minimum satellite quality")
parser.add_option("--append", action='store_true', default=False, help='append to log file')
parser.add_option("--module-reset", action='store_true', help="cold start all the modules")

parser.add_option("--udp-port", type='int', default=13320)
parser.add_option("--udp-addr", default="127.0.0.1")


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

dev1 = setup_port(opts.port, opts.log, append=opts.append)

dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 1)
dev1.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 1)
dev1.configure_message_rate(ublox.CLASS_AID, ublox.MSG_AID_EPH, 1)
dev1.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
dev1.configure_solution_rate(rate_ms=200)

# we want the ground station to use a stationary model, and the roving
# GPS to use a highly dynamic model
dev1.set_preferred_dynamic_model(opts.dynmodel1)

# enable PPP on the ground side if we can
dev1.set_preferred_usePPP(opts.usePPP)

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

messages = {}
satinfo = satelliteData.SatelliteData()

port = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

def position_estimate(messages, satinfo):
    '''process raw messages to calculate position
    '''

    rxm_raw   = messages['RXM_RAW']

    pos = positionEstimate.positionEstimate(satinfo)
    if pos is None:
        # not enough information for a fix
        return

    rtcm = RTCMv2.generateRTCM2_Message1(satinfo, maxsats=10)
    if len(rtcm) != 0:
        #print(rtcm)
        rtcmfile.write(rtcm)
        port.sendto(rtcm[:-2], (opts.udp_addr, opts.udp_port))

    rtcm = RTCMv2.generateRTCM2_Message3(satinfo)
    if len(rtcm) != 0:
        print(rtcm)
        rtcmfile.write(rtcm)
        port.sendto(rtcm[:-2], (opts.udp_addr, opts.udp_port))
    
    errset = {}
    for svid in satinfo.rtcm_bits.error_history:
        errset[svid] = satinfo.rtcm_bits.error_history[svid][-1]

    save_satlog(rxm_raw.iTOW, errset)

    print(satinfo.receiver_position)

    return pos

pos_count = 0

while True:
    # get a message from the reference GPS
    msg = dev1.receive_message_noerror()
    if msg is None:
        time.sleep(0.1)
        continue

    #if msg is not None:
    handle_device1(msg)
    last_msg1_time = time.time()

    if opts.reopen and time.time() > last_msg1_time + 5:
        dev1.close()
        dev1 = setup_port(opts.port1, opts.log1, append=True)
        last_msg1_time = time.time()
        sys.stdout.write('R1')

    sys.stdout.flush()
