#!/usr/bin/env python

import sys
import numpy, math
import scipy.sparse
import pylab as plt

from optparse import OptionParser

import util, ublox

parser = OptionParser("satlog_plot.py [options]")
parser.add_option("--errlog", help="Position error log", default='errlog.txt')
parser.add_option("--target", type=int, help="Sample number around which to examine", default=None)
parser.add_option("--window", type=int, help="Window around target sample point to examine", default=1000)
parser.add_option("--badness-thresh", type=float, help="Extra error introduced by DGPS procedure before a segment is marked bad", default=2)
parser.add_option("--ubx-log", help="Optional uBlox log file from which Ephemerides might be extracted", default='port1.log')
parser.add_option("--save-pos", help="Save satellite positions once parsed from UBX log", default=None)
parser.add_option("--load-pos", help="Load a previously saved satellite position log", default=None)
parser.add_option("--skip-plot", help="Rate at which to decimate samples when plotting", default=100)
parser.add_option("--plot-clusters", help="Plot skyviews split in to performance clusters", action='store_true')
parser.add_option("--split-by-time", type=float, default=None, help="Plot the error performance split in to periods")
parser.add_option("--timezone", type=float, default=10.0, help="Receiver time zone, used only to display good plot labels")

(opts, args) = parser.parse_args()

sat_errs = []
max_svid = 33
last_svid = max_svid + 1

def moving_average(a, n):
    r = numpy.cumsum(a, dtype=float)
    return (r[n-1:] - r[:1-n]) / n

def gps_to_time(t):
    day = t // 86400
    hour = (t - 86400 * day) // (60 * 60)
    minute = (t - 86400 * day - 60 * 60 * hour) // 60
    second = t - 86400 * day - 60 * 60 * hour - 60 * minute

    return (day, hour, minute, second)

def format_time(time):
    return "{}:{}".format(int(time[1]), int(time[2]))

sat_el, sat_az = None, None
t_first = 0
t_last = 0
t_wrap = 0

if opts.load_pos is not None:
    t_first = util.loadObject(opts.load_pos + '.stamp')
    if opts.plot_clusters:
        sat_el, sat_az = util.loadObject(opts.load_pos)

    print("Loaded")

if (sat_el is None or sat_az is None or t_first is None) and opts.plot_clusters:
    print("Parsing UBX")
    dev = ublox.UBlox(opts.ubx_log)
    # Create storage for all sats (inc SBAS), 80 hours, (elev,azim); this is sparse so
    # overestimating time doesn't hurt and we trim it back before using
    # it below anyway.  This would be nicer if sparse arrays supported tuple elements
    # but they don't..
    sat_el = scipy.sparse.lil_matrix((80*60*60, 140))
    sat_az = scipy.sparse.lil_matrix((80*60*60, 140))


    while True:
        '''process the ublox messages, extracting the ones we need for the sat position'''
        msg = dev.receive_message()
        if msg is None:
            break
        if msg.name() == 'NAV_SVINFO':
            msg.unpack()
            t = msg.iTOW * 0.001

            if t_first == 0:
                t_first = t

            if t_last != 0 and t - t_last >= 2:
                print("Missed Epoch")

            if t < t_first and t_wrap == 0:
                t_wrap = t_last

            t += t_wrap

            t_last = t

            for s in msg.recs:
                if not s.flags & 1: # ignore svs not used in soln
                    continue
                sat_el[t - t_first, s.svid] = s.elev
                sat_az[t - t_first, s.svid] = s.azim

if opts.save_pos is not None:
    util.saveObject(opts.save_pos, (sat_el, sat_az))
    util.saveObject(opts.save_pos + '.stamp', t_first)
    print("Saved OK")

p_err = []
dg_err = []
with open(opts.errlog, mode='r') as f:
    f.readline()

    for l in f:
        n, d, nxy, dxy = l.split()

        p_err.append(float(n))
        dg_err.append(float(d))


# trim off the last element of each array which may contain incomplete
# data, depending when the logging was stopped
p_err = numpy.array(p_err[:-1])
dg_err = numpy.array(dg_err[:-1])

plt.figure()

rel_err = moving_average(dg_err - p_err, opts.window)

if opts.split_by_time is not None:
    nplots = int(math.ceil(len(rel_err) / (opts.split_by_time * 60.0 * 60.0)))
    plen = int(opts.split_by_time * 60.0 * 60.0)
    offset_time = opts.split_by_time / 2
else:
    nplots = 1
    plen = len(rel_err)
    offset_time = 0

t_local = int(t_first + (opts.timezone * 60 * 60))

plt.suptitle("Relative error between corrected and uncorrected rovers")

ymin = min(0, min(rel_err) * 1.2)
ymax = max(rel_err) * 1.2

for i in range(nplots):
    ax = plt.subplot(nplots, 1, i + 1)

    tick_pos = range(0, plen, 30*60)
    tick_label = [format_time(gps_to_time(t_local + i * plen + offset_time + x)) for x in tick_pos]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_label, rotation=45)
    ax.set_xlim(0, plen)
    ax.set_ylim(ymin, ymax)

    dat = rel_err[i * plen: min(len(rel_err), (i+1)*plen)]

    ax.plot(dat, color='black')

    ax.fill_between(numpy.arange(len(dat)), dat, 0, dat > opts.badness_thresh, color='red', alpha=0.75)
    ax.fill_between(numpy.arange(len(dat)), dat, 0, (dat > 0) & (dat < opts.badness_thresh), color='orange', alpha=0.75)
    ax.fill_between(numpy.arange(len(dat)), dat, 0, dat < -opts.badness_thresh, color='green', alpha=0.75)
    ax.fill_between(numpy.arange(len(dat)), dat, 0, (dat < 0) & (dat > -opts.badness_thresh), color='blue', alpha=0.75)


