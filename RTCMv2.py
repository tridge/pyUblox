import struct, util, positionEstimate

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

        # if history_length is > 0 then do error averaging over
        # history_length values. If ==0 then average over samples between
        # RTCM points
        #self.history_length = 10
        self.history_length = 120

        self.last_time_of_week = 0
        self.stationID = 2

        # how often to send RTCM type 1 messages
        self.type1_send_time = 1

        # how often to send RTCM type 3 messages
        self.type3_send_time = 30

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

    def modZCount(self):
        '''return modified Z-count'''
        tow = self.time_of_week
        toh = tow - 3600*(int(tow)//3600)
        return int(round(toh / 0.6))
        

    def calcRTCMPosition(self, satinfo, msgsatid, msgprc, scalefactors):
        '''
        calculate a position using the raw reference receiver data
        and the generated RTCM data. This should be close to the reference
        position if we are calculating the RTCM data correctly
        '''
        msgsatcnt = len(msgsatid)
        
        pranges = {}
        for i in range(msgsatcnt):
            svid = msgsatid[i]
            err = msgprc[i]*0.02
            if scalefactors[i] == 1:
                err *= 16.0
            if not svid in satinfo.prSmoothed:
                continue

            pranges[svid] = satinfo.prSmoothed[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight
#            pranges[svid] = satinfo.prMeasured[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight - (satinfo.tropospheric_correction[svid])
#            pranges[svid] = satinfo.prMeasured[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight - (satinfo.ionospheric_correction[svid])
#            pranges[svid] = satinfo.prMeasured[svid] + satinfo.satellite_clock_error[svid]*util.speedOfLight - (satinfo.tropospheric_correction[svid] + satinfo.ionospheric_correction[svid])

            pranges[svid] += err
            #print(svid, prc, err, satinfo.receiver_clock_error*util.speedOfLight, satinfo.satellite_clock_error[svid]*util.speedOfLight, satinfo.tropospheric_correction[svid], satinfo.ionospheric_correction[svid])
        lastpos = satinfo.rtcm_position
        if lastpos is None:
            lastpos = util.PosVector(0,0,0)
        if len(pranges) >= 4:
            print pranges
            print satinfo.prCorrected
            satinfo.rtcm_position = positionEstimate.positionLeastSquares_ranges(satinfo, pranges, lastpos, 0)


    def getUDRE(self, svid, weight):
        '''return a UDRE given the weighting'''
        if weight > 0.9:
            return 0 # <= 1m
        if weight > 0.5:
            return 1 # <= 4m
        if weight > 0.25:
            return 2 # <= 8m
        return 3 # > 8m


    def RTCMType1(self, satinfo, maxsats=32):
        '''create a RTCM type 1 message'''

        for svid in satinfo.prSmoothed:
            prAdjusted = satinfo.prSmoothed[svid] + satinfo.receiver_clock_error*util.speedOfLight + satinfo.satellite_clock_error[svid]*util.speedOfLight
            #prAdjusted -= satinfo.tropospheric_correction[svid]
            #prAdjusted -= satinfo.ionospheric_correction[svid]

            err = satinfo.geometricRange[svid] - prAdjusted
            if not svid in self.error_history:
                self.error_history[svid] = []
            self.error_history[svid].append(err)

        self.time_of_week = satinfo.raw.time_of_week
        self.gps_week = satinfo.raw.gps_week

        svids = sorted([ (s, satinfo.elevation[s]) for s in satinfo.elevation], key=lambda x: x[1])
        svids = svids[-maxsats:]
        self.iode = {}
        for svid,elevation in svids:
            self.iode[svid] = satinfo.ephemeris[svid].iode

        print("RTCM Type 1, {} sats".format(len(svids)))

        return self.RTCMType1_step()

    def RTCMType1_ext(self, errset, iTOW, week, iode):
        for svid in self.error_history.copy():
            if not svid in errset:
                self.error_history.pop(svid)
        for svid in errset:
            if not svid in self.error_history:
                self.error_history[svid] = []

            self.error_history[svid].append(errset[svid])

        self.time_of_week = iTOW
        self.gps_week = week
        self.iode = iode

        return self.RTCMType1_step(False)

    def RTCMType1_step(self, throttle=True):
        gpssec = util.gpsTimeToTime(self.gps_week, self.time_of_week)
        if gpssec < self.last_type1_time + self.type1_send_time and throttle:
            return ''

        self.last_type1_time = gpssec
        self.reset()

        tow = self.time_of_week
        deltat = tow - self.last_time_of_week

        errors = {}
        rates = {}
        for svid in self.error_history:
            #errors[svid] = sum(self.error_history[svid])/float(len(self.error_history[svid]))

            l = len(self.error_history[svid])
            # Extract the median half of the error array and take the average over that.  This
            # will reject outliers that we see pretty often, though most of those outliers only
            # last for 1 or 2 samples at a time so we might want to broaden this window.
            trim = sorted(self.error_history[svid])[l // 4: 3 * l // 4 + 1]
            errors[svid] = sum(trim) / float(len(trim))

            if svid in self.last_errors and deltat > 0:
                rates[svid] = (errors[svid] - self.last_errors[svid]) / deltat
            else:
                rates[svid] = 0
            
        msgsatid     = []
        msgprc       = []
        msgprrc      = []
        msgiode      = []
        msgudre      = []
        scalefactors = []
        for svid in self.error_history:
            if not svid in self.iode or not svid in errors:
                continue

            prc  = int(round(errors[svid]/0.02))
            prrc = int(round(rates[svid]/0.002))

            sf = 0
            while prc > 32767 or prc < -32768:
                sf += 1
                prc  = (prc + 8)  // 16
            if sf > 1:
                # skip satellites if we can't represent the error in the
                # number of bits allowed
                continue
            if sf == 1:
                prrc = (prrc + 8) // 16
            prrc = min(prrc, 127)
            prrc = max(prrc, -128)
            msgsatid.append(svid)
            msgprc.append(prc)
            msgprrc.append(prrc)
            msgiode.append(self.iode[svid])
            scalefactors.append(sf)

        msgsatcnt = len(msgsatid)
        if msgsatcnt == 0:
            return ''

        # clear the history
        self.last_errors = errors.copy()
        if self.history_length == 0:
            self.error_history = {}
        else:
            for svid in self.error_history:
                while len(self.error_history[svid]) > self.history_length:
                    self.error_history[svid].pop(0)
        self.last_time_of_week = tow

        rtcmzcount = self.modZCount()

        # first part of header
        self.addbits(8, 0x66)  # header id
        self.addbits(6, 1)     # msg type 1
        self.addbits(10, self.stationID) 

        #  second part of header
        self.addbits(13, rtcmzcount) # z-count
        self.addbits(3, self.rtcmseq) # seq no.
        self.rtcmseq = (self.rtcmseq + 1) % 8

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
        print("MSG: bitlength=%u wordlength=%u len=%u" % (bitlength, wordlength, len(self.buf)))
        return self.buf + "\r\n"


    def RTCMType3(self, satinfo):
        '''create a RTCM type 3 message'''

        self.time_of_week = satinfo.raw.time_of_week
        self.gps_week = satinfo.raw.gps_week

        if satinfo.reference_position is not None:
            self.pos = satinfo.reference_position
        else:
            self.pos = satinfo.average_position

        return self.RTCMType3_step()

    def RTCMType3_ext(self, iTOW, week, pos):
        self.time_of_week = iTOW
        self.gps_week = week
        self.pos = pos

        return self.RTCMType3_step(False)

    def RTCMType3_step(self, throttle=True):
        gpssec = util.gpsTimeToTime(self.gps_week, self.time_of_week)
        if gpssec < self.last_type3_time + self.type3_send_time and throttle:
            return ''

        self.last_type3_time = gpssec

        self.reset()

        rtcmzcount = self.modZCount()

        self.addbits(8, 0x66)  # header id
        self.addbits(6, 3)     # msg type 1
        self.addbits(10, 2)    # station id

        #  1st word should be sent here
        self.addbits(13, rtcmzcount) # z-count
        self.addbits(3, self.rtcmseq) # seq no.
        self.rtcmseq = (self.rtcmseq + 1) % 8

        self.addbits(5, 4) # word length
        self.addbits(3, 0) # health bits

        pos = self.pos

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


def generateRTCM2_Message1(satinfo, maxsats=32):
    '''generate RTCMv2 corrections from satinfo'''
    bits = satinfo.rtcm_bits
    if bits is None:
        bits = RTCMBits()
        satinfo.rtcm_bits = bits
    msg = bits.RTCMType1(satinfo, maxsats=maxsats)
    return msg

def generateRTCM2_Message3(satinfo):
    '''generate RTCMv2 reference position from satinfo'''
    bits = satinfo.rtcm_bits
    if bits is None:
        bits = RTCMBits()
        satinfo.rtcm_bits = bits
    msg = bits.RTCMType3(satinfo)
    return msg
