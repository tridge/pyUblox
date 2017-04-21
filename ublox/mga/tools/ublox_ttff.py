#!/usr/bin/python

# Peter Barker
# 2017-04-13

# test a uBlox GPS to see how long it takes to get first fix.  may use
# a script to power-cycle the GPS unit; I use an Arduino sketch to
# toggle a pin which toggles a relay.

import re
import StringIO
import sys
import time

import ublox
import ublox.mga.dbd
import ublox.mga.tool
import ublox.mga.offline

class TTFF(ublox.mga.tool.MGATool):
    def __init__(self):
        self.state_deathly_cold = 14
        self.state_waiting_for_messages = 15
        self.state_waiting_for_nav_status = 16
        self.state_configuring = 17
        self.state_fix_acquired = 18
        self.state_first_configure = 19
        self.state_uploading_mga_dbd = 20
        self.state_waiting_reset = 21
        self.state_uploading_time = 22
        self.state_uploading_position = 23
        self.state_consider_aiding = 24
        self.state_configure_ack_aiding = 25
        self.state_uploading_mga_offline = 26

    def configure_dev(self):
#        self.dev.set_logfile(opts.log, append=opts.append)
        self.dev.set_binary()
        self.dev.configure_poll_port()
#        self.dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
#        self.dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
        self.dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_VER)
        self.dev.configure_port(port=ublox.PORT_SERIAL1, inMask=1, outMask=1)
#        self.dev.configure_port(port=ublox.PORT_USB, inMask=1, outMask=1)
#        self.dev.configure_port(port=ublox.PORT_SERIAL2, inMask=1, outMask=1)
        self.dev.configure_poll_port()
        self.dev.configure_poll_port(ublox.PORT_SERIAL1)
#        self.dev.configure_poll_port(ublox.PORT_SERIAL2)
#        self.dev.configure_poll_port(ublox.PORT_USB)
        self.dev.configure_solution_rate(rate_ms=1000)

        # self.dev.set_preferred_dynamic_model(opts.dynModel)
        # self.dev.set_preferred_usePPP(opts.usePPP)

        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_STATUS, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_ALM, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_EPH, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_TIMEGPS, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_CLOCK, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DOP, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_PVT, 1)
        self.dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)

    def get_fix(self, mga_dbd_source_dev=None, mga_offline_cache_file=None, position=None):
        self.state = self.state_deathly_cold

        lat = 0
        lon = 0
        fix = 0
        self.start_time = time.time()
        while self.state != self.state_fix_acquired:
            now = time.time()
            if self.state == self.state_deathly_cold:
                print("resetting module")
                self.dev.module_reset(0xffff, 0x00)
                self.state = self.state_first_configure
                # fall through....
            if self.state == self.state_first_configure:
                self.configure_dev()
                self.state = self.state_configuring
            msg = self.dev.receive_message()
#            sys.stdout.write("msg: %s\r" % (msg,))
            if msg is not None:
                msg.unpack()
                print(str(msg))
                if msg.msg_type() == (ublox.CLASS_NAV, ublox.MSG_NAV_PVT):
                    fix = msg.fixType
                elif msg.msg_type() == (ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH):
                    lat = msg.Latitude
                    lon = msg.Longitude

                string = "\r%4u lat=%u lon=%u fix=%u state=%u                                 " % (now-self.start_time, lat, lon, fix, self.state)
#                sys.stdout.write(string)
#                sys.stdout.flush()

            if self.state == self.state_configuring:
                if msg is not None:
                    if msg.msg_type() == (ublox.CLASS_NAV, ublox.MSG_NAV_PVT):
                        if msg.iTOW > 2000:
                            self.state = self.state_first_configure
                            continue
                    self.state = self.state_consider_aiding
                else:
                    self.configure_dev()
                # fall through
            if self.state == self.state_consider_aiding:
                if (mga_dbd_source_dev is not None
                    or mga_offline_cache_file is not None):
                    self.state = self.state_configure_ack_aiding
                else:
                    self.state = self.state_waiting_for_nav_status
            if self.state == self.state_configure_ack_aiding:
                print("Configuring ack-aiding")
                self.configure_dev_ack_aiding()
                self.state = self.state_uploading_time
#                self.state = self.state_uploading_mga_dbd
                # fall through
            if self.state == self.state_uploading_time:
                # perhaps we should wait until ack-aiding is set
                # before doing this, and wait for an ack....
                self.sendtime() # this blocks for ack
                self.state = self.state_uploading_position
            if self.state == self.state_uploading_position:
                # perhaps we should wait until ack-aiding is set
                # before doing this, and wait for an ack....
                if position is not None:
                    self.sendposition(position) # this blocks for ack
                self.state = self.state_uploading_mga_dbd
            if self.state == self.state_uploading_mga_dbd:
                if mga_dbd_source_dev is not None:
                    self.mga_dbd = ublox.mga.dbd.DBD()
                    self.mga_dbd.dev = self.dev
                    print("Uploading MGA DataBase")
                    self.mga_dbd.upload_mga_dbd(mga_dbd_source_dev)
                    print("Uploaded MGA DataBase")
                self.state = self.state_uploading_mga_offline
            if self.state == self.state_uploading_mga_offline:
                if mga_offline_cache_file is not None:
                    print("Uploading MGA Offline data")
                    cache = ublox.mga.offline.Offline(cachefile=mga_offline_cache_file)
                    cache.upload(self.dev)
                    print("Uploaded MGA Offline data")
                self.state = self.state_waiting_for_nav_status
            if msg is None:
                time.sleep(0.01)
                continue
            if self.state == self.state_waiting_for_nav_status:
                if msg.msg_type() == (ublox.CLASS_NAV, ublox.MSG_NAV_PVT):
                    if msg.fixType == 0x03:
                        print("\n3D fix aquired after %u seconds" % (now-self.start_time))
#                        print("msg: %s" % (str(msg),))
                        self.state = self.state_fix_acquired
                        continue
                continue

    def run(self):
        from optparse import OptionParser

        parser = OptionParser("ttff.py")
        parser.add_option("--port", help="serial port", default='/dev/ttyUSB0')
        parser.add_option("--baudrate", type='int',
                          help="serial baud rate", default=9600)
        parser.add_option("--mga-dbd", help="mga dbd data file", default=None)
        parser.add_option("--mga-offline", help="mga offline cache file", default=None)
        parser.add_option("--position", help="position e.g. 149.0420946,-35.2103418,652.954", default=None)
        (opts, args) = parser.parse_args()

        self.dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
#        self.get_fix()

        mga_dbd = ublox.mga.dbd.DBD()
#        mga_dbd.dev = self.dev
#        mga_dbd.download_mga_dbd()
#        print("Downloaded %u messages" % len(mga_dbd.messages))
#        source_dev = ublox.UBlox(mga_dbd.messages_fh())

        dbd_source_dev = None
        if opts.mga_dbd is not None:
            fh = open(opt.mga_dbd, "r")
            dbd_source_dev = ublox.UBlox(fh)

        split_position = None
        if opts.position is not None:
            split_position = opts.position.split(",")
            if len(split_position) < 3:
                raise ValueError("position must have at least three components")
            if len(split_position) < 4:
                split_position.append(100000) # default 100km accuracy
            split_position = tuple([ float(x) for x in split_position])
        self.get_fix(mga_dbd_source_dev=dbd_source_dev,
                     mga_offline_cache_file=opts.mga_offline,
                     position=split_position)


ttff = TTFF()
ttff.run()
