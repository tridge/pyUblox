#!/usr/bin/python

# Peter Barker
# 2017-04-21


from __future__ import print_function

import optparse
import os
import sys

import ublox.util
import ublox.mga.tool
import ublox.mga.offline

#mgaoffline = mga.MGAOffline(token="bob")
#mgaoffline.make_request()
#sys.exit(1)

class MGAOffline(ublox.mga.tool.MGATool):
    def __init__(self):
        pass
    def run(self):
        parser = optparse.OptionParser("mga-offline.py")
#        parser.add_option("--port", help="serial port", default='/dev/ttyUSB0')
#        parser.add_option("--baudrate", type='int',
#                          help="serial baud rate", default=115200)

        parser.add_option("--file", help="Data file", default="mga-offline.ubx")
        (opts, args) = parser.parse_args()
        parser.usage += " download [OPTIONS]"

        if len(args) < 1:
            print(parser.format_help())
            sys.exit(1)

        cmd = args[0]
        args = args[1:]

        cache = ublox.mga.offline.Offline(cachefile=opts.file)

        if cmd == "download":
            cache.freshen()
        else:
            print("Unknown command %s" % (cmd))

tool = MGAOffline()
tool.run()
