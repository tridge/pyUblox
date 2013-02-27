'''
Functions for calculating satellite position given ephemeris data and time
Thanks to Paul Riseborough for lots of help with this!
'''

class PosLLH:
    '''a class for latitude/longitude/altitude'''
    def __init__(self, lat, lon, alt):
        self.lat = lat
        self.lon = lon
        self.alt = alt

    def __str__(self):
        return '(%f, %f, %f)' % (self.lat, self.lon, self.alt)

class PosVector:
    '''a X/Y/Z vector class, used for ECEF positions'''
    def __init__(self, X,Y,Z):
        self.X = X
        self.Y = Y
        self.Z = Z

    def __add__(self, v):
        return PosVector(self.X + v.X,
                         self.Y + v.Y,
                         self.Z + v.Z)

    def __mul__(self, v):
        return PosVector(self.X * v,
                         self.Y * v,
                         self.Z * v)

    def __div__(self, v):
        return PosVector(self.X / v,
                         self.Y / v,
                         self.Z / v)

    def distance(self, pos2):
        import math
        return math.sqrt((self.X-pos2.X)**2 + 
                         (self.Y-pos2.Y)**2 + 
                         (self.Z-pos2.Z)**2)

    def ToLLH(self):
        '''convert from ECEF to lat/lon/alt

        Thanks to Nicolas Hennion
        http://www.nicolargo.com/dev/xyz2lla/
        '''
        from math import sqrt, pow, cos, sin, pi, atan2

        a = 6378137
        e = 8.1819190842622e-2

        b = sqrt(pow(a,2) * (1-pow(e,2)))
        ep = sqrt((pow(a,2)-pow(b,2))/pow(b,2))
        p = sqrt(pow(self.X,2)+pow(self.Y,2))
        th = atan2(a*self.Z, b*p)
        lon = atan2(self.Y, self.X)
        lat = atan2((self.Z+ep*ep*b*pow(sin(th),3)), (p-e*e*a*pow(cos(th),3)))
        n = a/sqrt(1-e*e*pow(sin(lat),2))
        alt = p/cos(lat)-n
        lat = (lat*180)/pi
        lon = (lon*180)/pi
        return PosLLH(lat, lon, alt)


def checkTime(time):
    '''correct the time accounting for beginning or end of week crossover'''
    half_week       = 302400 # seconds
    corrTime        = time
    if time > half_week:
        corrTime    = time - 2*half_week
    elif time < -half_week:
        corrTime    = time + 2*half_week
    return corrTime



def satPosition(ephemeris, transmitTime):
    '''
    % Required inputs
    %
    % Name                  Type	Dimension	Description, units
    %
    % ephemeris.A           double  1           Semimajor axis, m
    % ephemeris.cic         double  1           Inclination - amplitude of cosine, rad
    % ephemeris.cis         double  1           Inclination - amplitude of sine, rad
    % ephemeris.crc         double  1           Orbit radius - amplitude of cosine, m
    % ephemeris.crs         double  1           Orbit radius - amplitude of sine, m
    % ephemeris.cuc         double  1           Argument of latitude - amplitude of cosine, rad
    % ephemeris.cus         double  1           Argument of latitude - amplitude of sine, rad
    % ephemeris.deltaN      double  1           Mean motion difference, rad/sec
    % ephemeris.ecc         double  1           Eccentricity
    % ephemeris.i0          double  1           Inclination angle at reference time, rad
    % ephemeris.idot        double  1           Rate of inclination, rad/sec
    % ephemeris.M0          double  1           Mean anomaly of reference time, rad
    % ephemeris.omega       double  1           Argument of perigee, rad
    % ephemeris.omega_dot   double  1           Rate of right ascension, rad/sec
    % ephemeris.omega0      double  1           Right ascension, rad
    % ephemeris.toe         double  1           Reference time for ephemeris, sec
    % transmitTime          double  1           Time of message transmission, sec
    
    % Define Constants
    '''
    from math import sin, cos, sqrt, fmod, atan2, pow

    gpsPi                   = 3.1415926535898  # Definition of Pi used in the GPS coordinate system
    Omegae_dot              = 7.2921151467e-5  # Earth rotation rate, [rad/s]
    GM                      = 3.986005e14      # Earth universal gravitational parameter, [m^3/s^2]
    speedOfLight            = 299792458

    # Don't need to correct for satellite clock as it is a common mode error
    time = transmitTime # - satelliteClockCorrection

    # Set time zero to cooincide with the start time for the ephemeris
    tk = checkTime(time - ephemeris.toe)

    # Find the ECEF position for the satellite using Keplers equations plus
    # additional harmonics

    # Semi-major axis
    a = ephemeris.A

    # Initial mean motion
    n0 = sqrt(GM / pow(a,3))

    # Mean motion
    n = n0 + ephemeris.deltaN

    # Mean anomaly
    M = ephemeris.M0 + n * tk
    # Reduce mean anomaly to between 0 and 360 deg
    M = fmod(M + 2*gpsPi, 2*gpsPi)

    # Initial guess of eccentric anomaly
    E = M

    # Iteratively compute eccentric anomaly
    for ii in range(10):
        E_old = E
        E = M + ephemeris.ecc * sin(E)
        dE = fmod(E - E_old, 2*gpsPi)
    
        if abs(dE) < 1.0e-12:
            # Necessary precision is reached, exit from the loop
            break

    # Wrap eccentric anomaly to between 0 and 360 deg
    E = fmod(E + 2*gpsPi, 2*gpsPi)

    # Calculate the true anomaly
    nu = atan2(sqrt(1 - pow(ephemeris.ecc,2)) * sin(E), cos(E)-ephemeris.ecc)

    # Compute angle phi
    phi = nu + ephemeris.omega
    # Reduce phi to between 0 and 360 deg
    phi = fmod(phi, 2*gpsPi)

    # Correct argument of latitude
    u = phi + ephemeris.cuc * cos(2*phi) + ephemeris.cus * sin(2*phi)

    # Correct radius
    r = a * (1 - ephemeris.ecc*cos(E)) + ephemeris.crc * cos(2*phi) + ephemeris.crs * sin(2*phi)

    # Correct inclination
    i = ephemeris.i0 + ephemeris.idot * tk + ephemeris.cic * cos(2*phi) + ephemeris.cis * sin(2*phi)

    # Compute the angle between the ascending node and the Greenwich meridian
    Omega = ephemeris.omega0 + (ephemeris.omega_dot - Omegae_dot)*tk - Omegae_dot * ephemeris.toe
    # Reduce to between 0 and 360 deg
    Omega = fmod(Omega + 2*gpsPi, 2*gpsPi)

    # Compute satellite coordinates
    X = cos(u)*r * cos(Omega) - sin(u)*r * cos(i)*sin(Omega)
    Y = cos(u)*r * sin(Omega) + sin(u)*r * cos(i)*cos(Omega)
    Z = sin(u)*r * sin(i)

    # do we need this?
    tk = transmitTime - ephemeris.toc
    dts = ephemeris.af0 + ephemeris.af1 * tk + ephemeris.af2 * tk * tk

    # relativity correction
    dts -= 2.0 * sqrt(GM * ephemeris.A) * ephemeris.ecc * sin(E) / (speedOfLight * speedOfLight)
    
    #print dts

    return PosVector(X,Y,Z)
