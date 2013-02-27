#!/usr/bin/env python
'''
estimate receiver position from RXM_RAW uBlox messages
'''

import ublox
import util, ephemeris, satPosition, rangeCorrection
from ephemeris import eph2clk

from optparse import OptionParser

parser = OptionParser("position_estimate.py [options] <file>")

(opts, args) = parser.parse_args()

if len(args) != 1:
    print("usage: position_estimate.py <file>")
    sys.exit(1)

filename = args[0]

dev = ublox.UBlox(filename)

def position_error_fn(p, data):
    '''error function for least squares position fit'''
    pos = util.PosVector(p[0], p[1], p[2])
    ret = []
    for d in data:
        satpos, prange = d
        dist = pos.distance(satpos)
        ret.append(dist - prange)
    return ret

def position_leastsquares(satpos, pranges):
    '''estimate ECEF position via least squares fit to satellite positions and pseudo-ranges'''
    import scipy
    from scipy import optimize
    data = []
    for svid in satpos:
        data.append((satpos[svid], pranges[svid]))
    p0 = [0.0, 0.0, 0.0]
    p1, ier = optimize.leastsq(position_error_fn, p0[:], args=(data))
    if not ier in [1, 2, 3, 4]:
        raise RuntimeError("Unable to find solution")

    return util.PosVector(p1[0], p1[1], p1[2])


def position_estimate(messages, svid_ephemeris, svid_ionospheric):
    '''process raw messages to calculate position
    return the average position over all messages
    '''

    speedOfLight = 299792458.0

    needed = [ 'NAV_SOL', 'NAV_CLOCK', 'RXM_RAW', 'NAV_POSECEF', 'RXM_SFRB' ]
    for n in needed:
        if not n in messages:
            return
        
    nav_sol = messages['NAV_SOL']
    nav_clock = messages['NAV_CLOCK']
    rxm_raw   = messages['RXM_RAW']

    # get get position the receiver calculated. We use this to check the calculations
    pos       = messages['NAV_POSECEF']
    ourpos = util.PosVector(pos.ecefX*0.01, pos.ecefY*0.01, pos.ecefZ*0.01)

    # build a hash of SVID to satellite position and pseudoranges
    satpos = {}
    pranges = {}

    for i in range(rxm_raw.numSV):
        svid = rxm_raw.recs[i].sv
        if not svid in svid_ephemeris:
            # we don't have ephemeris data for this space vehicle
            continue

        if not svid in svid_ionospheric:
            # we don't have ionospheric data for this space vehicle
            continue

        if rxm_raw.recs[i].mesQI < 7:
            # for now we will ignore raw data that isn't very high quality. It would be
            # better to do a weighting in the least squares calculation
            continue

        # get the ephemeris and pseudo-range for this space vehicle
        ephemeris = svid_ephemeris[svid]
        prMes = rxm_raw.recs[i].prMes

        # calculate the time of flight for this pseudo range
        tof = prMes / speedOfLight

        # assume the iTOW in RXM_RAW is the exact receiver time of week that the message arrived.
        # subtract the time of flight to get the satellite transmit time
        transmitTime = rxm_raw.iTOW*1.0e-3 - tof

        # calculate the satellite clock error from the ephemeris data
        sat_clock_error = eph2clk(transmitTime, ephemeris)

        # calculate receiver clock bias
        receiver_time_bias = -nav_clock.clkB*1.0e-9 + 0.00001985

        # and the amount that bias has drifted between the time in NAV_CLOCK and the time in RXM_RAW
        receiver_time_bias2 = -((rxm_raw.iTOW*1.0e-3 - nav_clock.iTOW*1.0e-3) * nav_clock.clkD) * 1.0e-9

        # add up the various clock errors
        total_clock_error = sat_clock_error + receiver_time_bias + receiver_time_bias2

        # correct the pseudo-range for the clock errors
        prMes_biased = prMes + total_clock_error*speedOfLight

        # calculate the satellite position at the transmitTime
        satpos[svid] = satPosition.satPosition(ephemeris, transmitTime)

        # and also store the corrected pseudo-range for this time
        pranges[svid] = prMes_biased

        # calculate the apparent range between the receiver calculated position and the satellite. This gives
        # us an idea of the error
        dist = satpos[svid].distance(ourpos)

        # calculate the error between the receiver position and biased pseudo range
        range_error = dist - prMes_biased

        print("tow=%u sv:%u clkB=%f prMes=%f rerr=%f terr=%g clkerr=%f" % (
            rxm_raw.iTOW*0.001,
            svid,
            nav_clock.clkB*1.0e-9,
            prMes_biased,
            range_error,
            range_error/speedOfLight,
            total_clock_error))

    # if we got at least 4 satellites then calculate a position
    if len(satpos) < 4:
        return None
    
    posestimate = position_leastsquares(satpos, pranges)
    poserror = posestimate.distance(ourpos)

    print("poserr=%f pos=%s" % (poserror, posestimate.ToLLH()))
    return posestimate

    
svid_ephemeris = {}
svid_ionospheric = {}
messages = {}
pos_sum = util.PosVector(0,0,0)
pos_count = 0

while True:
    '''process the ublox messages, extracting the ones we need for the position'''
    msg = dev.receive_message()
    if msg is None:
        break
    if msg.name() in [ 'RXM_RAW', 'NAV_CLOCK', 'NAV_SOL', 'NAV_POSECEF', 'NAV_POSLLH', 'NAV_SVINFO', 'RXM_SFRB' ]:
        msg.unpack()
        messages[msg.name()] = msg
    if msg.name() == 'RXM_RAW':
        pos = position_estimate(messages, svid_ephemeris, svid_ionospheric)
        if pos is not None:
            pos_sum += pos
            pos_count += 1
    if msg.name() == 'AID_EPH':
        try:
            msg.unpack()
            messages[msg.name()] = msg
            svid_ephemeris[msg.svid] = ephemeris.EphemerisData(msg)
        except ublox.UBloxError as e:
            print(e)
    if msg.name() == 'RXM_SFRB':
        iondata = ephemeris.IonosphericData(msg)
        if iondata.valid:
            svid_ionospheric[msg.svid] = iondata

nav_ecef = messages['NAV_POSECEF']
receiver_ecef = util.PosVector(nav_ecef.ecefX*0.01, nav_ecef.ecefY*0.01, nav_ecef.ecefZ*0.01)

posavg = pos_sum / pos_count

print("Average position: %s  Receiver position: %s error=%f" % (
    posavg.ToLLH(),
    receiver_ecef.ToLLH(),
    posavg.distance(receiver_ecef)))
