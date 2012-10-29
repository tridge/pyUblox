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
CLASS_INF = 0x04
CLASS_ACK = 0x05
CLASS_CFG = 0x06
CLASS_MON = 0x0A
CLASS_AID = 0x0B
CLASS_TIM = 0x0D
CLASS_ESF = 0x10

# ACK messages
MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01

# NAV messages
MSG_NAV_POSECEF   = 0x1
MSG_NAV_POSLLH    = 0x2
MSG_NAV_STATUS    = 0x3
MSG_NAV_SOL       = 0x6
MSG_NAV_VELNED    = 0x12
MSG_NAV_VELECEF   = 0x11
MSG_NAV_TIMEGPS   = 0x20
MSG_NAV_TIMEUTC   = 0x21
MSG_NAV_CLOCK     = 0x22
MSG_NAV_SVINFO    = 0x30
MSG_NAV_AOPSTATUS = 0x60
MSG_NAV_DGPS      = 0x31
MSG_NAV_DOP       = 0x04
MSG_NAV_EKFSTATUS = 0x40
MSG_NAV_SBAS      = 0x32
MSG_NAV_SOL       = 0x06

# RXM messages
MSG_RXM_RAW    = 0x10
MSG_RXM_SFRB   = 0x11
MSG_RXM_SVSI   = 0x20
MSG_RXM_EPH    = 0x31
MSG_RXM_ALM    = 0x30
MSG_RXM_PMREQ  = 0x41

# AID messages
MSG_AID_ALM    = 0x30
MSG_AID_EPH    = 0x31
MSG_AID_ALPSRV = 0x32
MSG_AID_AOP    = 0x33
MSG_AID_DATA   = 0x10
MSG_AID_ALP    = 0x50
MSG_AID_DATA   = 0x10
MSG_AID_HUI    = 0x02
MSG_AID_INI    = 0x01
MSG_AID_REQ    = 0x00

# CFG messages
MSG_CFG_PRT = 0x00
MSG_CFG_ANT = 0x13
MSG_CFG_DAT = 0x06
MSG_CFG_EKF = 0x12
MSG_CFG_ESFGWT = 0x29
MSG_CFG_CFG = 0x09
MSG_CFG_USB = 0x1b
MSG_CFG_RATE = 0x08
MSG_CFG_SET_RATE = 0x01
MSG_CFG_NAV5 = 0x24
MSG_CFG_FXN = 0x0E
MSG_CFG_INF = 0x02
MSG_CFG_ITFM = 0x39
MSG_CFG_MSG = 0x01
MSG_CFG_NAVX5 = 0x23
MSG_CFG_NMEA = 0x17
MSG_CFG_NVS = 0x22
MSG_CFG_PM2 = 0x3B
MSG_CFG_PM = 0x32
MSG_CFG_RINV = 0x34
MSG_CFG_RST = 0x04
MSG_CFG_RXM = 0x11
MSG_CFG_SBAS = 0x16
MSG_CFG_TMODE2 = 0x3D
MSG_CFG_TMODE = 0x1D
MSG_CFG_TPS = 0x31
MSG_CFG_TP = 0x07

# ESF messages
MSG_ESF_MEAS   = 0x02
MSG_ESF_STATUS = 0x10

# INF messages
MSG_INF_DEBUG  = 0x04
MSG_INF_ERROR  = 0x00
MSG_INF_NOTICE = 0x02
MSG_INF_TEST   = 0x03
MSG_INF_WARNING= 0x01

# MON messages
MSG_MON_SCHD  = 0x01
MSG_MON_HW    = 0x09
MSG_MON_HW2   = 0x0B
MSG_MON_IO    = 0x02
MSG_MON_MSGPP = 0x06
MSG_MON_RXBUF = 0x07
MSG_MON_RXR   = 0x21
MSG_MON_TXBUF = 0x08
MSG_MON_VER   = 0x04

# TIM messages
MSG_TIM_TP   = 0x01
MSG_TIM_SVIN = 0x04
MSG_TIM_VRFY = 0x06

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

