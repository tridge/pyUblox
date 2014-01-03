'''
Single point position estimate from raw receiver data
'''

import time
import util, satPosition, rangeCorrection

logfile = time.strftime('satlog-klobuchar-%y%m%d-%H%M.txt')
satlog = None
def save_satlog(t, errset):
    global satlog
    if satlog is None:
        satlog = open(logfile, 'w')

    eset = [ str(errset.get(s,'0')) for s in range(33) ]

    satlog.write(str(t) + "," + ",".join(eset) + "\n")
    satlog.flush()

def positionErrorFunction(p, data):
    '''error function for least squares position fit'''
    pos = util.PosVector(p[0], p[1], p[2])
    recv_clockerr = p[3]
    ret = []
    for d in data:
        satpos, prange, weight = d
        dist = pos.distance(satpos)
        ret.append((dist - (prange + util.speedOfLight*recv_clockerr))*weight)
    return ret

def positionLeastSquares_ranges(satinfo, pranges, lastpos, last_clock_error, weights=None):
    '''estimate ECEF position of receiver via least squares fit to satellite positions and pseudo-ranges
    The weights dictionary is optional. If supplied, it is the weighting from 0 to 1 for each satellite.
    A weight of 1 means it has more influence on the solution
    '''
    import scipy
    from scipy import optimize
    data = []

    for svid in satinfo.satpos:
        if svid in pranges:
            if weights is not None:
                weight = weights[svid]
            else:
                weight = 1.0
            data.append((satinfo.satpos[svid], pranges[svid], weight))
    p0 = [lastpos.X, lastpos.Y, lastpos.Z, last_clock_error]
    p1, ier = optimize.leastsq(positionErrorFunction, p0[:], args=(data))
    if not ier in [1, 2, 3, 4]:
        raise RuntimeError("Unable to find solution")

    # return position and clock error
    return util.PosVector(p1[0], p1[1], p1[2], extra=p1[3])

def clockErrorFunction(p, data):
    '''error function for least squares position fit'''
    pos = util.PosVector(*data[0])
    recv_clockerr = p[0]
    ret = []
    for d in data[1:]:
        satpos, prange, weight = d
        dist = pos.distance(satpos)
        ret.append((dist - (prange + util.speedOfLight*recv_clockerr))*weight)
    return ret

def clockLeastSquares_ranges(eph, pranges, itow, ref_pos, last_clock_error, weights=None):
    '''estimate ECEF position of receiver via least squares fit to satellite positions and pseudo-ranges
    The weights dictionary is optional. If supplied, it is the weighting from 0 to 1 for each satellite.
    A weight of 1 means it has more influence on the solution
    '''
    import scipy
    from scipy import optimize
    data = [ref_pos]

    for svid in pranges:
        if svid in eph:
            if weights is not None:
                weight = weights[svid]
            else:
                weight = 1.0

            tof = pranges[svid] / util.speedOfLight
            transmitTime = itow - tof
            satpos = satPosition.satPosition_raw(eph[svid], svid, transmitTime)

            data.append((satpos, pranges[svid], weight))

    if len(data) < 4:
        return

    p1, ier = optimize.leastsq(clockErrorFunction, [last_clock_error], args=(data))
    if not ier in [1, 2, 3, 4]:
        raise RuntimeError("Unable to find solution")

    return p1[0]

def satelliteWeightings(satinfo):
    '''return a dictionary of weightings for the contribution to the least squares
       for each satellite'''
    weights = {}
    for svid in satinfo.prSmoothed:
        # start with the quality estimate from the receiver
        quality = satinfo.raw.quality[svid]
        weight = 1.0/(pow(8 - min(quality,7),2))

        # add in the elevation setting. Scale to 1.0 at twice the min_elevation, and drop linearly to
        # zero at zero elevation
        max_el = 2*satinfo.min_elevation
        elevation = max(min(satinfo.elevation[svid], max_el), 1)
        weight *= 1.0 - ((max_el - elevation)/max_el)

        # add in the length of the cp smoothing history
        weight *= satinfo.smooth.weight(svid)

        weights[svid] = weight
    return weights

