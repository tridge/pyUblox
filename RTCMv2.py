import struct, util

class RTCMBits:
    '''RTCMv2 bit packer. Thanks to Michael Oborne for the C# code this was based on

    ftp://ftp.tapr.org/gps/DGPS/N8PXW/
'''
    def __init__(self):
        self.rtcmseq = 0
        self.flip = [0,32,16,48,8,40,24,56,4,36,20,52,12,44,28,60,
                     2,34,18,50,10,42,26,58,6,38,22,54,14,46,30,62,
                     1,33,17,49,9,41,25,57,5,37,21,53,13,45,29,61,
                     3,35,19,51,11,43,27,59,7,39,23,55,15,47,31,63]
        self.parity29 = 0
        self.parity30 = 0
        self.reset()
        self.error_history = {}
        self.history_length = 10
        self.last_time_of_week = 0

    def reset(self):
        '''reset at the end of a message'''
        self.buf = ""
        self.rtcbits = 0
        self.rtcword = 0

    def addbits(self, nbits, value):
        '''add nbits bits of value to the buffer'''
        # put bits at high end of word
        value &= (1<<nbits)-1
        value <<= 32 - nbits
        for k in range(nbits):
            self.rtcword <<= 1
            if value & 0x80000000 != 0:
                self.rtcword |= 1
            value <<= 1
            # bump the output word bit count
            self.rtcbits += 1

        if self.rtcbits < 24:
            # we only encode output once we have 24 bits
            return

        # move data into lower 30 bits of 32 bit word
        self.rtcword <<= 6

        i = self.doparity(self.rtcword)
        # put parity into lower 6 bits of 32 bit word
        self.rtcword |= i
        # invert bits, if needed 
        if self.parity30 != 0:
            self.rtcword ^= 0x3fffffc0
        # copy parity bits  */
        self.parity30 = self.rtcword & 1
        self.parity29 = 0
        if (self.rtcword & 2) != 0:
            self.parity29 = 1

        rtcbufr = [0]*5

        for i in range(4,-1,-1):
            #* extract bottom 6 bits
            rtcbufr[i] = self.rtcword & 0x3f
            self.rtcword >>= 6
            # flip the bit order
            rtcbufr[i] = self.flip[rtcbufr[i]]
            # or in "01" into the upper bits
            rtcbufr[i] |= 0x40

        # we now the rtcm data complete in rtcbufr 0-4, send it
        self.buf += struct.pack('BBBBB', rtcbufr[0], rtcbufr[1], rtcbufr[2], rtcbufr[3], rtcbufr[4])
        self.rtcword = 0
        self.rtcbits = 0

    def getbit(self, word, bit):
        return (word >> (29 - bit)) & 1

    def doparity(self, word):
        d25 = d26 = d27 = d28 = d29 = d30 = 0
        parity29 = self.parity29
        parity30 = self.parity30

        d25 = parity29 ^ self.getbit(word, 0) ^ self.getbit(word, 1) ^ self.getbit(word, 2) ^ \
            self.getbit(word, 4) ^ self.getbit(word, 5) ^ self.getbit(word, 9) ^ self.getbit(word, 10) ^ \
            self.getbit(word, 11) ^ self.getbit(word, 12) ^ self.getbit(word, 13) ^ self.getbit(word, 16) ^ \
            self.getbit(word, 17) ^ self.getbit(word, 19) ^ self.getbit(word, 22)
        d26 = parity30 ^ self.getbit(word, 1) ^ self.getbit(word, 2) ^ self.getbit(word, 3) ^ \
            self.getbit(word, 5) ^ self.getbit(word, 6) ^ self.getbit(word, 10) ^ self.getbit(word, 11) ^ \
            self.getbit(word, 12) ^ self.getbit(word, 13) ^ self.getbit(word, 14) ^ self.getbit(word, 17) ^ \
            self.getbit(word, 18) ^ self.getbit(word, 20) ^ self.getbit(word, 23)
        d27 = parity29 ^ self.getbit(word, 0) ^ self.getbit(word, 2) ^ self.getbit(word, 3) ^ \
            self.getbit(word, 4) ^ self.getbit(word, 6) ^ self.getbit(word, 7) ^ self.getbit(word, 11) ^ \
            self.getbit(word, 12) ^ self.getbit(word, 13) ^ self.getbit(word, 14) ^ self.getbit(word, 15) ^ \
            self.getbit(word, 18) ^ self.getbit(word, 19) ^ self.getbit(word, 21)
        d28 = parity30 ^ self.getbit(word, 1) ^ self.getbit(word, 3) ^ self.getbit(word, 4) ^ \
            self.getbit(word, 5) ^ self.getbit(word, 7) ^ self.getbit(word, 8) ^ self.getbit(word, 12) ^ \
            self.getbit(word, 13) ^ self.getbit(word, 14) ^ self.getbit(word, 15) ^ self.getbit(word, 16) ^ \
            self.getbit(word, 19) ^ self.getbit(word, 20) ^ self.getbit(word, 22)
        d29 = parity30 ^ self.getbit(word, 0) ^ self.getbit(word, 2) ^ self.getbit(word, 4) ^ \
            self.getbit(word, 5) ^ self.getbit(word, 6) ^ self.getbit(word, 8) ^ self.getbit(word, 9) ^ \
            self.getbit(word, 13) ^ self.getbit(word, 14) ^ self.getbit(word, 15) ^ self.getbit(word, 16) ^ \
            self.getbit(word, 17) ^ self.getbit(word, 20) ^ self.getbit(word, 21) ^ self.getbit(word, 23)
        d30 = parity29 ^ self.getbit(word, 2) ^ self.getbit(word, 4) ^ self.getbit(word, 5) ^ \
            self.getbit(word, 7) ^ self.getbit(word, 8) ^ self.getbit(word, 9) ^ self.getbit(word, 10) ^ \
            self.getbit(word, 12) ^ self.getbit(word, 14) ^ self.getbit(word, 18) ^ self.getbit(word, 21) ^ \
            self.getbit(word, 22) ^ self.getbit(word, 23)
        parity = (((((((((d25 << 1) + d26) << 1) + d27) << 1) + d28) << 1) + d29) << 1) + d30
        return parity
        

    def RTCMType1(self, satinfo):
        '''create a RTCM type 1 message'''

        self.reset()

        tow = satinfo.raw.time_of_week
        deltat = tow - self.last_time_of_week
        self.last_time_of_week = tow
        msgsatcnt = len(satinfo.prCorrected)

        for svid in satinfo.prCorrected:
            err = satinfo.geometricRange[svid] - \
                (satinfo.prMeasured[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight + satinfo.receiver_clock_error*util.speedOfLight)
            if not svid in self.error_history:
                self.error_history[svid] = []
            self.error_history[svid].append(err)
            if len(self.error_history[svid]) > self.history_length:
                self.error_history[svid].pop(0)

        msgsatid = []
        msgprc   = []
        msgprrc  = []
        msgiode  = []
        for svid in satinfo.prCorrected:
            msgsatid.append(svid)
            err = sum(self.error_history[svid])/float(len(self.error_history[svid]))
            err = int(err / 0.02)
            msgprc.append(err)
            msgprrc.append(0)
            msgiode.append(satinfo.ephemeris[svid].iode)


#        print("msgsatid:", msgsatid)
#        print("msgprc:", msgprc)
#        print("msgiode:", msgiode)
            
        rtcmzcount = int((int(tow) % 3600) / 0.6)

        self.addbits(8, 0x66)  # header id
        self.addbits(6, 1)     # msg type 1
        self.addbits(10, 2)    # station id

        #  1st word should be sent here
        self.addbits(13, rtcmzcount) # z-count
        self.addbits(3, self.rtcmseq) # seq no.
        self.rtcmseq = (self.rtcmseq + 1) % 8

        # now compute the word count
        i = msgsatcnt * 40 #  no of bits to send
        j = i // 24  # no of RTCM words to send
        if (i % 24) != 0:
            j += 1  # bump, if not a full word
        bitlength = i
        wordlength = j

        self.addbits(5, wordlength) # word length
        self.addbits(3, 0) # health bits

        for i in range(msgsatcnt):
            '''      
            We have to calculate the scale factor, first.
            Mot PRC is 24 bits, scaled by 0.01 .
            RTCM PRC is 16 bits, scaled by 0.02, or 0.32 if sf==1 .
            Mot PRRC is 16 bits, scaled by 0.001 .
            RTCM PRRC is 8 bits, scaled by 0.002, or 0.032 if sf==1 .
            '''
            # 1. divide PRC and PRRC by 2 to get base corrections 
            # msgprc[i] /= 2
            # msgprrc[i] /= 2
            sf = 0
            # 2. see if PRC > 16 bits, or PRRC > 8 bits, if so sf=1.
            if msgprc[i] > 32767 or msgprc[i] < -32768:
                sf = 1
            if msgprrc[i] > 127 or msgprrc[i] < -128:
                sf = 1
            # 3a. if sf==1, add 8 to both PRC and PRRC to round up
            # 3b. if sf==1, then divide both PRC and PRRC by 16.
            if sf != 0:
                msgprc[i] += 8
                msgprrc[i] += 8
                msgprc[i] /= 16
                msgprrc[i] /= 16
            self.addbits(1, sf) # scale factor
            self.addbits(2, 0)  # UDRE
            self.addbits(5, msgsatid[i]) # sat id no
            # we split the prc into two 8-bit bytes, because an RTCM word
            # boundary can occur here
            self.addbits(8, msgprc[i] >> 8) # prc hob
            self.addbits(8, msgprc[i] & 0xff) # prc lob
            self.addbits(8, msgprrc[i]) # prcc
            self.addbits(8, msgiode[i]) # IODE

        while self.rtcbits != 0:
            self.addbits(8, 0xAA) # pad unused bits with 0xAA
        #print("MSG: bitlength=%u wordlength=%u len=%u" % (bitlength, wordlength, len(self.buf)))
        return self.buf


    def RTCMType3(self, satinfo):
        '''create a RTCM type 3 message'''

        self.reset()

        tow = satinfo.raw.time_of_week
        rtcmzcount = int((int(tow) % 3600) / 0.6)

        self.addbits(8, 0x66)  # header id
        self.addbits(6, 3)     # msg type 1
        self.addbits(10, 2)    # station id

        #  1st word should be sent here
        self.addbits(13, rtcmzcount) # z-count
        self.addbits(3, self.rtcmseq) # seq no.
        self.rtcmseq = (self.rtcmseq + 1) % 8

        self.addbits(5, 4) # word length
        self.addbits(3, 0) # health bits

        if satinfo.reference_position is not None:
            pos = satinfo.reference_position
        else:
            pos = satinfo.average_position

        X = int(pos.X * 100.0)
        Y = int(pos.Y * 100.0)
        Z = int(pos.Z * 100.0)

        self.addbits(8, (X>>24)&0xFF)
        self.addbits(8, (X>>16)&0xFF)
        self.addbits(8, (X>> 8)&0xFF)
        self.addbits(8, (X>> 0)&0xFF)

        self.addbits(8, (Y>>24)&0xFF)
        self.addbits(8, (Y>>16)&0xFF)
        self.addbits(8, (Y>> 8)&0xFF)
        self.addbits(8, (Y>> 0)&0xFF)

        self.addbits(8, (Z>>24)&0xFF)
        self.addbits(8, (Z>>16)&0xFF)
        self.addbits(8, (Z>> 8)&0xFF)
        self.addbits(8, (Z>> 0)&0xFF)

        while self.rtcbits != 0:
            self.addbits(8, 0xAA) # pad unused bits with 0xAA
        return self.buf


def generateRTCM2_Message1(satinfo):
    '''generate RTCMv2 corrections from satinfo'''
    bits = satinfo.rtcm_bits
    if bits is None:
        bits = RTCMBits()
        satinfo.rtcm_bits = bits
    msg = bits.RTCMType1(satinfo)
    return msg

def generateRTCM2_Message3(satinfo):
    '''generate RTCMv2 reference position from satinfo'''
    bits = satinfo.rtcm_bits
    if bits is None:
        bits = RTCMBits()
        satinfo.rtcm_bits = bits
    msg = bits.RTCMType3(satinfo)
    return msg
