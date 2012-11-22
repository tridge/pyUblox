#!/usr/bin/env python

import ublox, sys, fnmatch, os, time
import numpy, util, math
from matplotlib import pyplot
from matplotlib.lines import Line2D

from optparse import OptionParser

parser = OptionParser("ublox_plot.py [options] <file>")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")
parser.add_option("--size", type='int', default=20, help="plot size in meters")

(opts, args) = parser.parse_args()

# create a figure
f = pyplot.figure(1)
f.clf()
pyplot.axis([-opts.size,opts.size,-opts.size,opts.size])
pyplot.ion()

dev = ublox.UBlox(args[0])

if opts.seek != 0:
    dev.seek_percent(opts.seek)

home = None
last_pos = None
last_t = time.time()

def get_xy(pos):
    global home
    distance = util.gps_distance(home[0], home[1], pos[0], pos[1])
    bearing = util.gps_bearing(home[0], home[1], pos[0], pos[1])
    x = distance * math.sin(math.radians(bearing))
    y = distance * math.cos(math.radians(bearing))
    print distance
    return (x,y)

def plot_line(pos1, pos2):
    global last_t
    (x1,y1) = get_xy(pos1)
    (x2,y2) = get_xy(pos2)
    pyplot.plot([x1,x2], [y1,y2], 'ro', linestyle='solid', marker='.')
    t = time.time()
    if t - last_t > 1:
        pyplot.draw()
        pyplot.show()
        last_t = t

while True:
    msg = dev.receive_message(ignore_eof=opts.follow)
    if msg is None:
        break
    if msg.name() == 'NAV_POSLLH':
        msg.unpack()
        pos = (msg.Latitude*1.0e-7, msg.Longitude*1.0e-7)
        if home is None:
            home = pos
            last_pos = pos
        plot_line(last_pos, pos)
        last_pos = pos
        print pos
f.show()
time.sleep(5)
