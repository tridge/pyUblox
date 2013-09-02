#!/usr/bin/env python
''' Decode RTCM v3 messages and extract parameters required to generate v2 Type 1 and 3 messages.

The end game here is to be able to use RTCMv3 broadcast CORS corrections from, e.g. Geoscience
Australia, as RTCMv2 input to COTS uBlox receviers

Much of this work, esp. getting the unit conversions right, is based on  rtcm.c and rtcm3.c from
rtklib.

'''


import sys
import bitstring as bs
import satelliteData, util, RTCMv2

from bitstring import BitStream

RTCMv3_PREAMBLE = 0xD3
PRUNIT_GPS = 299792.458
CLIGHT = 299792458.0

FREQ1 =      1.57542E9
FREQ2 =      1.22760E9
FREQ5 =      1.17645E9
FREQ6 =      1.27875E9
FREQ7 =      1.20714E9
FREQ8 =      1.191795E9

L2codes = ['CODE_L2C', 'CODE_L2P', 'CODE_L2W', 'CODE_L2W']

lam_carr= [CLIGHT/FREQ1,CLIGHT/FREQ2,CLIGHT/FREQ5,CLIGHT/FREQ6,CLIGHT/FREQ7,CLIGHT/FREQ8]


# Globals required to build v2 messages
iode_rtcm = 0
corr_set = {}
statid = 0 #initially only support 1 reference station

satinfo = satelliteData.SatelliteData()

cp_hist = {}

def adjcp(sat, freq, cp):
    '''Adjust carrier phase for rollover'''
    if not sat in cp_hist or cp_hist[sat] is None:
        cp_hist[sat] = [0.0, 0.0]

    if cp_hist[sat][freq] == 0.0:
        return cp
    elif cp > cp_hist[sat][freq] - 750.0:
        cp += 1500.0
    elif cp > cp_hist[sat][freq] + 750.0:
        cp -= 1500.0

    cp_hist[sat][freq] = cp

    return cp


lock_hist = {}
def lossoflock(sat, freq, lock):
    '''Calc loss of lock indication'''
    if not sat in lock_hist or lock_hist[sat] is None:
        lock_hist[sat] = [0, 0]

    lli = (not lock and not lock_hist[sat][freq]) or (lock < lock_hist[sat][freq])

    lock_hist[sat][freq] = lock

    return lli


def snratio(snr):
    return int(snr <= 0.0 or 0.0 if 255.5 <= snr else snr * 4.0 + 0.5)


def decode_1004(pkt):
    global statid, corr_set

    statid = pkt.read(12).uint

    tow = pkt.read(30).uint * 0.001
    sync = pkt.read(1).uint
    nsat = pkt.read(5).uint

    smoothed = bool(pkt.read(1).uint)
    smint = pkt.read(3).uint

    for n in range(nsat):
        svid = pkt.read(6).uint
        corr_set[svid] = {}

        code1 = pkt.read(1).uint
        pr1 = pkt.read(24).uint
        ppr1 = pkt.read(20).int
        lock1 = pkt.read(7).uint
        amb = pkt.read(8).uint
        cnr1 = pkt.read(8).uint
        code2 = pkt.read(2).uint
        pr21 = pkt.read(14).int
        ppr2 = pkt.read(20).int
        lock2 = pkt.read(7).uint
        cnr2 = pkt.read(8).uint

        pr1 = pr1 * 0.02 + amb * PRUNIT_GPS

        if ppr1 != 0x80000:
            corr_set[svid]['P1'] = pr1
            cp1 = adjcp(svid, 0, ppr1 * 0.0005 / lam_carr[0])
            corr_set[svid]['L1'] = pr1 / lam_carr[0] + cp1

        corr_set[svid]['LLI1'] = lossoflock(svid, 0, lock1)
        corr_set[svid]['SNR1'] = snratio(cnr1 * 0.25)
        corr_set[svid]['CODE1'] = 'CODE_P1' if code1 else 'CODE_C1'
        
        if pr21 != 0xE000:
            corr_set[svid]['P2'] = pr1 + pr21 * 0.02

        if ppr2 != 0x80000:
            cp2 = adjcp(svid, 1, ppr2 * 0.0005 / lam_carr[1])
            corr_set[svid]['L2'] = pr1 / lam_carr[1] + cp2

        corr_set[svid]['LLI2'] = lossoflock(svid, 1, lock2)
        corr_set[svid]['SNR2'] = snratio(cnr2 * 0.25)
        corr_set[svid]['CODE2'] = L2codes[code2]

        satinfo.prSmoothed[svid] = corr_set[svid]['P1']
        
    satinfo.raw.time_of_week = tow

    #print(corr_set)

