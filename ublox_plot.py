#!/usr/bin/env python

import ublox, sys, fnmatch, os, time
import numpy, util, math
import matplotlib
from matplotlib import pyplot
from matplotlib.lines import Line2D

from optparse import OptionParser

parser = OptionParser("ublox_plot.py [options] <file>")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")
parser.add_option("--size", type='int', default=20, help="plot size in meters")
parser.add_option("--skip", type='int', default=1, help="show every N positions")
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)

(opts, args) = parser.parse_args()

if opts.reference:
    reference_position = util.ParseLLH(opts.reference)
else:
    reference_position = None

# create a figure
f = pyplot.figure(1)
f.clf()
pyplot.axis([-opts.size,opts.size,-opts.size,opts.size])
pyplot.ion()

colours = ['ro', 'bo', 'go', 'yo']

devs = []
for d in args:
    devs.append(ublox.UBlox(d))

if opts.seek != 0:
    for d in devs:
        d.seek_percent(opts.seek)

last_t = time.time()

def get_xy(pos, home):
    distance = util.gps_distance(home[0], home[1], pos[0], pos[1])
    bearing = util.gps_bearing(home[0], home[1], pos[0], pos[1])
    x = distance * math.sin(math.radians(bearing))
    y = distance * math.cos(math.radians(bearing))
    return (x,y)

def plot_line(pos1, pos2, home, colour):
    global last_t
    (x1,y1) = get_xy(pos1, home)
    (x2,y2) = get_xy(pos2, home)
    pyplot.plot([x1,x2], [y1,y2], colour, linestyle='solid', marker=None, alpha=0.1)
    t = time.time()
    if t - last_t > 1:
        pyplot.draw()
        pyplot.show()
        last_t = t

poscount = [0]*len(devs)
home = None
if reference_position:
    home = (reference_position.lat, reference_position.lon)
last_pos = [None]*len(devs)

while True:
    got_eof = 0
    for i in range(len(devs)):
        d = devs[i]
        msg = d.receive_message(ignore_eof=False)
        if msg is None:
            if opts.follow:
                time.sleep(0.001)
                continue
            got_eof += 1
            break
        if msg.name() == 'NAV_POSLLH':
            msg.unpack()
            pos = (msg.Latitude*1.0e-7, msg.Longitude*1.0e-7)
            if home is None:
                home = pos
            if last_pos[i] is None:
                last_pos[i] = pos
            poscount[i] += 1
            if poscount[i] % opts.skip == 0:
                plot_line(last_pos[i], pos, home, colours[i])
                last_pos[i] = pos
    if got_eof == len(devs):
        break
f.show()
raw_input('Press enter')