class UBloxAttrDict(dict):
    '''allow dictionary members as attributes'''
    def __init__(self):
        dict.__init__(self)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if self.__dict__.has_key(name):
            # allow set on normal attributes
            dict.__setattr__(self, name, value)
        else:
            self.__setitem__(name, value)

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
	'''unpack a UBloxMessage, creating the .fields and ._recs attributes in msg'''
	size1 = struct.calcsize(self.msg_format)
        buf = msg._buf[6:-2]
        if size1 > len(buf):
            raise UBloxError("%s INVALID_SIZE1=%u" % (self.name, len(buf)))
        count = 0
        f1 = list(struct.unpack(self.msg_format, buf[:size1]))
        msg._fields = {}
        for i in range(len(self.fields)):
            msg._fields[self.fields[i]] = f1[i]
            if self.count_field == self.fields[i]:
                count = int(f1[i])
        if count == 0:
            msg._recs = []
            msg._unpacked = True
            return
        buf = buf[size1:]
        size2 = struct.calcsize(self.format2)
        msg._recs = []
        for c in range(count):
            r = UBloxAttrDict()
            if size2 > len(buf):
                raise UBloxError("INVALID_SIZE=%u, " % len(buf))
            f2 = list(struct.unpack(self.format2, buf[:size2]))
            for i in range(len(self.fields2)):
                r[self.fields2[i]] = f2[i]
            buf = buf[size2:]
            msg._recs.append(r)
        if len(buf) != 0:
            raise UBloxError("EXTRA_BYTES=%u" % len(buf))
        msg._unpacked = True

    def pack(self, msg, msg_class=None, msg_id=None):
	'''pack a UBloxMessage from the .fields and ._recs attributes in msg'''
        f1 = []
        for f in self.fields:
            f1.append(msg._fields[f])
        length = struct.calcsize(self.msg_format)
        if msg._recs:
            length += len(msg._recs) * struct.calcsize(self.format2)
        if msg_class is None:
            msg_class = msg.msg_class()
        if msg_id is None:
            msg_id = msg.msg_id()
        msg._buf = struct.pack('<BBBBH', PREAMBLE1, PREAMBLE2, msg_class, msg_id, length)
        msg._buf += struct.pack(self.msg_format, *tuple(f1))
        for r in msg._recs:
            f2 = []
            for f in self.fields2:
                f2.append(r[f])
            msg._buf += struct.pack(self.format2, *tuple(f2))            
        msg._buf += struct.pack('<BB', *msg.checksum(data=msg._buf[2:]))

    def format(self, msg):
	'''return a formatted string for a message'''
        if not msg._unpacked:
            self.unpack(msg)
        ret = self.name + ': '
        for f in self.fields:
            v = msg._fields[f]
            if isinstance(v, str):
                ret += '%s="%s", ' % (f, v.rstrip(' \0'))
            else:
                ret += '%s=%s, ' % (f, v)
        for r in msg._recs:
            ret += '[ '
            for f in self.fields2:
                v = r[f]
                ret += '%s=%s, ' % (f, v)
            ret = ret[:-2] + ' ], '
        return ret[:-2]
        

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
    (CLASS_NAV, MSG_NAV_POSECEF): UBloxDescriptor('NAV_POSECEF',
                                                  '<IiiiI',
                                                  ['iTOW', 'ecefX', 'ecefY', 'ecefZ', 'pAcc']),
    (CLASS_NAV, MSG_NAV_TIMEGPS): UBloxDescriptor('NAV_TIMEGPS',
                                                  '<IihbBI',
                                                  ['iTOW', 'fTOW', 'week', 'leapS', 'valid', 'tAcc']),
    (CLASS_NAV, MSG_NAV_CLOCK)  : UBloxDescriptor('NAV_CLOCK',
                                                  '<IiiII',
                                                  ['iTOW', 'clkB', 'clkD', 'tAcc', 'fAcc']),
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
    (CLASS_RXM, MSG_RXM_EPH)    : UBloxDescriptor('RXM_EPH',
                                                  '<II IIIIIIII IIIIIIII IIIIIIII',
                                                  ['svid', 'how',
                                                   'sf1d1', 'sf1d2', 'sf1d3', 'sf1d4', 'sf1d5', 'sf1d6', 'sf1d7', 'sf1d8',
                                                   'sf2d1', 'sf2d2', 'sf2d3', 'sf2d4', 'sf2d5', 'sf2d6', 'sf2d7', 'sf2d8',
                                                   'sf3d1', 'sf3d2', 'sf3d3', 'sf3d4', 'sf3d5', 'sf3d6', 'sf3d7', 'sf3d8']),
    (CLASS_AID, MSG_AID_EPH)    : UBloxDescriptor('AID_EPH',
                                                  '<II IIIIIIII IIIIIIII IIIIIIII',
                                                  ['svid', 'how',
                                                   'sf1d1', 'sf1d2', 'sf1d3', 'sf1d4', 'sf1d5', 'sf1d6', 'sf1d7', 'sf1d8',
                                                   'sf2d1', 'sf2d2', 'sf2d3', 'sf2d4', 'sf2d5', 'sf2d6', 'sf2d7', 'sf2d8',
                                                   'sf3d1', 'sf3d2', 'sf3d3', 'sf3d4', 'sf3d5', 'sf3d6', 'sf3d7', 'sf3d8']),
    (CLASS_RXM, MSG_RXM_RAW)   : UBloxDescriptor('RXM_RAW',
                                                  '<ihBB',
                                                  ['iTOW', 'week', 'numSV', 'reserved1'],
                                                  'numSV',
                                                  '<ddfBbbB',
                                                  ['cpMes', 'prMes', 'doMes', 'sv', 'mesQI', 'cno', 'lli']),
    (CLASS_RXM, MSG_RXM_SFRB)  : UBloxDescriptor('RXM_SFRB',
                                                  '<BBIIIIIIIIII',
                                                  ['chn', 'svid',
                                                   'dwrd1', 'dwrd2', 'dwrd3', 'dwrd4', 'dwrd5',
                                                   'dwrd6', 'dwrd7', 'dwrd8', 'dwrd9', 'dwrd10']),
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
						   'pullH', 'pullL']),
    (CLASS_MON, MSG_MON_SCHD)   : UBloxDescriptor('MON_SCHD',
                                                  '<IIIIHHHBB',
                                                  ['tskRun', 'tskSchd', 'tskOvrr', 'tskReg', 'stack',
                                                   'stackSize', 'CPUIdle', 'flySly', 'ptlSly']),
    (CLASS_TIM, MSG_TIM_TP)     : UBloxDescriptor('TIM_TP',
                                                  '<IIiHBB',
                                                  ['towMS', 'towSubMS', 'qErr', 'week', 'flags', 'reserved1']),
    (CLASS_TIM, MSG_TIM_SVIN)   : UBloxDescriptor('TIM_SVIN',
                                                  '<IiiiIIBBH',
                                                  ['dur', 'meanX', 'meanY', 'meanZ', 'meanV',
                                                   'obs', 'valid', 'active', 'reserved1'])
}


