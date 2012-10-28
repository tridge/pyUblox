#!/usr/bin/env python

import struct
import serial
from datetime import datetime
import time, os

PREAMBLE1 = 0xb5
PREAMBLE2 = 0x62

CLASS_NAV = 0x01
CLASS_RXM = 0x02
CLASS_ACK = 0x05
CLASS_CFG = 0x06

MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01

MSG_NAV_POSLLH = 0x2
MSG_NAV_STATUS = 0x3
MSG_NAV_SOL    = 0x6
MSG_NAV_VELNED = 0x12
MSG_NAV_SVINFO = 0x30

MSG_RXM_RAW    = 0x10
MSG_RXM_SFRB   = 0x11
MSG_RXM_SVSI   = 0x20

MSG_CFG_PRT = 0x00
MSG_CFG_USB = 0x1b
MSG_CFG_RATE = 0x08
MSG_CFG_SET_RATE = 0x01
MSG_CFG_NAV_SETTINGS = 0x24

PORT_SERIAL1=1
PORT_SERIAL2=2
PORT_USB    =3


class UBloxDescriptor:
    def __init__(self, name, msg_format, fields=[], count_field=None, format2=None, fields2=None):
        self.name = name
        self.msg_format = msg_format
        self.fields = fields
        self.count_field = count_field
        self.format2 = format2
        self.fields2 = fields2

    def format(self, msg):
        size1 = struct.calcsize(self.msg_format)
        buf = msg.buf[6:-2]
        ret = 'UBloxMessage(%s, ' % self.name
        if size1 > len(buf):
            ret +=  "INVALID_SIZE=%u, " % len(buf)
            return ret[:-2] + ')'
        count = 0
        f1 = list(struct.unpack(self.msg_format, buf[:size1]))
        for i in range(len(self.fields)):
            ret += '%s=%s, ' % (self.fields[i], f1[i])
            if self.count_field == self.fields[i]:
                count = int(f1[i])
        if count == 0:
            return ret[:-2] + ')'
        buf = buf[size1:]
        size2 = struct.calcsize(self.format2)
        for c in range(count):
            ret += '[ '
            if size2 > len(buf):
                ret +=  "INVALID_SIZE=%u, " % len(buf)
                return ret[:-2] + ')'
            f2 = list(struct.unpack(self.format2, buf[:size2]))
            for i in range(len(self.fields2)):
                ret += '%s=%s, ' % (self.fields2[i], f2[i])
            buf = buf[size2:]
            ret = ret[:-2] + ' ], '
        if len(buf) != 0:
                ret +=  "EXTRA_BYTES=%u, " % len(buf)            
        return ret[:-2] + ')'
        

msg_types = {
    (CLASS_NAV, MSG_NAV_POSLLH) : UBloxDescriptor('NAV_POSLLH',
                                                  '<IiiiiII', 
                                                  ['iTOW', 'Longitude', 'Latitude', 'height', 'hMSL', 'hAcc', 'vAcc']),
    (CLASS_NAV, MSG_NAV_VELNED) : UBloxDescriptor('NAV_VELNED',
                                                  '<IiiiIIiII', 
                                                  ['iTOW', 'velN', 'velE', 'velD', 'speed', 'gSpeed', 'heading', 
                                                   'sAcc', 'cAcc']),
    (CLASS_NAV, MSG_NAV_STATUS) : UBloxDescriptor('NAV_STATUS',
                                                  '<IBBBBII', 
                                                  ['iTOW', 'gpsFix', 'flags', 'fixStat', 'flags2', 'ttff', 'msss']),
    (CLASS_NAV, MSG_NAV_SOL)    : UBloxDescriptor('NAV_SOL',
                                                  '<IihBBiiiIiiiIHBBI',
                                                  ['iTOW', 'fTOW', 'week', 'gpsFix', 'flags', 'ecefX', 'ecefY', 'ecefZ',
                                                   'pAcc', 'ecefVX', 'ecefVY', 'ecefVZ', 'sAcc', 'pDOP', 'reserved1', 
                                                   'numSV', 'reserved2']),
    (CLASS_NAV, MSG_NAV_SVINFO)  : UBloxDescriptor('NAV_SVINFO',
                                                   '<IBBH',
                                                   ['iTOW', 'numCh', 'globalFlags', 'reserved2'],
                                                   'numCh',
                                                   '<BBBBBbhi',
                                                   ['chn', 'svid', 'flags', 'quality', 'cno', 'elev', 'azim', 'prRes']),
    (CLASS_NAV, MSG_NAV_SVINFO)  : UBloxDescriptor('RXM_SVSI',
                                                   '<IhBB',
                                                   ['iTOW', 'week', 'numVis', 'numSV'],
                                                   'numSV',
                                                   '<BBhbB',
                                                   ['svid', 'svFlag', 'azim', 'elev', 'age'])
                                                  
}

