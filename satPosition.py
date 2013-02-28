'''
Functions for calculating satellite position given ephemeris data and time
Thanks to Paul Riseborough for lots of help with this!
'''

import util

def satPosition(satinfo, svid, transmitTime):
    '''calculate satellite position
    Based upon http://home-2.worldonline.nl/~samsvl/stdalone.pas
    '''
    from math import sqrt, atan, sin, cos
    
    eph = satinfo.ephemeris[svid]

    # WGS 84 value of earth's univ. grav. par.
    mu = 3.986005E+14

    # WGS 84 value of earth's rotation rate
    Wedot = 7.2921151467E-5

    # relativistic correction term constant
    F = -4.442807633E-10

    pi = util.gpsPi

    Crs = eph.crs
    dn  = eph.deltaN
    M0  = eph.M0
    Cuc = eph.cuc
    ec  = eph.ecc
    Cus = eph.cus
    A   = eph.A
    Toe = eph.toe
    Cic = eph.cic
    W0  = eph.omega0
    Cis = eph.cis
    i0  = eph.i0
    Crc = eph.crc
    w   = eph.omega
    Wdot = eph.omega_dot
    idot = eph.idot

    T = transmitTime - Toe
    if T > 302400:
        T = T - 604800
    if T < -302400:
        T = T + 604800

    n0 = sqrt(mu / (A*A*A))
    n = n0 + dn

    M = M0 + n*T
    E = M
    for ii in range(20):
        Eold = E
        E = M + ec * sin(E)
        if abs(E - Eold) < 1.0e-12:
            break

    snu = sqrt(1 - ec*ec) * sin(E) / (1 - ec*cos(E))
    cnu = (cos(E) - ec) / (1 - ec*cos(E))
    if cnu == 0:
        nu = pi/2 * snu / abs(snu)
    elif (snu == 0) and (cnu > 0):
        nu = 0
    elif (snu == 0) and (cnu < 0):
        nu = pi
    else:
        nu = atan(snu/cnu)
        if cnu < 0:
            nu += pi * snu / abs(snu)

    phi = nu + w

    du = Cuc*cos(2*phi) + Cus*sin(2*phi)
    dr = Crc*cos(2*phi) + Crs*sin(2*phi)
    di = Cic*cos(2*phi) + Cis*sin(2*phi)

    u = phi + du
    r = A*(1 - ec*cos(E)) + dr
    i = i0 + idot*T +di

    Xdash = r*cos(u)
    Ydash = r*sin(u)

    Wc = W0 + (Wdot - Wedot)*T - Wedot*Toe

    satpos = util.PosVector(
        Xdash*cos(Wc) - Ydash*cos(i)*sin(Wc),
        Xdash*sin(Wc) + Ydash*cos(i)*cos(Wc),
        Ydash*sin(i))

    # relativistic correction term
    satpos.extra = F * ec * sqrt(A) * sin(E)

    return satpos

def correctPosition(satpos, time_of_flight):
    '''correct the satellite position for the time it took the message to get to the receiver'''
    from math import sin, cos
    
    # WGS-84 earth rotation rate
    We = 7.292115E-5
    
    alpha = time_of_flight * We
    X = satpos.X
    Y = satpos.Y
    satpos.X = X * cos(alpha) + Y * sin(alpha)
    satpos.Y = -X * sin(alpha) + Y * cos(alpha)
