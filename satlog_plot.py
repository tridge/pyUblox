#!/usr/bin/env python

import sys
import numpy, math
import scipy.sparse
import pylab as plt

from optparse import OptionParser

import util, ublox

satlogs = []

for log in sys.argv[1:]:
    l = []
    with open(log) as f:
        for line in f:
            meas = [ float(m) if abs(float(m)) < 200 else 0 for m in line.strip().split(',')[1:]] # Cut off the leading timestamp
            #if any([abs(r) > 100 for r in meas]):
            #    print line
            #else:
            l.append(meas)

        satlogs.append(l)

for sat in range(5):
    sat_dat = []
    for log in satlogs:
        print len(log), len(log[0])
        ranges = [ ep[sat] for ep in log ]

        # if any sat has one log with only empty ranges, move to the next sat
        if not any([r for r in ranges]):
            break

        sat_dat.append(ranges)
    else:
        plt.figure()
        for log in sat_dat:
            plt.plot(log)

plt.show()