def positionLeastSquares(satinfo):
    '''estimate ECEF position of receiver via least squares fit to satellite positions and pseudo-ranges'''
    pranges = satinfo.prCorrected
    weights = satelliteWeightings(satinfo)

    # Estimate position and rx clk error
    newpos = positionLeastSquares_ranges(satinfo,
                                         satinfo.prCorrected,
                                         satinfo.lastpos,
                                         satinfo.receiver_clock_error,
                                         weights)
    satinfo.lastpos = newpos
    satinfo.receiver_clock_error = newpos.extra

    if satinfo.reference_position is not None:
        # Estimate rx clk error again if we have position
        # we still do the above as we use lastpos etc for statistic generation
        clk_err = clockLeastSquares_ranges(satinfo.ephemeris,
                                           satinfo.prCorrected,
                                           satinfo.raw.time_of_week,
                                           (satinfo.reference_position.X, satinfo.reference_position.Y, satinfo.reference_position.Z),
                                           0,
                                           weights)

        satinfo.receiver_clock_error = clk_err


    return newpos


def calculatePrCorrections(satinfo):
    raw = satinfo.raw
    satinfo.reset()
    errset={}
    for svid in raw.prMeasured:

        if not satinfo.valid(svid):
            # we don't have ephemeris data for this space vehicle
            #print("not valid")
            continue

        # get the ephemeris and pseudo-range for this space vehicle
        ephemeris = satinfo.ephemeris[svid]
        prMes = raw.prMeasured[svid]
        prSmooth = satinfo.smooth.prSmoothed[svid]

        # calculate the time of flight for this pseudo range
        tof = prSmooth / util.speedOfLight

        # assume the time_of_week is the exact receiver time of week that the message arrived.
        # subtract the time of flight to get the satellite transmit time
        transmitTime = raw.time_of_week - tof

        timesec = util.gpsTimeToTime(raw.gps_week, raw.time_of_week)

        # calculate the satellite position at the transmitTime
        satPosition.satPosition(satinfo, svid, transmitTime)
        Trel = satinfo.satpos[svid].extra

        # correct for earths rotation in the time it took the messages to get to the receiver
        satPosition.correctPosition(satinfo, svid, tof)

        # calculate satellite azimuth and elevation
        satPosition.calculateAzimuthElevation(satinfo, svid, satinfo.lastpos)

        # calculate the satellite clock correction
        sat_clock_error = rangeCorrection.sv_clock_correction(satinfo, svid, transmitTime, Trel)

        # calculate the satellite group delay
        sat_group_delay = -satinfo.ephemeris[svid].Tgd

        # calculate the ionospheric range correction
        ion_corr = rangeCorrection.ionospheric_correction(satinfo, svid, transmitTime, satinfo.lastpos)

        # calculate the tropospheric range correction
        tropo_corr = rangeCorrection.tropospheric_correction_sass(satinfo, svid, satinfo.lastpos)

        # get total range correction
        total_range_correction = ion_corr + tropo_corr
        errset[svid]=-total_range_correction
        # correct the pseudo-range for the clock and atmospheric errors
        prCorrected = prSmooth + (sat_clock_error + sat_group_delay)*util.speedOfLight - total_range_correction

        # save the values in the satinfo object
        satinfo.prMeasured[svid] = prMes
        satinfo.prSmoothed[svid] = prSmooth
        satinfo.prCorrected[svid] = prCorrected
        satinfo.ionospheric_correction[svid] = ion_corr
        satinfo.tropospheric_correction[svid] = tropo_corr
        satinfo.satellite_clock_error[svid] = sat_clock_error
        satinfo.satellite_group_delay[svid] = sat_group_delay

    save_satlog(raw.time_of_week, errset)

def positionEstimate(satinfo):
    '''process raw messages to calculate position
    '''

    calculatePrCorrections(satinfo)

    # if we got at least 4 satellites then calculate a position
    if len(satinfo.satpos) < 4:
        return None

    posestimate = positionLeastSquares(satinfo)

    satinfo.position_sum += posestimate
    satinfo.position_count += 1
    satinfo.average_position = satinfo.position_sum / satinfo.position_count
    satinfo.position_estimate = posestimate

    for svid in satinfo.prCorrected:
        if satinfo.reference_position is not None:
            satinfo.geometricRange[svid] = satinfo.reference_position.distance(satinfo.satpos[svid])
        elif satinfo.receiver_position is not None:
            satinfo.geometricRange[svid] = satinfo.receiver_position.distance(satinfo.satpos[svid])
        else:
            satinfo.geometricRange[svid] = satinfo.average_position.distance(satinfo.satpos[svid])

    return posestimate
