#!/usr/bin/python

# Peter Barker
# 2017-04-13

from __future__ import print_function

import ublox

import datetime
import struct


class MGA:
    @staticmethod
    def msg_ini_time_utc(datetime_utc=None):
        '''send datetime_utc to the module (defaults to 'utcnow')'''
        if datetime_utc is None:
             datetime_utc = datetime.datetime.utcnow()
        version = 0x00
        ref = 0 # valid on receipt of message
        leapSecs = -128 # unknown
        reserved1 = 0
        tAccS = 1
        reserved2 = [0,0]
        tAccNs = 999999999
        fmt = ublox.msg_types[(ublox.CLASS_MGA, ublox.MSG_MGA_INI_TIME_UTC, ublox.MSG_MGA_INI_TYPE_TIME_UTC)].msg_format
        nanosecond = 0
        payload = struct.pack(fmt,
                              ublox.MSG_MGA_INI_TYPE_TIME_UTC,
                              version,
                              ref,
                              leapSecs,
                              datetime_utc.year,
                              datetime_utc.month,
                              datetime_utc.day,
                              datetime_utc.hour,
                              datetime_utc.minute,
                              datetime_utc.second,
                              reserved1,
                              nanosecond,
                              tAccS,
                              0, # reserved2
                              0, # reserved2
                              tAccNs
        )
        return ublox.UBlox.pack_message(ublox.CLASS_MGA, ublox.MSG_MGA_INI_TIME_UTC, payload)

    @staticmethod
    def msg_ini_pos_llh(position):
        '''send position to the module'''
        if position is None:
             raise ValueError("Position must be supplied")
        version = 0x00
        reserved1 = [0,0]
        fmt = ublox.msg_types[(ublox.CLASS_MGA, ublox.MSG_MGA_INI_POS_LLH, ublox.MSG_MGA_INI_TYPE_POS_LLH)].msg_format
        nanosecond = 0
        print("position: %s  fmt=%s" % (str(position), str(fmt)))
        (lat, lon, alt, prec) = position
        payload = struct.pack(fmt,
                              ublox.MSG_MGA_INI_TYPE_POS_LLH,
                              version,
                              reserved1[0],  # check byte ordering!
                              reserved1[1],
                              lat*1e7,
                              lon*1e7,
                              alt*100,
                              prec*100
        )
        return ublox.UBlox.pack_message(ublox.CLASS_MGA, ublox.MSG_MGA_INI_POS_LLH, payload)

import requests
import StringIO
import os.path
class Requester(object):
    def __init__(self, token):
        self.token = token

    def make_request(self):
        params = self.request_params()
        escaped = ";".join([ ("%s=%s" % (key,params[key])) for key in params])
        url = "%s?%s" % (self.script_url(), escaped)
#        print("URL: %s" % str(url))
        r = requests.get(url)
        r.raise_for_status()
        ret = StringIO.StringIO()
        for block in r.iter_content(1024):
            ret.write(block)
        ret.seek(0);
        return ret

    def script_url(self):
        return 'http://%s:%u/%s' % (self.hostname(),self.hostport(),self.scriptpath())

    def hostname(self):
#        return 'localhost'
        return 'offline-live1.services.u-blox.com'

    def hostport(self):
#        return 8000
        return 80
