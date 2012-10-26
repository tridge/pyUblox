#!/usr/bin/env python

import struct
import serial
from datetime import datetime
import time

PREAMBLE1 = 0xb5
PREAMBLE2 = 0x62
CLASS_NAV = 0x01
CLASS_ACK = 0x05
CLASS_CFG = 0x06
MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01
MSG_POSLLH = 0x2
MSG_STATUS = 0x3
MSG_SOL = 0x6
MSG_VELNED = 0x12
MSG_CFG_PRT = 0x00
MSG_CFG_RATE = 0x08
MSG_CFG_SET_RATE = 0x01
MSG_CFG_NAV_SETTINGS = 0x24

PORT_SERIAL1=1
PORT_SERIAL2=2
PORT_USB    =3

class UBloxMessage:
    def __init__(self):
        self.buf = ""

    def __str__(self):
        if not self.valid():
            return 'UBloxMessage(INVALID)'
        return 'UBloxMessage(%u, %u, %u)' % (self.msg_class(), self.msg_id(), self.msg_length())

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
        self.dev = serial.Serial(self.serial_device, baudrate=self.baudrate,
                                 dsrdtr=False, rtscts=False, xonxoff=False)

    def set_binary(self):
	self.dev.write("$PUBX,41,1,0003,0001,38400,0*26\n")

    def receive_message(self):
        msg = UBloxMessage()
        while True:
            b = self.dev.read(1)
            msg.add(b)
            if msg.valid():
                return msg

    def send_message(self, msg_class, msg_id, payload):
        msg = UBloxMessage()
        msg.buf = struct.pack('<BBBBH', 0xb5, 0x62, msg_class, msg_id, len(payload))
        msg.buf += payload
        (ck_a, ck_b) = msg.checksum(msg.buf[2:])
        msg.buf += struct.pack('<BB', ck_a, ck_b)
        if not msg.valid():
            print("invalid send")
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
                              