def decode_1006(pkt):
    global ref_pos

    staid = pkt.read(12).uint

    # Only set reference station location if it's the one used by
    # the observations
    if staid != statid:
        return

    itrf = pkt.read(6).uint
    pkt.read(4)
    ref_x = pkt.read(38).int * 0.0001
    pkt.read(2)
    ref_y = pkt.read(38).int * 0.0001
    pkt.read(2)
    ref_z = pkt.read(38).int * 0.0001
    anth = pkt.read(16).uint * 0.0001
 
    satinfo.reference_position = [ref_x, ref_y, ref_z]
    satinfo.receiver_position = [ref_x, ref_y, ref_z]


def decode_1033(pkt):
    # Don't really care about any of this stuff at this stage..
    des = ''
    sno = ''
    rec = ''
    ver = ''
    rsn = ''

    stat_id = pkt.read(12).uint

    n = pkt.read(8).uint
    for i in range(n):
        des = des + chr(pkt.read(8).uint)

    setup = pkt.read(8).uint

    n = pkt.read(8).uint
    for i in range(n):
        sno = sno + chr(pkt.read(8).uint)

    n = pkt.read(8).uint
    for i in range(n):
        rec = rec + chr(pkt.read(8).uint)

    n = pkt.read(8).uint
    for i in range(n):
        ver = ver + chr(pkt.read(8).uint)

    n = pkt.read(8).uint
    for i in range(n):
        rsn = rsn + chr(pkt.read(8).uint)

    #print(des, sno, rec, ver, rsn)
    

def decode_1019(pkt):
    global satinfo

    svid = pkt.read(6).uint
    week = pkt.read(10).uint
    acc = pkt.read(4).uint
    l2code = pkt.read(2).uint
    idot = pkt.read(14).int
    iode = pkt.read(8).uint
    toc = pkt.read(16).uint
    af2 = pkt.read(8).int
    af1 = pkt.read(16).int
    af0 = pkt.read(22).int
    iodc = pkt.read(10).uint
    crs = pkt.read(16).int
    deltan = pkt.read(16).int
    m0 = pkt.read(32).int
    cuc = pkt.read(16).int
    e = pkt.read(32).uint
    cus = pkt.read(16).int
    rootA = pkt.read(32).uint
    toe = pkt.read(16).uint
    cic = pkt.read(16).int
    omega0 = pkt.read(32).int
    cis = pkt.read(16).int
    i0 = pkt.read(32).int
    crc = pkt.read(16).int
    omega = pkt.read(32).int
    omegadot = pkt.read(24).int
    tgd = pkt.read(8).int
    health = pkt.read(6).uint
    l2p = pkt.read(1).uint
    fit = pkt.read(1).uint

    satinfo.ephemeris[svid].crs = crs
    satinfo.ephemeris[svid].deltaN = deltan
    satinfo.ephemeris[svid].M0 = m0
    satinfo.ephemeris[svid].cuc = cuc
    satinfo.ephemeris[svid].ecc = e
    satinfo.ephemeris[svid].cus = cus
    satinfo.ephemeris[svid].A = rootA * rootA
    satinfo.ephemeris[svid].toe = toe
    satinfo.ephemeris[svid].cic = cic
    satinfo.ephemeris[svid].omega0 = omega0
    satinfo.ephemeris[svid].cis = cis
    satinfo.ephemeris[svid].i0 = i0
    satinfo.ephemeris[svid].crc = crc
    satinfo.ephemeris[svid].omega = omega
    satinfo.ephemeris[svid].omega_dot = omegadot
    satinfo.ephemeris[svid].idot = idot
    satinfo.ephemeris[svid].iode = iode

    satinfo.raw.gps_week = week

def regen_v2_type1():
    try:
        msg = RTCMv2.generateRTCM2_Message1(satinfo)
        if len(msg) > 0:
            print(msg)
    except Exception as e:
        print e

def regen_v2_type3():
    try:
        msg = RTCMv2.generateRTCM2_Message3(satinfo)
        if len(msg) > 0:
            print(msg)

    except Exception as e:
        print e


def parse_rtcmv3(pkt):
    pkt_type = pkt.read(12).uint

    if pkt_type == 1004:
        decode_1004(pkt)
        regen_v2_type1()
    elif pkt_type == 1006:
        decode_1006(pkt)
        regen_v2_type3()
    elif pkt_type == 1033:
        decode_1033(pkt)
    else:
        print("Ignore {}".format(pkt_type))

while True:
    d = ord(sys.stdin.read(1))
    if d != RTCMv3_PREAMBLE:
        continue

    pack_stream = BitStream()

    l1 = ord(sys.stdin.read(1))
    l2 = ord(sys.stdin.read(1))

    pack_stream.append(bs.pack('2*uint:8', l1, l2))
    pack_stream.read(6)
    pkt_len = pack_stream.read(10).uint

    pkt = sys.stdin.read(pkt_len)
    parity = sys.stdin.read(3)

    if True: #TODO check parity
        for d in pkt:
            pack_stream.append(bs.pack('uint:8',ord(d)))

        parse_rtcmv3(pack_stream)




