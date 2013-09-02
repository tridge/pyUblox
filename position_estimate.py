#!/usr/bin/env python
'''
estimate receiver position from RXM_RAW uBlox messages
'''

import ublox, sys
import util, ephemeris, positionEstimate, satelliteData, dataPlotter, time

from optparse import OptionParser

parser = OptionParser("position_estimate.py [options] <file>")
parser.add_option("--plot", action='store_true', default=False, help="plot points")
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)

(opts, args) = parser.parse_args()

if len(args) != 1:
    print("usage: position_estimate.py <file>")
    sys.exit(1)

filename = args[0]

dev = ublox.UBlox(filename)

rtcmfile = open('rtcm2.dat', mode='wb')

if opts.plot:
    reference = util.ParseLLH(opts.reference).ToECEF()
    plotter = dataPlotter.dataPlotter(reference)

def position_estimate(messages, satinfo):
    '''process raw messages to calculate position
    '''

    # get get position the receiver calculated. We use this to check the calculations

    pos = positionEstimate.positionEstimate(satinfo)
    if pos is None:
        # not enough information for a fix
        return

    if opts.plot:
        plotter.plotPosition(pos, 0)
        plotter.plotPosition(satinfo.average_position, 1)

    import RTCMv2
    rtcm = RTCMv2.generateRTCM2_Message1(satinfo)
    rtcmfile.write(rtcm)

    rtcm = RTCMv2.generateRTCM2_Message3(satinfo)
    if len(rtcm) > 0:
        rtcmfile.write(rtcm)
    
    if 'NAV_POSECEF' in messages:
        posecef = messages['NAV_POSECEF']
        ourpos = util.PosVector(posecef.ecefX*0.01, posecef.ecefY*0.01, posecef.ecefZ*0.01)
        posdiff = pos.distance(ourpos)
        print("posdiff=%f pos=%s avg=%s %s" % (posdiff, pos.ToLLH(), satinfo.average_position.ToLLH(), time.ctime(satinfo.raw.gps_time)))
    else:
        print("pos=%s" % (pos.ToLLH()))
    return pos


satinfo = satelliteData.SatelliteData()
messages = {}
pos_sum = util.PosVector(0,0,0)
pos_count = 0

while True:
    '''process the ublox messages, extracting the ones we need for the position'''
    msg = dev.receive_message()
    if msg is None:
        break
    if msg.name() in [ 'RXM_RAW', 'NAV_POSECEF', 'RXM_SFRB', 'RXM_RAW', 'AID_EPH' ]:
        try:
            msg.unpack()
            messages[msg.name()] = msg
            satinfo.add_message(msg)
        except ublox.UBloxError as e:
            print(e)
    if msg.name() == 'RXM_RAW':
        pos = position_estimate(messages, satinfo)
        if pos is not None:
            pos_sum += pos
            pos_count += 1

# get the receivers estimate of position. This should be quite accurate if
# we had PPP enabled
nav_ecef = messages['NAV_POSECEF']
receiver_ecef = util.PosVector(nav_ecef.ecefX*0.01, nav_ecef.ecefY*0.01, nav_ecef.ecefZ*0.01)

rtcmfile.close()

if pos_count > 0:
    posavg = pos_sum / pos_count

    print("Average position: %s  Satinfo.average: %s Receiver position: %s error=%f pos_count=%u" % (
            posavg.ToLLH(),
            satinfo.average_position.ToLLH(),
            receiver_ecef.ToLLH(),
            posavg.distance(receiver_ecef),
            pos_count))
else:
    print("No positions calculated")

if opts.plot:
    raw_input('Press enter')
