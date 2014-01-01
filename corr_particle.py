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

filt = None
indices = []

def rebuild_filter(m):
    global filt
    
    latest_indices = numpy.where(m>0)[0]

    new = numpy.setdiff1d(latest_indices, indices)
    dropped = numpy.setdiff1d(indices, latest_indices)

    # If our sat set hasn't changed, no need to rebuild
    if len(new) == 0 and len(dropped) == 0:
        return

    if filt is not None:
        last_parts = filt.posterior().particles

    init_mean

    # The initial PDF for corrections are Gaussian particles around the Klobuchar corrections
    mean = numpy.array(m)
    cov = numpy.diag([gps_cov] * 33)
    init_pdf = pybayes.pdfs.GaussPdf(mean, cov)

    # The state transition PDF is just Gaussian around the last state
    cov = [ state_cov ] * 33
    A = numpy.identity(33)
    b = [0] * 33
    p_xt_xtp = pybayes.pdfs.MLinGaussCPdf(cov, a, b)

    # The measurement probability PDF is an EVD, or more precisely a Gumbel Distribution
    # The implementation allows negative b to indicate Gumbel
    p_yt_xt = pybayes.pdfs.EVDCpdf([0] * 33, [gps_cov] * 33)

    filt = pybayes.filters.ParticleFilter(n, init_pdf, p_xt_xtp, p_yt_xt)



#--- From Satlog
with open(args[0], 'r') as f:
    while True:
        r = f.readline()
        if r is None or len(r.split(',')) != 34:
            break

        r = r.split(',')
        r = r[1:] # Trim off timestamp
        m = [ float(s) for s in r ]

        rebuild_filter(m)

        if filt is not None:
            filt.bayes(m)

            print(filt.posterior().mean(), filt.posterior().variance())


