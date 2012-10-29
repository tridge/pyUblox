#!/usr/bin/env python
'''
UBlox binary protocol handling

Copyright Andrew Tridgell, October 2012
Released under GNU GPL version 3 or later
'''

import struct
import serial
from datetime import datetime
import time, os

# protocol constants
PREAMBLE1 = 0xb5
PREAMBLE2 = 0x62

# message classes
CLASS_NAV = 0x01
CLASS_RXM = 0x02
CLASS_ACK = 0x05
CLASS_CFG = 0x06
CLASS_MON = 0x0A

# ACK messages
MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01

# NAV messages
MSG_NAV_POSLLH = 0x2
MSG_NAV_STATUS = 0x3
MSG_NAV_SOL    = 0x6
MSG_NAV_VELNED = 0x12
MSG_NAV_SVINFO = 0x30

# RXM messages
MSG_RXM_RAW    = 0x10
MSG_RXM_SFRB   = 0x11
MSG_RXM_SVSI   = 0x20

# CFG messages
MSG_CFG_PRT = 0x00
MSG_CFG_CFG = 0x09
MSG_CFG_USB = 0x1b
MSG_CFG_RATE = 0x08
MSG_CFG_SET_RATE = 0x01
MSG_CFG_NAV5 = 0x24

# MON messages
MSG_MON_HW = 0x09

# port IDs
PORT_DDC    =0
PORT_SERIAL1=1
PORT_SERIAL2=2
PORT_USB    =3
PORT_SPI    =4

class UBloxError(Exception):
    '''Ublox error class'''
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.message = msg

class UBloxDescriptor:
    '''class used to describe the layout of a UBlox message'''
    def __init__(self, name, msg_format, fields=[], count_field=None, format2=None, fields2=None):
        self.name = name
        self.msg_format = msg_format
        self.fields = fields
        self.count_field = count_field
        self.format2 = format2
        self.fields2 = fields2
	
    def unpack(self, msg):
	'''unpack a UBloxMessage, creating the .fields and .recs attributes in msg'''
	size1 = struct.calcsize(self.msg_format)
        buf = msg.buf[6:-2]
        if size1 > len(buf):
            raise UBloxError("INVALID_SIZE=%u" % len(buf))
        count = 0
        f1 = list(struct.unpack(self.msg_format, buf[:size1]))
        msg.fields = {}
        for i in range(len(self.fields)):
            msg.fields[self.fields[i]] = f1[i]
            if self.count_field == self.fields[i]:
                count = int(f1[i])
        if count == 0:
            msg.recs = []
            return
        buf = buf[size1:]
        size2 = struct.calcsize(self.format2)
        msg.recs = []
        for c in range(count):
            r = {}
            if size2 > len(buf):
                raise UBloxError("INVALID_SIZE=%u, " % len(buf))
            f2 = list(struct.unpack(self.format2, buf[:size2]))
            for i in range(len(self.fields2)):
                r[self.fields2[i]] = f2[i]
            buf = buf[size2:]
            msg.recs.append(r)
        if len(buf) != 0:
            raise UBloxError("EXTRA_BYTES=%u" % len(buf))

    def pack(self, msg, msg_class=None, msg_id=None):
	'''pack a UBloxMessage from the .fields and .recs attributes in msg'''
        f1 = []
        for f in self.fields:
            f1.append(msg.fields[f])
        length = struct.calcsize(self.msg_format)
        if msg.recs:
            length += len(msg.recs) * struct.calcsize(self.format2)
        if msg_class is None:
            msg_class = msg.msg_class()
        if msg_id is None:
            msg_id = msg.msg_id()
        msg.buf = struct.pack('<BBBBH', PREAMBLE1, PREAMBLE2, msg_class, msg_id, length)
        msg.buf += struct.pack(self.msg_format, *tuple(f1))
        for r in msg.recs:
            f2 = []
            for f in self.fields2:
                f2.append(r[f])
            msg.buf += struct.pack(self.format2, *tuple(f2))            
        msg.buf += struct.pack('<BB', *msg.checksum(data=msg.buf[2:]))

    def format(self, msg):
	'''return a formatted string for a message'''
        self.unpack(msg)
        ret = 'UBloxMessage(%s, ' % self.name
        for f in self.fields:
            v = msg.fields[f]
            if isinstance(v, str):
                ret += '%s="%s", ' % (f, v.rstrip(' \0'))
            else:
                ret += '%s=%s, ' % (f, v)
        for r in msg.recs:
            ret += '[ '
            for f in self.fields2:
                v = r[f]
                ret += '%s=%s, ' % (f, v)
            ret = ret[:-2] + ' ], '
        return ret[:-2] + ')'
        