plt.figure()
plt.suptitle("Corrected/Uncorrected Errors w.r.t. Ground Truth")

ymin = min(0, min(p_err), min(dg_err)) * 1.2
ymax = max(max(p_err), max(dg_err)) * 1.2

for i in range(nplots):
    ax = plt.subplot(nplots, 1, i + 1)

    tick_pos = range(0, plen, 30*60)
    tick_label = [format_time(gps_to_time(t_local + i * plen + x)) for x in tick_pos]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_label, rotation=45)
    ax.set_xlim(0, plen)
    ax.set_ylim(ymin, ymax)

    ax.plot(p_err[i * plen: min(len(rel_err), (i+1)*plen)], color='red')
    ax.plot(dg_err[i * plen: min(len(rel_err), (i+1)*plen)], color='green')

if opts.plot_clusters:
    plt.figure()
    plt.suptitle("Bad Clump Constellations")
    # Bad clumps

    # Slight trickery: returns a list of tuples where each tuple contains
    # the first and last index of a region where the rel_err data set is
    # above the badness threshold.  Indices are generated in to the original
    # data rather than the averaged set, hence the offset by half the window
    # size
    clumps = [(q[0] + opts.window // 2,q[-1] + opts.window // 2)
                for q in numpy.split(numpy.arange(len(rel_err)), numpy.where(rel_err < opts.badness_thresh)[0])
                if len(q) > 1]

    cols = math.floor(math.sqrt(len(clumps)))
    rows = math.ceil(len(clumps) / cols)

    for plot, clump in enumerate(clumps):

        els = []
        for i in range(clump[0],clump[1], opts.skip_plot):
            els.append([math.cos(e * math.pi / 180.) for e in sat_el[i,:].toarray()[0]])

        azs = []
        for i in range(clump[0], clump[1], opts.skip_plot):
            azs.append([a * math.pi / 180. for a in sat_az[i,:].toarray()[0]])

        # This hideous lump of bollocks scans through the position arrays and ensures
        # that any zero-entries at the beginning or end are set to the first/last non-
        # zero entry respectively.  This stops the plotter drawing lines back to the origin
        # if a sat drops out.  Ideally we'd just remove zero-entries completely however
        # the matrix structure laid out here doesn't really lend itself to that..
        for i in range(1,len(els)):
            for svid in range(len(els[i])):
                if els[i - 1][svid] != 0 and els[i][svid] == 0:
                    els[i][svid] = els[i - 1][svid]
                    azs[i][svid] = azs[i - 1][svid]

        for i in range(len(els)-1,0,-1):
            for svid in range(len(els[i])):
                if els[i][svid] != 0 and els[i - 1][svid] == 0:
                    els[i - 1][svid] = els[i][svid]
                    azs[i - 1][svid] = azs[i][svid]

        for i in range(1,len(azs)):
            for svid in range(len(azs[i])):
                if azs[i - 1][svid] != 0 and azs[i][svid] == 0:
                    els[i][svid] = els[i - 1][svid]
                    azs[i][svid] = azs[i - 1][svid]

        for i in range(len(azs)-1,0,-1):
            for svid in range(len(azs[i])):
                if azs[i][svid] != 0 and azs[i - 1][svid] == 0:
                    els[i - 1][svid] = els[i][svid]
                    azs[i - 1][svid] = azs[i][svid]



        ax = plt.subplot(rows, cols, plot + 1, polar=True)
        ax.set_rmax(1.0)
        ax.plot(azs, els)


    # Good clumps

    clumps = [(q[0] + opts.window // 2,q[-1] + opts.window // 2)
                for q in numpy.split(numpy.arange(len(rel_err)), numpy.where(rel_err > -opts.badness_thresh)[0])
                if len(q) > 1]

    cols = 3.
    rows = math.ceil(len(clumps) / cols)

    plt.figure()
    plt.suptitle("Good Clump Constellations")

    for plot, clump in enumerate(clumps):

        els = []
        for i in range(clump[0],clump[1], opts.skip_plot):
            els.append([math.cos(e * math.pi / 180.) for e in sat_el[i,:].toarray()[0]])

        azs = []
        for i in range(clump[0], clump[1], opts.skip_plot):
            azs.append([a * math.pi / 180. for a in sat_az[i,:].toarray()[0]])

        for i in range(1,len(els)):
            for svid in range(len(els[i])):
                if els[i - 1][svid] != 0 and els[i][svid] == 0:
                    els[i][svid] = els[i - 1][svid]
                    azs[i][svid] = azs[i - 1][svid]

        for i in range(len(els)-1,0,-1):
            for svid in range(len(els[i])):
                if els[i][svid] != 0 and els[i - 1][svid] == 0:
                    els[i - 1][svid] = els[i][svid]
                    azs[i - 1][svid] = azs[i][svid]

        for i in range(1,len(azs)):
            for svid in range(len(azs[i])):
                if azs[i - 1][svid] != 0 and azs[i][svid] == 0:
                    els[i][svid] = els[i - 1][svid]
                    azs[i][svid] = azs[i - 1][svid]

        for i in range(len(azs)-1,0,-1):
            for svid in range(len(azs[i])):
                if azs[i][svid] != 0 and azs[i - 1][svid] == 0:
                    els[i - 1][svid] = els[i][svid]
                    azs[i - 1][svid] = azs[i][svid]

        ax = plt.subplot(rows, cols, plot + 1, polar=True)
        ax.set_rmax(1.0)
        ax.plot(azs, els)

plt.show()

    



