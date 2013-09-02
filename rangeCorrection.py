'''
pseudorange correction
See http://home-2.worldonline.nl/~samsvl/pseucorr.htm
'''

import util

def sv_clock_correction(satinfo, svid, transmitTime, Trel):
    '''space vehicle clock correction'''
    from math import sin, sqrt

    toc = satinfo.ephemeris[svid].toc
    eph = satinfo.ephemeris[svid]
    
    T = util.correctWeeklyTime(transmitTime - toc)
    
    dTclck = eph.af0 + eph.af1 * T + eph.af2 * T * T + Trel # - eph.Tgd

    return dTclck


def ionospheric_correction(satinfo,
                           svid,
                           transmitTime,
                           posestimate_ecef):
    '''calculate ionospheric delay
    based on ionocorr() from http://home-2.worldonline.nl/~samsvl/stdalone.pas
    '''
    from math import radians, cos, sin

    if not svid in satinfo.ionospheric:
        return 0
    
    llh = posestimate_ecef.ToLLH()
    pi = util.gpsPi

    # convert to semi-circles
    Latu = radians(llh.lat) / pi
    Lonu = radians(llh.lon) / pi
    Az = radians(satinfo.azimuth[svid]) / pi
    El = radians(satinfo.elevation[svid]) / pi

    a0 = satinfo.ionospheric[svid].a0
    a1 = satinfo.ionospheric[svid].a1
    a2 = satinfo.ionospheric[svid].a2
    a3 = satinfo.ionospheric[svid].a3
    b0 = satinfo.ionospheric[svid].b0
    b1 = satinfo.ionospheric[svid].b1
    b2 = satinfo.ionospheric[svid].b2
    b3 = satinfo.ionospheric[svid].b3
    
    # main calculation
    phi = 0.0137 / (El + 0.11) - 0.022
    Lati = Latu + phi * cos(Az * pi)
    if Lati > 0.416:
        Lati = 0.416
    elif Lati < -0.416:
        Lati = -0.416
        
    Loni = Lonu + phi * sin(Az * pi) / cos(Lati * pi)
    Latm = Lati + 0.064 * cos((Loni - 1.617) * pi)
    
    T = 4.32E+4 * Loni + transmitTime
    
    while T >= 86400:
        T = T - 86400
    while T < 0:
        T = T + 86400
        
    F = 1.0 + 16.0 * (0.53 - El) * (0.53 - El) * (0.53 - El)
    
    per = b0 + b1 * Latm + b2 * Latm * Latm + b3 * Latm * Latm * Latm
    
    if per < 72000.0:
        per = 72000.0
    x = 2 * pi * (T - 50400.0) / per
    amp = a0 + a1 * Latm + a2 * Latm * Latm + a3 * Latm * Latm * Latm
    if amp < 0.0:
        amp = 0.0
    if abs(x) >= 1.57:
        dTiono = F * 5.0E-9
    else:
        dTiono = F * (5.0E-9 + amp * (1.0 - x * x / 2.0 + x * x * x * x /24.0))
    return dTiono * util.speedOfLight

def tropospheric_correction_standard(satinfo, svid):
    '''tropospheric correction using standard atmosphere values'''
    from math import sin, sqrt, radians

    El = radians(satinfo.elevation[svid])
    
    dRtrop = 2.312 / sin(sqrt(El * El + 1.904E-3)) + 0.084 / sin(sqrt(El * El + 0.6854E-3))
    return dRtrop


def tropospheric_correction_sass(satinfo, svid, pos):
    '''tropospheric correction, based on rtklib tropmodel()'''
    from math import pow, exp, cos, radians

    humidity = 0.7

    llh = pos.ToLLH()
    altitude = llh.alt
    lat_rad = radians(llh.lat)
    lon_rad = radians(llh.lon)
    elevation = radians(satinfo.elevation[svid])
    
    temp0 = 15.0 # temparature at sea level
    
    if altitude < -100.0 or 1e4 < altitude or elevation <= 0:
        return 0.0
    
    pres = 1013.25 * pow(1.0 - 2.2557e-5 * altitude, 5.2568)
    temp = temp0 - 6.5e-3 * altitude + 273.16
    
    e = 6.108 * humidity * exp((17.15 * temp - 4684.0) / (temp - 38.45))
    
    # saastamoninen model
    z = util.gpsPi / 2.0 - elevation
    trph = 0.0022768 * pres / (1.0 - 0.00266 * cos(2.0 * lat_rad) - 0.00028 * altitude/1e3)/cos(z)
    trpw = 0.002277  * (1255.0 / temp + 0.05) * e / cos(z)
    return trph+trpw

