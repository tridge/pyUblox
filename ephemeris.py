import util

class EphemerisData:
    '''container for parsing a AID_EPH message
    Thanks to Sylvain Munaut <tnt@246tNt.com>
    http://cgit.osmocom.org/cgit/osmocom-lcs/tree/gps.c
    for the C version of this parser

    See IS-GPS-200F.pdf Table 20-III for the field meanings, scaling factors and
    field widths
    '''

    def GET_FIELD_U(self, w, nb, pos):
        return (((w) >> (pos)) & ((1<<(nb))-1))

    def twos_complement(self, v, nb):
        sign = v >> (nb-1)
        value = v
        if sign != 0:
            value = value - (1<<nb)
        return value

    def GET_FIELD_S(self, w, nb, pos):
        v = self.GET_FIELD_U(w, nb, pos)
        return self.twos_complement(v, nb)

    def __init__(self, msg):
        from math import pow

        self._msg = msg
        self.svid = msg.svid
        self.how = msg.how
        
        if not msg.have_field('sf1d'):
            # it doesn't contain the optional part
            self.valid = False
            return

        week_no    = self.GET_FIELD_U(msg.sf1d[0], 10, 14)
        code_on_l2 = self.GET_FIELD_U(msg.sf1d[0],  2, 12)
        sv_ura     = self.GET_FIELD_U(msg.sf1d[0],  4,  8)
        sv_health  = self.GET_FIELD_U(msg.sf1d[0],  6,  2)
        l2_p_flag  = self.GET_FIELD_U(msg.sf1d[1],  1, 23)
        t_gd       = self.GET_FIELD_S(msg.sf1d[4],  8,  0)
        iodc       = (self.GET_FIELD_U(msg.sf1d[0],  2,  0) << 8) | self.GET_FIELD_U(msg.sf1d[5],  8, 16)

        t_oc       = self.GET_FIELD_U(msg.sf1d[5], 16,  0)
        a_f2       = self.GET_FIELD_S(msg.sf1d[6],  8, 16)
        a_f1       = self.GET_FIELD_S(msg.sf1d[6], 16,  0)
        a_f0       = self.GET_FIELD_S(msg.sf1d[7], 22,  2)
        
        c_rs       = self.GET_FIELD_S(msg.sf2d[0], 16,  0)
        delta_n    = self.GET_FIELD_S(msg.sf2d[1], 16,  8)
        m_0        = (self.GET_FIELD_S(msg.sf2d[1],  8,  0) << 24) | self.GET_FIELD_U(msg.sf2d[2], 24,  0)
        c_uc       = self.GET_FIELD_S(msg.sf2d[3], 16,  8)
        e          = (self.GET_FIELD_U(msg.sf2d[3],  8,  0) << 24) | self.GET_FIELD_U(msg.sf2d[4], 24,  0)
        c_us       = self.GET_FIELD_S(msg.sf2d[5], 16,  8)
        a_powhalf  = (self.GET_FIELD_U(msg.sf2d[5],  8,  0) << 24) | self.GET_FIELD_U(msg.sf2d[6], 24,  0)
        t_oe       = self.GET_FIELD_U(msg.sf2d[7], 16,  8)
        fit_flag   = self.GET_FIELD_U(msg.sf2d[7],  1,  7)
        
        c_ic       = self.GET_FIELD_S(msg.sf3d[0], 16,  8)
        omega_0    = (self.GET_FIELD_S(msg.sf3d[0],  8,  0) << 24) | self.GET_FIELD_U(msg.sf3d[1], 24,  0)
        c_is       = self.GET_FIELD_S(msg.sf3d[2], 16,  8)
        i_0        = (self.GET_FIELD_S(msg.sf3d[2],  8,  0) << 24) | self.GET_FIELD_U(msg.sf3d[3], 24,  0)
        c_rc       = self.GET_FIELD_S(msg.sf3d[4], 16,  8)
        w          = (self.GET_FIELD_S(msg.sf3d[4],  8,  0) << 24) | self.GET_FIELD_U(msg.sf3d[5], 24,  0)
        omega_dot  = self.GET_FIELD_S(msg.sf3d[6], 24,  0)
        idot       = self.GET_FIELD_S(msg.sf3d[7], 14,  2)
        
        self._rsvd1     = self.GET_FIELD_U(msg.sf1d[1], 23,  0)
        self._rsvd2     = self.GET_FIELD_U(msg.sf1d[2], 24,  0)
        self._rsvd3     = self.GET_FIELD_U(msg.sf1d[3], 24,  0)
        self._rsvd4     = self.GET_FIELD_U(msg.sf1d[4], 16,  8)
        self.aodo       = self.GET_FIELD_U(msg.sf2d[7],  5,  2)

        # Definition of Pi used in the GPS coordinate system
        gpsPi          = 3.1415926535898

        # now form variables in radians, meters and seconds etc
        self.Tgd       = t_gd    * pow(2, -31)
        self.A         = pow(a_powhalf * pow(2,-19), 2.0)
        self.cic       = c_ic    * pow(2, -29)
        self.cis       = c_is    * pow(2, -29)
        self.crc       = c_rc    * pow(2, -5)
        self.crs       = c_rs    * pow(2, -5)
        self.cuc       = c_uc    * pow(2, -29)
        self.cus       = c_us    * pow(2, -29)
        self.deltaN    = delta_n * pow(2, -43) * gpsPi
        self.ecc       = e       * pow(2, -33)
        self.i0        = i_0     * pow(2, -31) * gpsPi
        self.idot      = idot    * pow(2, -43) * gpsPi
        self.M0        = m_0     * pow(2, -31) * gpsPi
        self.omega     = w       * pow(2, -31) * gpsPi
        self.omega_dot = omega_dot * pow(2, -43) * gpsPi
        self.omega0    = omega_0 * pow(2, -31) * gpsPi
        self.toe       = t_oe * pow(2, 4)

        # clock correction information
        self.toc = t_oc * pow(2, 4)
        self.af0 = a_f0 * pow(2, -31)
        self.af1 = a_f1 * pow(2, -43)
        self.af2 = a_f2 * pow(2, -55)


        iode1           = self.GET_FIELD_U(msg.sf2d[0],  8, 16)
        iode2           = self.GET_FIELD_U(msg.sf3d[7],  8, 16)
        self.valid = (iode1 == iode2) and (iode1 == (iodc & 0xff))
        self.iode = iode1

    def __eq__(self, other):
        '''allow for equality testing
        See http://stackoverflow.com/questions/3550336/comparing-two-objects
        '''
        attrs = [ 'svid', 'valid', 'Tgd', 'A', 'cic', 'cis', 'crc', 'crs', 'cuc', 'cus',
                  'deltaN', 'ecc', 'i0', 'idot', 'M0', 'omega', 'omega_dot', 'omega0',
                  'toe', 'toc', 'af0', 'af1', 'af2', 'iode' ]
        for a in attrs:
            v1, v2 = [getattr(obj, a, None) for obj in [self, other]]
            if v1 is None or v2 is None or v1 != v2:
                return False
        return True

    def __ne__(self, other):
        '''allow for equality testing'''
        return not self.__eq__(other)


