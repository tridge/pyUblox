#!/usr/bin/env python

import ublox, sys, fnmatch, os, time
import numpy, util, math, itertools

from optparse import OptionParser

parser = OptionParser("ublox_stats.py [options] <file>")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")
parser.add_option("--size", type='int', default=20, help="plot size in meters")
parser.add_option("--skip", type='int', default=1, help="show every N positions")
parser.add_option("--reference", help="reference position (lat,lon,alt)", default=None)

(opts, args) = parser.parse_args()

if opts.reference:
    reference_position = util.ParseLLH(opts.reference).ToECEF()
else:
    reference_position = None

def distance(p1, p2):
    return numpy.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

def single_stats(pos):
    '''Calcuates statistics over a time-sequence of position vectors'''
    mean_pos = numpy.mean(pos, axis=0)
    med_pos = numpy.median(pos, axis=0)

    dmeanpos = pos - mean_pos
    dmedpos = pos - med_pos

    std = numpy.std(dmeanpos, axis=0)
    
    dist = numpy.array([numpy.sqrt(p[0]**2 + p[1]**2 + p[2]**2) for p in dmeanpos])
    max_dist_m = max(dist)
    av_dist_m = numpy.mean(dist)

    dist95_m = numpy.percentile(dist,95)

    if reference_position is not None:
        ref_pos = numpy.array([reference_position.X, reference_position.Y, reference_position.Z])
        drefpos = pos - ref_pos
        std = numpy.std(drefpos, axis=0)

        dmeanref = distance(ref_pos, mean_pos)

        dist = numpy.array([numpy.sqrt(p[0]**2 + p[1]**2 + p[2]**2) for p in drefpos])
        max_dist_r = max(dist)
        av_dist_r = numpy.mean(dist)

        dist95_r = numpy.percentile(dist,95)

    st = "Mean:       {}\n".format(mean_pos)
    st+= "Median:     {}\n".format(med_pos)
    st+= "STD:         {}\n".format(std)
    st+= "From Mean::\n"
    st+= "  Max Dist    {}\n".format(max_dist_m)
    st+= "  95% Dist    {}\n".format(dist95_m)
    st+= "  Av Dist     {}\n".format(av_dist_m)

    if reference_position is not None:
        st+= "From Ref::\n"
        st+= "  Max Dist    {}\n".format(max_dist_r)
        st+= "  95% Dist    {}\n".format(dist95_r)
        st+= "  Av Dist     {}\n".format(av_dist_r)

        st+= "Bias          {}\n".format(dmeanref)

    print st

   

def pairwise_stats(p1, p2):
    '''Calculates statistics over two time-sequences of position vectors'''

    l = min(len(p1), len(p2))

    p1 = numpy.array(p1[:l])
    p2 = numpy.array(p2[:l])

    r = p1 - p2
    dist = numpy.array([numpy.sqrt(p[0]**2 + p[1]**2 + p[2]**2) for p in r])

    mp1 = numpy.mean(p1, axis=0)
    mp2 = numpy.mean(p2, axis=0)

    dm = distance(mp1, mp2)
    max_dist = max(dist)
    av_dist = numpy.mean(dist)

    dist95 = numpy.percentile(dist,95)

    if reference_position is not None:
        ref_pos = numpy.array([reference_position.X, reference_position.Y, reference_position.Z])
        ep1 = numpy.array([distance(p, ref_pos) for p in p1])
        ep2 = numpy.array([distance(p, ref_pos) for p in p2])

        imp = ep2 - ep1

        max_imp = max(imp)
        av_imp = numpy.average(imp)
        imp95 = numpy.percentile(imp,95)

    st = "Max Dist    {}\n".format(max_dist)
    st+= "95% Dist    {}\n".format(dist95)
    st+= "Av Dist     {}\n".format(av_dist)

    st+= "Bias        {}\n".format(dm)

    if reference_position is not None:
        st+= "Max Imp     {}\n".format(max_imp)
        st+= "Av Imp      {}\n".format(av_imp)
        st+= "95% Imp     {}\n".format(imp95)

    print st


devs = []
for d in args:
    devs.append((ublox.UBlox(d),d))

if opts.seek != 0:
    for d, name in devs:
        d.seek_percent(opts.seek)

last_t = time.time()

# Load all positions
pos = {}
for i in range(len(devs)):
    pos[i] = []

for i, (d, name) in enumerate(devs):
    while True:
        msg = d.receive_message()
        if msg is None:
            break

        if msg.name() == 'NAV_POSECEF':
            msg.unpack()
            pos[i].append(numpy.array([msg.ecefX / 100., msg.ecefY / 100., msg.ecefZ / 100.]))

for i in pos:
    print(devs[i][1])
    print('---')
    single_stats(pos[i])


for n1, n2 in itertools.combinations(pos.keys(), 2):
    print(devs[n1][1] + '  <--->  ' + devs[n2][1])
    print('---')
    pairwise_stats(pos[n1], pos[n2])




