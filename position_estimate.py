#!/usr/bin/env python
'''
estimate receiver position from RXM_RAW uBlox messages
'''

import ublox
import util, ephemeris, satPosition, rangeCorrection, positionEstimate

from optparse import OptionParser

parser = OptionParser("position_estimate.py [options] <file>")

(opts, args) = parser.parse_args()

if len(args) != 1:
    print("usage: position_estimate.py <file>")
    sys.exit(1)

filename = args[0]

dev = ublox.UBlox(filename)

def position_estimate(messages, satinfo):
    '''process raw messages to calculate position
    '''

    needed = [ 'RXM_RAW', 'NAV_POSECEF' ]
    for n in needed:
        if not n in messages:
            return
        
    rxm_raw   = messages['RXM_RAW']

    # get get position the receiver calculated. We use this to check the calculations
    pos = messages['NAV_POSECEF']
    ourpos = util.PosVector(pos.ecefX*0.01, pos.ecefY*0.01, pos.ecefZ*0.01)

    raw = positionEstimate.rawPseudoRange(rxm_raw.week, rxm_raw.iTOW*1.0e-3)
    for i in range(rxm_raw.numSV):
        raw.add(rxm_raw.recs[i].sv,
                rxm_raw.recs[i].prMes,
                rxm_raw.recs[i].mesQI)

    pos = positionEstimate.positionEstimate(satinfo, raw)
    if pos is None:
        # not enough information for a fix
        return
    
    poserror = pos.distance(ourpos)

    print("poserr=%f pos=%s" % (poserror, pos.ToLLH()))
    return pos


satinfo = ephemeris.SatelliteData()
messages = {}
pos_sum = util.PosVector(0,0,0)
pos_count = 0

while True:
    '''process the ublox messages, extracting the ones we need for the position'''
    msg = dev.receive_message()
    if msg is None:
        break
    if msg.name() in [ 'RXM_RAW', 'NAV_POSECEF', 'RXM_SFRB' ]:
        msg.unpack()
        messages[msg.name()] = msg
        satinfo.add_message(msg)
    if msg.name() == 'RXM_RAW':
        pos = position_estimate(messages, satinfo)
        if pos is not None:
            pos_sum += pos
            pos_count += 1
    if msg.name() == 'AID_EPH':
        try:
            msg.unpack()
            messages[msg.name()] = msg
            satinfo.add_message(msg)
        except ublox.UBloxError as e:
            print(e)

# get the receivers estimate of position. This should be quite accurate if
# we had PPP enabled
nav_ecef = messages['NAV_POSECEF']
receiver_ecef = util.PosVector(nav_ecef.ecefX*0.01, nav_ecef.ecefY*0.01, nav_ecef.ecefZ*0.01)

posavg = pos_sum / pos_count

print("Average position: %s  Receiver position: %s error=%f" % (
    posavg.ToLLH(),
    receiver_ecef.ToLLH(),
    posavg.distance(receiver_ecef)))