class IonosphericData:
    '''decode ionospheric data from a RXM_SFRB subframe 4 message
    see http://home-2.worldonline.nl/~samsvl/nav2eu.htm
    '''

    def extract_uint8(self, v, b):
        return (v >> (8*(3-b))) & 255

    def extract_int8(self, v, b):
        value = self.extract_uint8(v, b)
        if value > 127:
            value -= 256
        return value
        
    def __init__(self, msg):
        '''parse assuming a subframe 4 page 18 message containing ionospheric data'''
        words = msg.dwrd
        for i in range(10):
            words[i] = (words[i] & 0xffffff)
        words[0] &= 0xff0000
        if not words[0] in [0x8b0000, 0x740000]:
            #print("words[0]=0x%06x" % words[0])
            self.valid = False
            return
        if words[0] == 0x740000:
            print("SFRB invert")
            for i in range(10):
                words[i] ^= 0xffffff

        self.svid = msg.svid
        self.id = (words[1] >> 2) & 0x07
        self.pageID = (words[2] & 0x3f0000) >> 16

        self.a0     = self.extract_int8(words[2], 2) * pow(2, -30)
        self.a1     = self.extract_int8(words[2], 3) * pow(2, -27)
        self.a2     = self.extract_int8(words[3], 1) * pow(2, -24)
        self.a3     = self.extract_int8(words[3], 2) * pow(2, -24)
        self.b0     = self.extract_int8(words[3], 3) * pow(2, 11)
        self.b1     = self.extract_int8(words[4], 1) * pow(2, 14)
        self.b2     = self.extract_int8(words[4], 2) * pow(2, 16)
        self.b3     = self.extract_int8(words[4], 3) * pow(2, 16)
        self.leap   = self.extract_uint8(words[8], 1)

        # this checks if we have the right subframe
        self.valid  = (self.pageID == 56 and self.id == 4)
        #print("svid=%u id=%u pageID=%u" % (self.svid, self.id, self.pageID))
#        '''
        if self.valid:
            print("a0=%g a1=%g a2=%g a3=%g b0=%g b1=%g b2=%g b3=%g leap=%u" % (
                self.a0, self.a1, self.a2, self.a3,
                self.b0, self.b1, self.b2, self.b3,
                self.leap))
#                '''
                  
    def __eq__(self, other):
        '''allow for equality testing
        See http://stackoverflow.com/questions/3550336/comparing-two-objects
        '''
        attrs = [ 'svid', 'valid', 'a0', 'a1', 'a2', 'a3',
                  'b0', 'b1', 'b2', 'b3', 'leap', 'id', 'pageID' ]
        for a in attrs:
            v1, v2 = [getattr(obj, a, None) for obj in [self, other]]
            if v1 is None or v2 is None or v1 != v2:
                return False
        return True

    def __ne__(self, other):
        '''allow for equality testing'''
        return not self.__eq__(other)