class UBloxMessage:
    def __init__(self):
        self.buf = ""

    def __str__(self):
        if not self.valid():
            return 'UBloxMessage(INVALID)'
        (msg_class, msg_id) = (self.msg_class(), self.msg_id())
        if (msg_class, msg_id) in msg_types:
                return msg_types[(msg_class, msg_id)].format(self)
        return 'UBloxMessage(%u, %u, %u)' % (msg_class, msg_id, self.msg_length())

    def msg_class(self):
        return ord(self.buf[2])

    def msg_id(self):
        return ord(self.buf[3])

    def msg_length(self):
        (payload_length,) = struct.unpack('<H', self.buf[4:6])
        return payload_length

    def valid_so_far(self):
        if len(self.buf) > 0 and ord(self.buf[0]) != PREAMBLE1:
            return False
        if len(self.buf) > 1 and ord(self.buf[1]) != PREAMBLE2:
            print("bad pre2")
            return False
        if self.needed_bytes() == 0 and not self.valid():
            print("bad len")
            return False
        return True

    def add(self, bytes):
        self.buf += bytes
        if not self.valid_so_far():
            self.buf = ""

    def checksum(self, data=None):
        if data is None:
            data = self.buf[2:-2]
        cs = 0
        ck_a = 0
        ck_b = 0
        for i in data:
            ck_a = (ck_a + ord(i)) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return (ck_a, ck_b)

    def valid_checksum(self):
        (ck_a, ck_b) = self.checksum()
        d = self.buf[2:-2]
        (ck_a2, ck_b2) = struct.unpack('<BB', self.buf[-2:])
        #print(len(self.buf), ck_a, ck_a2, ck_b, ck_b2)
        return ck_a == ck_a2 and ck_b == ck_b2

    def needed_bytes(self):
        '''return number of bytes still needed'''
        if len(self.buf) < 6:
            return 8 - len(self.buf)
        return self.msg_length() + 8 - len(self.buf)

    def valid(self):
        return len(self.buf) >= 8 and self.valid_checksum()

class UBlox:
    def __init__(self, port, baudrate=38400):
        self.serial_device = port
        self.baudrate = baudrate
        if os.path.isfile(self.serial_device):
            self.read_only = True
            self.dev = open(self.serial_device)
        else:
            self.dev = serial.Serial(self.serial_device, baudrate=self.baudrate,
                                     dsrdtr=False, rtscts=False, xonxoff=False)
            self.read_only = False
        self.logfile = None
        self.log = None

    def set_logfile(self, logfile, append=False):
        if self.log is not None:
            self.log.close()
            self.log = None
        self.logfile = logfile
        if self.logfile is not None:
            if append:
                mode = 'a'
            else:
                mode = 'w'
            self.log = open(self.logfile, mode=mode)

    def set_binary(self):
        if not self.read_only:
            self.dev.write("$PUBX,41,1,0003,0001,38400,0*26\n")

    def receive_message(self):
        msg = UBloxMessage()
        while True:
            b = self.dev.read(1)
            if not b:
                return None
            msg.add(b)
            if self.log is not None:
                self.log.write(b)
            if msg.valid():
                #msg.parse()
                return msg

    def send_message(self, msg_class, msg_id, payload):
        msg = UBloxMessage()
        msg.buf = struct.pack('<BBBBH', 0xb5, 0x62, msg_class, msg_id, len(payload))
        msg.buf += payload
        (ck_a, ck_b) = msg.checksum(msg.buf[2:])
        msg.buf += struct.pack('<BB', ck_a, ck_b)
        if not msg.valid():
            print("invalid send")
        if not self.read_only:
            self.dev.write(msg.buf)

    def configure_solution_rate(self, rate_ms=200, nav_rate=1, timeref=0):
        payload = struct.pack('<HHH', rate_ms, nav_rate, timeref)
        self.send_message(CLASS_CFG, MSG_CFG_RATE, payload)

    def configure_message_rate(self, msg_class, msg_id, rate):
        payload = struct.pack('<BBB', msg_class, msg_id, rate)
        self.send_message(CLASS_CFG, MSG_CFG_SET_RATE, payload)

    def configure_port(self, port=1, inMask=3, outMask=3):
        payload = struct.pack('BBHIIHHHH', 3, 0, 0, 0, 0, inMask, outMask, 0, 0)
        self.send_message(CLASS_CFG, MSG_CFG_PRT, payload)

    def configure_poll_port(self):
        self.send_message(CLASS_CFG, MSG_CFG_PRT, '')

    def configure_poll_usb(self):
        self.send_message(CLASS_CFG, MSG_CFG_USB, '')
                              
