#!/usr/bin/env python

import ublox, sys, fnmatch, os, time
import util, satelliteData, positionEstimate
import numpy

from mpl_toolkits.axes_grid1 import host_subplot
import mpl_toolkits.axisartist as AA
import matplotlib.pyplot as plt

from optparse import OptionParser

parser = OptionParser("ublox_pr_plot.py [options] <file>")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)
parser.add_option("--sats", type='int', help="Satellite to plot")

(opts, args) = parser.parse_args()

if opts.reference:
    reference_position = util.ParseLLH(opts.reference)

dev = ublox.UBlox(args[0])

if opts.seek != 0:
    for d in devs:
        d.seek_percent(opts.seek)

sat = opts.sats

geo = {}
pr = {}
sm = {}
cr = {}
qi = {}
slip = {}

# Here on mostly coded to support multiple sats
sats = [sat]

for sv in sats:
    geo[sv] = []
    pr[sv] = []
    sm[sv] = []
    cr[sv] = []
    qi[sv] = []
    slip[sv] = []

satinfo = satelliteData.SatelliteData()
satinfo.reference_position = util.ParseLLH(opts.reference).ToECEF()

satinfo.min_elevation = 0
satinfo.min_quality = 0

while True:
    msg = dev.receive_message(ignore_eof=False)

    if msg is None:
        break

    if msg.name() in ['RXM_RAW', 'RXM_SFRB', 'AID_EPH']:
        msg.unpack()
        satinfo.add_message(msg)
    else:
        continue

    if msg.name() == 'RXM_RAW':
        positionEstimate.positionEstimate(satinfo)

        for r in msg.recs:
            if r.sv not in sats:
                continue

            if not satinfo.valid(r.sv):
                continue

            geo[r.sv].append(satinfo.reference_position.distance(satinfo.satpos[r.sv]))
            pr[r.sv].append(satinfo.prMeasured[r.sv] + util.speedOfLight*satinfo.receiver_clock_error)
            sm[r.sv].append(satinfo.prSmoothed[r.sv] + util.speedOfLight*satinfo.receiver_clock_error)
            cr[r.sv].append(satinfo.prCorrected[r.sv] + util.speedOfLight * satinfo.receiver_clock_error)
            qi[r.sv].append(r.mesQI)

            slip[r.sv].append(1 if satinfo.smooth.N[r.sv] == 1 else 0)


smdelta = numpy.array(pr[sat]) - numpy.array(sm[sat])
res = numpy.array(geo[sat]) - numpy.array(cr[sat])

print(satinfo.satpos.keys())

host = host_subplot(111, axes_class=AA.Axes)
plt.subplots_adjust(right=0.75)

par1 = host.twinx()
par2 = host.twinx()

offset = 60
new_fixed_axis = par2.get_grid_helper().new_fixed_axis
par2.axis["right"] = new_fixed_axis(loc="right",
                                        axes=par2,
                                        offset=(offset, 0))

par2.axis["right"].toggle(all=True)

host.set_xlim(0, len(geo[sat]))
host.set_ylim(min(geo[sat]), max(geo[sat]))
par1.set_ylim(0, 8)

yl = min(min(res),min(smdelta))
yh = max(max(res),max(smdelta))

par2.set_ylim(yl, yh)

host.set_xlabel("Time")
host.set_ylabel("Range")
par1.set_ylabel("Quality")
par2.set_ylabel("Smoothing")

host.plot(range(len(geo[sat])), geo[sat], label="Geometric Range")
host.plot(range(len(pr[sat])), pr[sat], label="Pseudorange")
host.plot(range(len(sm[sat])), sm[sat], label="Smoothed Range")
host.plot(range(len(cr[sat])), cr[sat], label="Corrected Range")

par1.plot(range(len(qi[sat])), qi[sat], label="Quality")
par1.plot(range(len(slip[sat])), slip[sat], label="Slip")

par2.plot(range(len(smdelta)), smdelta, label="Smoothing")
par2.plot(range(len(res)), res, label="Residual")

host.legend()

plt.draw()
plt.show()

raw_input('Press enter')

