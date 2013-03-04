import util, ephemeris

class rawPseudoRange:
    '''class to hold raw range information from a receiver'''
    def __init__(self, gps_week, time_of_week):
        # time of week in seconds, including fractions of a second
        self.time_of_week = time_of_week
        self.gps_week     = gps_week
        self.gps_time     = util.gpsTimeToTime(gps_week, time_of_week)
        self.prMeasured   = {}
        self.quality      = {}

    def add(self, svid, prMes, quality):
        '''add a pseudo range for a given svid'''
        self.prMeasured[svid] = prMes
        self.quality[svid]    = quality
        

class SatelliteData:
    '''class to hold satellite data from AID_EPH, RXM_SFRB and RXM_RAW messages plus calculated
       positions and error terms'''
    def __init__(self):
        self.ephemeris = {}
        self.azimuth = {}
        self.elevation = {}
        self.lastpos = util.PosVector(0,0,0)
        self.receiver_clock_error = 0
        self.rtcm_bits = None
        self.last_rtcm_msg3 = util.gpsTimeToTime(0,0)
        self.reset()
        self.average_position = None
        self.position_sum = util.PosVector(0,0,0)
        self.position_count = 0
        self.reference_position = None
        self.receiver_position = None
        self.ionospheric = util.loadObject('ionospheric.dat')
        if self.ionospheric is None:
            self.ionospheric = {}

    def reset(self):
        self.satpos = {}
        self.prMeasured = {}
        self.ionospheric_correction = {}
        self.tropospheric_correction = {}
        self.satellite_clock_error = {}
        self.prCorrected = {}
        self.geometricRange = {}

    def valid(self, svid):
        '''return true if we have all data for a given svid'''
        if not svid in self.ephemeris:
            #print("no eph")
            return False
        return True

    def add_AID_EPH(self, msg):
        '''add some AID_EPH ephemeris data'''
        eph = ephemeris.EphemerisData(msg)
        if eph.valid:
            self.ephemeris[eph.svid] = eph

    def add_RXM_SFRB(self, msg):
        '''add some RXM_SFRB subframe data'''
        ion = ephemeris.IonosphericData(msg)
        if ion.valid:
            self.ionospheric[msg.svid] = ion
            util.saveObject('ionospheric.dat', self.ionospheric)

    def add_RXM_RAW(self, msg):
        '''add some RXM_RAW pseudo range data'''
        self.raw = rawPseudoRange(msg.week, msg.iTOW*1.0e-3)
        for i in range(msg.numSV):
            self.raw.add(msg.recs[i].sv,
                         msg.recs[i].prMes,
                         msg.recs[i].mesQI)

    def add_NAV_POSECEF(self, msg):
        '''add a NAV_POSECEF message'''
        self.receiver_position = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
            
    def add_message(self, msg):
        '''add information from ublox messages'''
        if msg.name() == 'AID_EPH':
            self.add_AID_EPH(msg)
        elif msg.name() == 'RXM_SFRB':
            self.add_RXM_SFRB(msg)
        elif msg.name() == 'RXM_RAW':
            self.add_RXM_RAW(msg)
        elif msg.name() == 'NAV_POSECEF':
            self.add_NAV_POSECEF(msg)

