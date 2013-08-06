#! /usr/bin/env python

from bitstring import BitArray
from collections import deque

import sys

class RTCMParityError(Exception):
    pass

class RTCMBitError(Exception):
    pass

class RTCMv2_Decode:
    def __init__(self):
        self.buf = deque()
        self.p29 = 0
        self.p30 = 0

        self.callbacks = {}

    def xor_bits(self, word, bits):
        '''xor a set of bits from a word'''
        word = word.uint
        ret = 0
        for b in bits:
            ret ^= (word >> (29 - b)) & 1
        return ret

    def calculate_parity(self, word):
        '''calculate 6 parity bits for a word'''
        parity1 = self.p29
        parity2 = self.p30

        d = [0]*6
        d[0] = parity1 ^ self.xor_bits(word, [0, 1, 2, 4, 5,  9, 10, 11, 12, 13, 16, 17, 19, 22])
        d[1] = parity2 ^ self.xor_bits(word, [1, 2, 3, 5, 6, 10, 11, 12, 13, 14, 17, 18, 20, 23])
        d[2] = parity1 ^ self.xor_bits(word, [0, 2, 3, 4, 6,  7, 11, 12, 13, 14, 15, 18, 19, 21])
        d[3] = parity2 ^ self.xor_bits(word, [1, 3, 4, 5, 7,  8, 12, 13, 14, 15, 16, 19, 20, 22])
        d[4] = parity2 ^ self.xor_bits(word, [0, 2, 4, 5, 6,  8,  9, 13, 14, 15, 16, 17, 20, 21, 23])
        d[5] = parity1 ^ self.xor_bits(word, [2, 4, 5, 7, 8,  9, 10, 12, 14, 18, 21, 22, 23])
        ret = d[0]
        for i in range(1, 6):
            ret = (ret<<1) + d[i]

        print(hex(ret))

        return ret

    def get_word(self, allow_recalc=False):
        word = BitArray(0)
        for i in range(5):
            b = self.buf.popleft()

            if b >> 6 != 1:
                pass
                #print("6-of-8 decode wrong")
                #raise RTCMBitError()

            b = BitArray(uint=(b&0x3f), length=6)
            b.reverse()
            word.append(b)

        if self.p30:
            word ^= BitArray(uint=0x3fffffc0, length=30)

        print(hex(word.uint))

        if allow_recalc and self.calculate_parity(word) != word.uint & 0x3f:
            self.p29 = 1

        if self.calculate_parity(word) != word.uint & 0x3f:
            raise RTCMParityError()

        self.p30 = word.uint & 1
        self.p29 = (word.uint & 2) >> 1

        return word

    def decode(self):
        print("Decode")
        print([hex(a) for a in self.buf])
        #header 1
        # Note the BitArray slice semantics follow the Python semantics, not
        # the intuative bit numbering (i.e. 0 is left-most)
        w = self.get_word(True)

        h = w[0:8].uint
        rec = w[8:14].uint
        stat = w[14:24].uint

        #header 2
        w = self.get_word()
        zcount = w[0:13].uint * 0.6
        seq = w[13:16].uint
        wordcount = w[16:21].uint
        health = w[21:24].uint

        print("Header {} Record {} Station {} ZCount {} Seq {} WordCount {} Health {}".format(
                h, rec, stat, zcount, seq, wordcount, health))


    def add_byte(self, b):

        if b == 0x59:
            self.p30 = 1

        if b == 0x59 or b == 0x66:
            try:
                if len(self.buf) > 0:
                    self.decode()
            except IndexError:
                print("Bad RTCM record length")
            except RTCMParityError:
                print("Parity Error")
            except RTCMBitError:
                print("Bit Error")
            finally:
                self.buf = deque()

        self.buf.append(b)

if __name__ == '__main__':
    decoder = RTCMv2_Decode()

    while True:
        decoder.add_byte(ord(sys.stdin.read(1)))


