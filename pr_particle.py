#!/usr/bin/env python

import ublox, sys, os
import numpy
import numpy.linalg as linalg
import satelliteData, positionEstimate, util
import pybayes, pybayes.pdfs, pybayes.filters

from optparse import OptionParser

parser = OptionParser("pr_particlew.py [options] <file>")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")

(opts, args) = parser.parse_args()

#--- Parameters

n = 10000

gps_cov = 1000
state_cov = 10

meas = None
#--- End Parameters

dev = ublox.UBlox(args[0])

if opts.seek != 0:
    dev.seek_percent(opts.seek)

satinfo = satelliteData.SatelliteData();
filt = None

def p_xt_xtp_mu(xtp):
    '''Return mean of Gaussian PDF for state xt given x(t-1).  Assume static receiver, Mean at old state'''
    return xtp

def p_xt_xtp_R(xtp):
    '''Return covariance of Gaussian PDF for state xt given x(t-1).'''
    return numpy.diag([state_cov, state_cov, state_cov, state_cov / util.speedOfLight])

def p_yt_xt_mu(xt):
    ''' Return mean of Gaussian PDF for measurement yt given xt.  Mean is at the ideal measurement'''
    rxpos = util.PosVector(xt[0], xt[1], xt[2])
    ideal = [0] * 32
    for i in range(32):
        if i in satinfo.satpos and i in satinfo.prCorrected:
            ideal[i] = satinfo.satpos[i].distance(rxpos) + xt[3] * util.speedOfLight

    #print(xt)
    #print(numpy.array(ideal) - numpy.array(meas))
    return numpy.array(ideal)

def p_yt_xt_R(xt):
    ''' Return covariance matric of Gaussian PDF for measurement yt given xt.
        Covariance is related to signal quality, assumed independent for all sats'''

    dia = [gps_cov] * 32
    #for i in range(32):
    #    if i in satinfo.satpos and i in satinfo.prCorrected:
    #        dia[i] = gps_cov #10**(satinfo.raw.cno[i]/10)

    return numpy.diag(dia)

def build_filter(info):
    global filt
    
    if filt is None:
        est = positionEstimate.positionEstimate(satinfo)
        if est is None:
            # We use the least-squares method to bootstrap our one to avoid
            # a requirement for mad particle space
            return

    print("RP" + str(est))
    mean = numpy.array([est.X, est.Y, est.Z, est.extra])

    cov = numpy.diag([100 * state_cov, 100 * state_cov, 100 * state_cov, 100 * state_cov / util.speedOfLight])
    init_pdf = pybayes.pdfs.GaussPdf(mean, cov)

    p_xt_xtp = pybayes.pdfs.GaussCPdf(4, 4, p_xt_xtp_mu, p_xt_xtp_R)
    p_yt_xt  = pybayes.pdfs.GaussCPdf(32, 4, p_yt_xt_mu, p_yt_xt_R)

    filt = pybayes.filters.ParticleFilter(n, init_pdf, p_xt_xtp, p_yt_xt)


def do_filter(info):
    global meas
    if filt is None:
        build_filter(info)

    can_filter = False
    meas = [0] * 32

    for sv in info.prCorrected:
        meas[sv] = info.prCorrected[sv]

        if sv in satinfo.satpos:
            can_filter = True

    if can_filter:
        #print("M:{}".format(meas))
        filt.bayes(numpy.array(meas))
    	print(filt.posterior().mean(), filt.posterior().variance())


#---
while True:
    msg = dev.receive_message(ignore_eof=opts.follow)
    if msg is None:
        break

    try:
        name = msg.name()
        print name
    except ublox.UBloxError as e:
        continue

    msg.unpack()
    satinfo.add_message(msg)

    if name == 'RXM_RAW':
        # The measurements used are Hatch smoothed and with all corrections made that can be
        # made without the state (or with a very rough estimate)

	#for i in satinfo.prCorrected:
        #    print(satinfo.satpos[i].distance(satinfo.receiver_position) + util.speedOfLight * , satinfo.prCorrected[i])

        do_filter(satinfo)