# list of supported message types.
msg_types = {
    (CLASS_ACK, MSG_ACK_ACK)    : UBloxDescriptor('ACK_ACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
    (CLASS_ACK, MSG_ACK_NACK)   : UBloxDescriptor('ACK_NACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
    (CLASS_CFG, MSG_CFG_USB)    : UBloxDescriptor('CFG_USB',
                                                  '<HHHHHH32s32s32s',
                                                  ['vendorID', 'productID', 'reserved1', 'reserved2', 'powerConsumption',
                                                   'flags', 'vendorString', 'productString', 'serialNumber']),
    (CLASS_CFG, MSG_CFG_PRT)    : UBloxDescriptor('CFG_PRT',
                                                  '<BBHIIHHHH',
                                                  ['portID', 'reserved0', 'txReady', 'mode', 'baudRate', 'inProtoMask', 
                                                   'outProtoMask', 'reserved4', 'reserved5']),
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
    (CLASS_NAV, MSG_NAV_SVINFO) : UBloxDescriptor('NAV_SVINFO',
                                                  '<IBBH',
                                                  ['iTOW', 'numCh', 'globalFlags', 'reserved2'],
                                                  'numCh',
                                                  '<BBBBBbhi',
                                                  ['chn', 'svid', 'flags', 'quality', 'cno', 'elev', 'azim', 'prRes']),
    (CLASS_RXM, MSG_RXM_SVSI)   : UBloxDescriptor('RXM_SVSI',
                                                  '<IhBB',
                                                  ['iTOW', 'week', 'numVis', 'numSV'],
                                                  'numSV',
                                                  '<BBhbB',
                                                  ['svid', 'svFlag', 'azim', 'elev', 'age']),
    (CLASS_CFG, MSG_CFG_NAV5)   : UBloxDescriptor('CFG_NAV5',
                                                  '<HBBiIbBHHHHBBIII',
                                                  ['mask', 'dynModel', 'fixMode', 'fixedAlt', 'fixedAltVar', 'minElev', 
                                                   'drLimit', 'pDop', 'tDop', 'pAcc', 'tAcc', 'staticHoldThresh', 
                                                   'dgpsTimeOut', 'reserved2', 'reserved3', 'reserved4']),
    (CLASS_MON, MSG_MON_HW)     : UBloxDescriptor('MON_HW',
                                                  '<IIIIHHBBBBIBBBBBBBBBBBBBBBBBBBBBBBBBBHIII',
                                                  ['pinSel', 'pinBank', 'pinDir', 'pinVal', 'noisePerMS', 'agcCnt', 'aStatus',
						   'aPower', 'flags', 'reserved1', 'usedMask', 
						   'VP1', 'VP2', 'VP3', 'VP4', 'VP5', 'VP6', 'VP7', 'VP8', 'VP9', 'VP10', 
						   'VP11', 'VP12', 'VP13', 'VP14', 'VP15', 'VP16', 'VP17', 'VP18', 'VP19', 
						   'VP20', 'VP21', 'VP22', 'VP23', 'VP24', 'VP25',
						   'jamInd', 'reserved3', 'pinInq',
						   'pullH', 'pullL'])
}


class UBloxMessage:
    '''UBlox message class - holds a UBX binary message'''
    def __init__(self):
        self.buf = ""
        self.fields = None
        self.recs = None

    def __str__(self):
	'''format a message as a string'''
        if not self.valid():
            return 'UBloxMessage(INVALID)'
        type = self.msg_type()
        if type in msg_types:
                return msg_types[type].format(self)
        return 'UBloxMessage(%s, %u)' % (str(type), self.msg_length())

    def unpack(self):
	'''unpack a message'''
        if not self.valid():
            raise UBloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s' % str(type))
        msg_types[type].unpack(self)

    def pack(self):
	'''pack a message'''
        if not self.valid():
            raise UbloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s' % str(type))
        msg_types[type].pack(self)

    def name(self):
	'''return the short string name for a message'''
        if not self.valid():
            raise UbloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s' % str(type))
        return msg_types[type].name

    def msg_class(self):
	'''return the message class'''
        return ord(self.buf[2])

    def msg_id(self):
	'''return the message id within the class'''
        return ord(self.buf[3])

    def msg_type(self):
	'''return the message type tuple (class, id)'''
        return (self.msg_class(), self.msg_id())

    def msg_length(self):
	'''return the payload length'''
        (payload_length,) = struct.unpack('<H', self.buf[4:6])
        return payload_length

    def valid_so_far(self):
	'''check if the message is valid so far'''
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
	'''add some bytes to a message'''
        self.buf += bytes
        while not self.valid_so_far() and len(self.buf) > 0:
	    '''handle corrupted streams'''
            self.buf = self.buf[1:]
        if self.needed_bytes() < 0:
            self.buf = ""

    def checksum(self, data=None):
	'''return a checksum tuple for a message'''
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
	'''check if the checksum is OK'''
        (ck_a, ck_b) = self.checksum()
        d = self.buf[2:-2]
        (ck_a2, ck_b2) = struct.unpack('<BB', self.buf[-2:])
        return ck_a == ck_a2 and ck_b == ck_b2

    def needed_bytes(self):
        '''return number of bytes still needed'''
        if len(self.buf) < 6:
            return 8 - len(self.buf)
        return self.msg_length() + 8 - len(self.buf)

    def valid(self):
	'''check if a message is valid'''
        return len(self.buf) >= 8 and self.valid_checksum()


class UBlox:
    '''main UBlox control class.

    port can be a file (for reading only) or a serial device
    '''
    def __init__(self, port, baudrate=38400, timeout=0):
        self.serial_device = port
        self.baudrate = baudrate
        if os.path.isfile(self.serial_device):
            self.read_only = True
            self.dev = open(self.serial_device)
        else:
            self.dev = serial.Serial(self.serial_device, baudrate=self.baudrate,
                                     dsrdtr=False, rtscts=False, xonxoff=False, timeout=timeout)
            self.read_only = False
        self.logfile = None
        self.log = None

    def close(self):
	'''close the device'''
        self.dev.close()
	self.dev = None

    def set_logfile(self, logfile, append=False):
	'''setup logging to a file'''
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
	'''put a UBlox into binary mode using a NMEA string'''
        if not self.read_only:
            self.dev.write("$PUBX,41,1,0001,0001,38400,0*24\n")

    def seek_percent(self, pct):
	'''seek to the given percentage of a file'''
	self.dev.seek(0, 2)
	filesize = self.dev.tell()
	self.dev.seek(pct*0.01*filesize)

    def receive_message(self):
	'''blocking receive of one ublox message'''
        msg = UBloxMessage()
        while True:
            n = msg.needed_bytes()
            #print n, len(msg.buf)
            b = self.dev.read(n)
            if not b:
                return None
            msg.add(b)
            if self.log is not None:
                self.log.write(b)
            if msg.valid():
                return msg

    def send(self, msg):
	'''send a preformatted ublox message'''
        if not msg.valid():
            print("invalid send")
            return
        if not self.read_only:
            self.dev.write(msg.buf)        

    def send_message(self, msg_class, msg_id, payload):
	'''send a ublox message with class, id and payload'''
        msg = UBloxMessage()
        msg.buf = struct.pack('<BBBBH', 0xb5, 0x62, msg_class, msg_id, len(payload))
        msg.buf += payload
        (ck_a, ck_b) = msg.checksum(msg.buf[2:])
        msg.buf += struct.pack('<BB', ck_a, ck_b)
        self.send(msg)

    def configure_solution_rate(self, rate_ms=200, nav_rate=1, timeref=0):
	'''configure the solution rate in milliseconds'''
        payload = struct.pack('<HHH', rate_ms, nav_rate, timeref)
        self.send_message(CLASS_CFG, MSG_CFG_RATE, payload)

    def configure_message_rate(self, msg_class, msg_id, rate):
	'''configure the message rate for a given message'''
        payload = struct.pack('<BBB', msg_class, msg_id, rate)
        self.send_message(CLASS_CFG, MSG_CFG_SET_RATE, payload)

    def configure_port(self, port=1, inMask=3, outMask=3, mode=2240, baudrate=9600):
	'''configure a IO port'''
        payload = struct.pack('<BBHIIHHHH', port, 0, 0, mode, baudrate, inMask, outMask, 0, 0)
        self.send_message(CLASS_CFG, MSG_CFG_PRT, payload)

    def configure_loadsave(self, clearMask=0, saveMask=0, loadMask=0, deviceMask=0):
	'''configure configuration load/save'''
        payload = struct.pack('<IIIB', clearMask, saveMask, loadMask, deviceMask)
        self.send_message(CLASS_CFG, MSG_CFG_CFG, payload)

    def configure_poll(self, msg_class, msg_id, payload=''):
	'''poll a configuration message'''
        self.send_message(msg_class, msg_id, payload)

    def configure_poll_port(self, portID=None):
	'''poll a port configuration'''
        if portID is None:
            self.configure_poll(CLASS_CFG, MSG_CFG_PRT)
        else:
            self.configure_poll(CLASS_CFG, MSG_CFG_PRT, struct.pack('<B', portID))

    def configure_poll_usb(self):
	'''poll USB configuration'''
        self.configure_poll(CLASS_CFG, MSG_CFG_USB)

    def configure_poll_nav_settings(self):
	'''poll nav settings'''
        self.configure_poll(CLASS_CFG, MSG_CFG_NAV5)
