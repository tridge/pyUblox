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
            # Some bug means that huge ranges sometimes get through and stuff the scales.
            # While we search for the bug itself, at least we can stop is messing with the plots
            meas = [ float(m) if abs(float(m)) < 200 else 0
                for m in line.strip().split(',')[1:]] # Cut off the leading timestamp
            l.append(meas)

        satlogs.append(l)

for log in satlogs:
    for i in range(1,len(log)-1):
        for j in range(len(log[i])):
            if log[i][j] == 0 and log[i-1][j] != 0:
                log[i][j] = log[i-1][j]

for sat in range(10):
    sat_dat = []
    for log in satlogs:
        print len(log), len(log[0])
        ranges = [ ep[sat] for ep in log ]

        # if any sat has one log with only empty ranges, move to the next sat
        if not any(ranges):
            break

        sat_dat.append(ranges)
    else:
        plt.figure()
        for log in sat_dat:
            plt.plot(log)

plt.show()
