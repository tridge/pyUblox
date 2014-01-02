#!/usr/bin/env python

import sys
import numpy, math
import scipy.sparse
import pylab as plt

from optparse import OptionParser

import util, ublox

parser = OptionParser("satlog_plot.py [options]")
parser.add_option("--avg", help="Average samples, comma-separated list for multiple satlogs")
parser.add_option("--scale", help="Horizontal scale (rate) factors, comma-separated list for multiple satlogs")

(opts, args) = parser.parse_args()

if opts.avg is not None:
    avgs = [int(a) for a in opts.avg.split(',')]
    avgs = avgs + [1] * (len(args) - len(avgs))
else:
    avgs = [1] * len(args)

if opts.scale is not None:
    scales = [int(a) for a in opts.scale.split(',')]
    scales = scales + [1] * (len(args) - len(scales))
else:
    scales = [1] * len(args)

satlogs = []

def moving_average(a, n):
    if n == 1:
        return a

    r = numpy.cumsum(a, dtype=float)
    return ((r[n-1:] - r[:1-n]) / n).tolist()

def trimmed_average(a, n):
    out = []
    if n == 1:
        return a

    for i in range(len(a) - n):
        window = a[i:i+n]
        t = sorted(window)[n // 4: 3 * n // 4]
        out.append(sum(t) / len(t))

    return out

for log, avg in zip(args, avgs):
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

for sat in range(30):
    sat_dat = []
    #print('---' + str(sat) + '---')
    for log, avg, scale in zip(satlogs, avgs, scales):
        ranges = []
        for r in [ ep[sat] for ep in log ]:
            ranges += [r] * scale


        #ranges = moving_average(ranges, avg)
        ranges = trimmed_average(ranges, avg)
        ranges = [0] * (avg // 2) + ranges + [0] * (avg // 2)

        # if any sat has one log with only empty ranges, move to the next sat
        #if not any(ranges):
        #    break

        sat_dat.append(ranges)

        #print(numpy.average(ranges), numpy.std(ranges))
    else:
        ax = plt.subplot(5, 6, sat)
        for log in sat_dat:
            ax.plot(log)

plt.show()
