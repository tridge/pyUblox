#!/usr/bin/env python

import ublox, sys, fnmatch, os

from optparse import OptionParser

parser = OptionParser("ublox_show.py [options] <file>")
parser.add_option("--types", default='*', help="comma separated list of types to show (wildcards allowed)")
parser.add_option("--seek", type='float', default=0, help="seek percentage to start in log")
parser.add_option("-f", "--follow", action='store_true', default=False, help="ignore EOF")

(opts, args) = parser.parse_args()

dev = ublox.UBlox(args[0])

if opts.seek != 0:
    dev.seek_percent(opts.seek)

types = opts.types.split(',')

while True:
    msg = dev.receive_message(ignore_eof=opts.follow)
    if msg is None:
        break
    if types != ['*']:
        matched = False
        try:
            name = msg.name()
        except ublox.UBloxError as e:
            continue
        for t in types:
            if fnmatch.fnmatch(name, t):
                matched = True
                break
        if not matched:
            continue
    try:
        print(str(msg))
    except ublox.UBloxError as e:
        print e.message
    sys.stdout.flush()

