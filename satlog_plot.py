#!/usr/bin/env python

import sys
import numpy

from pylab import *

from optparse import OptionParser

import satelliteData, satPosition, util

parser = OptionParser("satlog_plot.py [options]")
parser.add_option("--satlog", help="Satellite data log", default='satlog.txt')
parser.add_option("--errlog", help="Position error log", default='errlog.txt')
parser.add_option("--target", type=int, help="Sample number around which to examine", default=None)
parser.add_option("--window", type=int, help="Window around target sample point to examine", default=1000)
parser.add_option("--badness-thresh", type=float, help="Extra error introduced by DGPS procedure before a segment is marked bad", default=2)
parser.add_option("--ubx-log", help="Optional uBlox log file from which Ephemerides might be extracted", default=None)
parser.add_option("--ref-ecef", help="ECEF reference position against which to plot satellite positions")

(opts, args) = parser.parse_args()

sat_errs = []
max_svid = 33
last_svid = max_svid + 1

def moving_average(a, n):
    r = numpy.cumsum(a, dtype=float)
    return (r[n-1:] - r[:1-n]) / n

start_time = -1
satinfo = satelliteData.SatelliteData()
satinfo.save_files = False

if opts.ref_ecef is not None:
    satinfo.reference_position = util.PosVector(*opts.ref_ecef.split(','))

if opts.ubx_log is not None:
    import ublox

    dev = ublox.UBlox(opts.ubx_log)

    while True:
        '''process the ublox messages, extracting the ones we need for the position'''
        msg = dev.receive_message()
        if msg is None:
            break
        if msg.name() == 'AID_EPH':
            try:
                msg.unpack()
                satinfo.add_message(msg)
            except ublox.UBloxError as e:
                print(e)
        if msg.name() == 'RXM_RAW' and start_time == -1:
            msg.unpack()
            start_time = msg.iTOW*1.0e-3

with open(opts.satlog, mode='r') as f:
    f.readline()

    for l in f:
        svid, geo, sm, cl, adj, err = l.split()

        svid = int(svid)

        if svid < last_svid:
            sat_errs.append([0] * max_svid)

        last_svid = svid

        sat_errs[-1][svid] = float(err)

p_err = []
dg_err = []
with open(opts.errlog, mode='r') as f:
    f.readline()

    for l in f:
        n, d, nxy, dxy = l.split()

        p_err.append(float(n))
        dg_err.append(float(d))


if abs(len(sat_errs) - len(p_err)) > 1:
    print("Data mismatch, {sat} Sat points but {p} Pos points".format(sat=len(sat_errs), p=len(p_err)))
    min_len = min(len(sat_errs), len(p_err))
    sat_errs = sat_errs[:min_len]
    p_err = p_err[:min_len]
    dg_err = dg_err[:min_len]

# trim off the last element of each array which may contain incomplete
# data, depending when the logging was stopped
p_err = numpy.array(p_err[:-1])
dg_err = numpy.array(dg_err[:-1])
sat_errs = numpy.array(sat_errs[:-1])

rel_err = moving_average(dg_err - p_err, opts.window)

# Slight trickery: returns a list of tuples where each tuple contains
# the first and last index of a region where the rel_err data set is
# above the badness threshold
clumps = [(q[0],q[-1]) for q in numpy.split(numpy.arange(len(rel_err)), numpy.where(rel_err < opts.badness_thresh)[0]) if len(q) > 1]

print clumps

csat_errs = []

clump_satdata = [[None] * max_svid for i in range(len(clumps))]

for cnum, clump in enumerate(clumps):
    maxi = numpy.max(sat_errs[clump[0]:clump[1]][:], axis=0)
    mini = numpy.min(sat_errs[clump[0]:clump[1]][:], axis=0)
    clump_errs = numpy.where(abs(maxi) > abs(mini), maxi, mini)
    csat_errs.append(clump_errs)

    for s_ent, err in enumerate(clump_errs):
        if err == 0:
            continue

        sv = s_ent + 1

        t = start_time + (clump[0] + clump[1]) / 2
        if sv in satinfo.ephemeris and satinfo.ephemeris[sv].valid and satinfo.reference_position is not None:
            satPosition.satPosition(satinfo, sv, t)
            satPosition.calculateAzimuthElevation(satinfo, sv, satinfo.reference_position)
            clump_satdata[cnum][s_ent] = (sv, err, satinfo.azimuth[sv], satinfo.elevation[sv])
        

print numpy.array(csat_errs).T

for c_num, clump in enumerate(clump_satdata):
    theta = [s[2] * numpy.pi / 180 for s in clump if s is not None and s[3] > 0]
    r = [s[3] for s in clump if s is not None and s[3] > 0]

    print(theta,r)