class UBloxMessage:
    '''UBlox message class - holds a UBX binary message'''
    def __init__(self):
        self._buf = ""
        self._fields = {}
        self._recs = []
        self._unpacked = False

    def __str__(self):
	'''format a message as a string'''
        if not self.valid():
            return 'UBloxMessage(INVALID)'
        type = self.msg_type()
        if type in msg_types:
            return msg_types[type].format(self)
        return 'UBloxMessage(UNKNOWN %s, %u)' % (str(type), self.msg_length())

    def __getattr__(self, name):
        '''allow access to message fields'''
        try:
            return self._fields[name]
        except KeyError:
            if name == 'recs':
                return self._recs
            raise AttributeError(name)

    def __setattr__(self, name, value):
        '''allow access to message fields'''
        if name.startswith('_'):
            self.__dict__[name] = value
        else:
            self._fields[name] = value

    def unpack(self):
	'''unpack a message'''
        if not self.valid():
            raise UBloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s length=%u' % (str(type), len(self._buf)))
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
            raise UBloxError('Unknown message %s length=%u' % (str(type), len(self._buf)))
        return msg_types[type].name

    def msg_class(self):
	'''return the message class'''
        return ord(self._buf[2])

    def msg_id(self):
	'''return the message id within the class'''
        return ord(self._buf[3])

    def msg_type(self):
	'''return the message type tuple (class, id)'''
        return (self.msg_class(), self.msg_id())

    def msg_length(self):
	'''return the payload length'''
        (payload_length,) = struct.unpack('<H', self._buf[4:6])
        return payload_length

    def valid_so_far(self):
	'''check if the message is valid so far'''
        if len(self._buf) > 0 and ord(self._buf[0]) != PREAMBLE1:
            return False
        if len(self._buf) > 1 and ord(self._buf[1]) != PREAMBLE2:
            print("bad pre2")
            return False
        if self.needed_bytes() == 0 and not self.valid():
            print("bad len")
            return False
        return True

    def add(self, bytes):
	'''add some bytes to a message'''
        self._buf += bytes
        while not self.valid_so_far() and len(self._buf) > 0:
	    '''handle corrupted streams'''
            self._buf = self._buf[1:]
        if self.needed_bytes() < 0:
            self._buf = ""

    def checksum(self, data=None):
	'''return a checksum tuple for a message'''
        if data is None:
            data = self._buf[2:-2]
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
        d = self._buf[2:-2]
        (ck_a2, ck_b2) = struct.unpack('<BB', self._buf[-2:])
        return ck_a == ck_a2 and ck_b == ck_b2

    def needed_bytes(self):
        '''return number of bytes still needed'''
        if len(self._buf) < 6:
            return 8 - len(self._buf)
        return self.msg_length() + 8 - len(self._buf)

    def valid(self):
	'''check if a message is valid'''
        return len(self._buf) >= 8 and self.needed_bytes() == 0 and self.valid_checksum()


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
            #print n, len(msg._buf)
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
            self.dev.write(msg._buf)        

    def send_message(self, msg_class, msg_id, payload):
	'''send a ublox message with class, id and payload'''
        msg = UBloxMessage()
        msg._buf = struct.pack('<BBBBH', 0xb5, 0x62, msg_class, msg_id, len(payload))
        msg._buf += payload
        (ck_a, ck_b) = msg.checksum(msg._buf[2:])
        msg._buf += struct.pack('<BB', ck_a, ck_b)
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
