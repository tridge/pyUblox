'''
Functions for calculating satellite position given ephemeris data and time
Thanks to Paul Riseborough for lots of help with this!
'''

import util

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

    Omegae_dot              = 7.2921151467e-5  # Earth rotation rate, [rad/s]
    GM                      = 3.986005e14      # Earth universal gravitational parameter, [m^3/s^2]
    gpsPi                   = util.gpsPi
    
    # Don't need to correct for satellite clock as it is a common mode error
    time = transmitTime # - satelliteClockCorrection

    # Set time zero to cooincide with the start time for the ephemeris
    tk = util.correctWeeklyTime(time - ephemeris.toe)

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
    dts -= 2.0 * sqrt(GM * ephemeris.A) * ephemeris.ecc * sin(E) / (util.speedOfLight * util.speedOfLight)
    
    #print dts

    return util.PosVector(X,Y,Z)
