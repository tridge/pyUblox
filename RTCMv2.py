import struct, util

class RTCMBits:
    '''RTCMv2 bit packer. Thanks to Michael Oborne for the C# code this was based on

    Also thanks to this site for a great RTCMv2 parser to test the generated output
    ftp://ftp.tapr.org/gps/DGPS/N8PXW/
    '''
    def __init__(self):
        self.rtcmseq = 0
        self.bitreverse = self.bitreverse_array()
        self.parity1 = 0
        self.parity2 = 0
        self.reset()
        self.error_history = {}
        self.last_errors = {}

        self.last_time_of_week = 0
        self.stationID = 2

        # how often to send RTCM type 1 messages
        self.type1_send_time = 1

        # how often to send RTCM type 3 messages
        self.type3_send_time = 10

        self.last_type1_time = 0
        self.last_type3_time = 0

    def reset(self):
        '''reset at the end of a message'''
        self.buf = ""
        self.rtcbits = 0
        self.rtcword = 0

    def bitreverse_array(self):
        ret = []
        for i in range(64):
            v = 0
            for b in range(6):
                if i & (1<<b):
                    v |= (1<<(5-b))
            ret.append(v)
        return ret

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

        i = self.calculate_parity(self.rtcword)
        # put parity into lower 6 bits of 32 bit word
        self.rtcword |= i
        # invert bits, if needed 
        if self.parity2 != 0:
            self.rtcword ^= 0x3fffffc0
        # copy parity bits  */
        self.parity2 = self.rtcword & 1
        self.parity1 = 0
        if (self.rtcword & 2) != 0:
            self.parity1 = 1

        rtcbufr = [0]*5

        for i in range(4,-1,-1):
            #* extract bottom 6 bits
            rtcbufr[i] = self.rtcword & 0x3f
            self.rtcword >>= 6
            # reverse the bit order
            rtcbufr[i] = self.bitreverse[rtcbufr[i]]
            # or in "01" into the upper bits
            rtcbufr[i] |= 0x40

        # we now the rtcm data complete in rtcbufr 0-4, send it
        self.buf += struct.pack('BBBBB', rtcbufr[0], rtcbufr[1], rtcbufr[2], rtcbufr[3], rtcbufr[4])
        self.rtcword = 0
        self.rtcbits = 0

    def xor_bits(self, word, bits):
        '''xor a set of bits from a word'''
        ret = 0
        for b in bits:
            ret ^= (word >> (29 - b)) & 1
        return ret

    def calculate_parity(self, word):
        '''calculate 6 parity bits for a word'''
        parity1 = self.parity1
        parity2 = self.parity2

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
        return ret

    def modZCount(self, satinfo):
        '''return modified Z-count'''
        tow = satinfo.raw.time_of_week
        toh = tow - 3600*(int(tow)//3600)
        return int(round(toh / 0.6))
        

    def RTCMType1(self, satinfo):
        '''create a RTCM type 1 message'''

        for svid in satinfo.prCorrected:
            err = satinfo.geometricRange[svid] - \
                (satinfo.prMeasured[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight + satinfo.receiver_clock_error*util.speedOfLight)
            if not svid in self.error_history:
                self.error_history[svid] = []
            self.error_history[svid].append(err)

        gpssec = util.gpsTimeToTime(satinfo.raw.gps_week, satinfo.raw.time_of_week)
        if gpssec < self.last_type1_time + self.type1_send_time:
            return ''

        self.last_type1_time = gpssec
        self.reset()

        tow = satinfo.raw.time_of_week
        deltat = tow - self.last_time_of_week
        self.last_time_of_week = tow

        errors = {}
        rates = {}
        for svid in self.error_history:
            errors[svid] = sum(self.error_history[svid])/float(len(self.error_history[svid]))
            if svid in self.last_errors and deltat > 0:
                rates[svid] = (errors[svid] - self.last_errors[svid]) / deltat
            else:
                rates[svid] = 0
                
            
        msgsatid     = []
        msgprc       = []
        msgprrc      = []
        msgiode      = []
        scalefactors = []
        for svid in self.error_history:
            prc  = int(round(errors[svid]/0.02))
            prrc = int(round(rates[svid]/0.002))

            sf = 0
            while prc > 32767 or prc < -32768 or prrc > 127 or prrc < -128:
                sf += 1
                prc  = (prc + 8)  // 16
                prrc = (prrc + 8) // 16
            if sf > 1:
                # skip satellites if we can't represent the error in the
                # number of bits allowed
                continue
            msgsatid.append(svid)
            msgprc.append(prc)
            msgprrc.append(prrc)
            msgiode.append(satinfo.ephemeris[svid].iode)
            scalefactors.append(sf)

        # clear the history
        self.last_errors = errors
        self.error_history = {}

        rtcmzcount = self.modZCount(satinfo)

        # first part of header
        self.addbits(8, 0x66)  # header id
        self.addbits(6, 1)     # msg type 1
        self.addbits(10, self.stationID) 

        #  second part of header
        self.addbits(13, rtcmzcount) # z-count
        self.addbits(3, self.rtcmseq) # seq no.
        self.rtcmseq = (self.rtcmseq + 1) % 8

        msgsatcnt = len(msgsatid)

        # now compute the word length of the message
        # each word contains 24 bits of data, plus 6 bits of parity
        bitlength = msgsatcnt * 40
        wordlength = bitlength // 24
        if (bitlength % 24) != 0:
            wordlength += 1

        self.addbits(5, wordlength)
        # health bits - mark as healthy
        self.addbits(3, 0)

        for i in range(msgsatcnt):
            self.addbits(1, scalefactors[i])
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
        return self.buf + "\r\n"


    def RTCMType3(self, satinfo):
        '''create a RTCM type 3 message'''

        gpssec = util.gpsTimeToTime(satinfo.raw.gps_week, satinfo.raw.time_of_week)
        if gpssec < self.last_type3_time + self.type3_send_time:
            return ''

        self.last_type3_time = gpssec

        self.reset()

        rtcmzcount = self.modZCount(satinfo)

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
        return self.buf + "\n\r"


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
