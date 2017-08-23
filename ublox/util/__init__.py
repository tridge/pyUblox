#!/usr/bin/env python
'''common utility functions'''

import math, os

radius_of_earth = 6378137.0 # in meters
speedOfLight    = 299792458.0 # in m/s
gpsPi           = 3.1415926535898  # Definition of Pi used in the GPS coordinate system

def gps_distance(lat1, lon1, lat2, lon2):
	'''return distance between two points in meters,
	coordinates are in degrees
	thanks to http://www.movable-type.co.uk/scripts/latlong.html'''
	from math import radians, cos, sin, sqrt, atan2
	lat1 = radians(lat1)
	lat2 = radians(lat2)
	lon1 = radians(lon1)
	lon2 = radians(lon2)
	dLat = lat2 - lat1
	dLon = lon2 - lon1
	
	a = sin(0.5*dLat)**2 + sin(0.5*dLon)**2 * cos(lat1) * cos(lat2)
	c = 2.0 * atan2(sqrt(a), sqrt(1.0-a))
	return radius_of_earth * c


def gps_bearing(lat1, lon1, lat2, lon2):
	'''return bearing between two points in degrees, in range 0-360
	thanks to http://www.movable-type.co.uk/scripts/latlong.html'''
	from math import sin, cos, atan2, radians, degrees
	lat1 = radians(lat1)
	lat2 = radians(lat2)
	lon1 = radians(lon1)
	lon2 = radians(lon2)
	dLat = lat2 - lat1
	dLon = lon2 - lon1    
	y = sin(dLon) * cos(lat2)
	x = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dLon)
	bearing = degrees(atan2(y, x))
	if bearing < 0:
		bearing += 360.0
	return bearing

class PosLLH:
    '''a class for latitude/longitude/altitude'''
    def __init__(self, lat, lon, alt):
        self.lat = lat
        self.lon = lon
        self.alt = alt

    def __str__(self):
        return '(%.8f, %.8f, %.8f)' % (self.lat, self.lon, self.alt)

    def ToECEF(self):
        '''convert from lat/lon/alt to ECEF

        Thanks to Nicolas Hennion
        http://www.nicolargo.com/dev/xyz2lla/
        '''
        from math import sqrt, pow, sin, cos
	a = 6378137.0
	e = 8.1819190842622e-2
	pi = gpsPi
	
	lat = self.lat*(pi/180.0)
	lon = self.lon*(pi/180.0)
	alt = self.alt

	n = a/sqrt((1.0-pow(e,2)*pow(sin(lat),2)))
	x= (n+alt)*cos(lat)*cos(lon)
	y= (n+alt)*cos(lat)*sin(lon)
	z= (n*(1-pow(e,2))+alt)*sin(lat)

	return PosVector(x, y, z)

    def distance(self, pos):
        '''return distance to another position'''
        if isinstance(pos, PosLLH):
            pos = pos.ToECEF()
        return self.ToECEF().distance(pos)

    def distanceXY(self, pos):
        '''return distance to another position'''
        if isinstance(pos, PosLLH):
            pos = pos.ToECEF()
        return self.ToECEF().distanceXY(pos)

class PosVector:
    '''a X/Y/Z vector class, used for ECEF positions'''
    def __init__(self, X,Y,Z, extra=None):
        self.X = float(X)
        self.Y = float(Y)
        self.Z = float(Z)
	# allow for some extra information to be carried in the vector
	self.extra = extra

    def __str__(self):
        return '(%.8f, %.8f, %.8f)' % (self.X, self.Y, self.Z)

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
        if isinstance(pos2, PosLLH):
            pos2 = pos2.ToECEF()
        return math.sqrt((self.X-pos2.X)**2 + 
                         (self.Y-pos2.Y)**2 + 
                         (self.Z-pos2.Z)**2)

    def distanceXY(self, pos2):
        import math
        if isinstance(pos2, PosLLH):
            pos2 = pos2.ToECEF()
	llh1 = self.ToLLH()
	llh2 = pos2.ToLLH()
	alt = (llh1.alt + llh2.alt)*0.5
	llh1.alt = alt
	llh2.alt = alt
	return llh1.distance(llh2)

    def bearing(self, pos):
	'''return bearing between two points in degrees, in range 0-360
	thanks to http://www.movable-type.co.uk/scripts/latlong.html'''
	from math import sin, cos, atan2, radians, degrees
	llh1 = self.ToLLH()
	llh2 = pos.ToLLH()
	
	lat1 = radians(llh1.lat)
	lat2 = radians(llh2.lat)
	lon1 = radians(llh1.lon)
	lon2 = radians(llh2.lon)
	dLat = lat2 - lat1
	dLon = lon2 - lon1    
	y = sin(dLon) * cos(lat2)
	x = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dLon)
	bearing = degrees(atan2(y, x))
	if bearing < 0:
		bearing += 360.0
	return bearing

    def offsetXY(self, pos):
        '''
	return offset X,Y in meters to pos
	'''
	from math import sin, cos, radians
        distance = self.distanceXY(pos)
        bearing = self.bearing(pos)
        x = distance * sin(radians(bearing))
        y = distance * cos(radians(bearing))
        return (x,y)

    def SagnacCorrection(self, pos2):
        '''return the Sagnac range correction. Based
           on on RTCM2.3 appendix C. Note that this is not a symmetric error!
	   The pos2 position should be the satellite
        '''
	OMGE = 7.2921151467e-5     # earth angular velocity (IS-GPS) (rad/s)
	return OMGE*(pos2.X * self.Y - pos2.Y * self.X) / speedOfLight
    
    def distanceSagnac(self, pos2):
        '''return distance taking into account Sagnac effect. Based
           on geodist() in rtklib. Note that this is not a symmetric distance!
	   The pos2 position should be the satellite

	   Note that the Sagnac distance is an alternative to rotating
	   the satellite positions using
	   rangeCorrection.correctPosition(). Only one of them should
	   be used
        '''
	return self.distance(pos2) + self.SagnacCorrection(pos2)

    def ToLLH(self):
        '''convert from ECEF to lat/lon/alt

        Thanks to Nicolas Hennion
        http://www.nicolargo.com/dev/xyz2lla/
        '''
        from math import sqrt, pow, cos, sin, pi, atan2

        a = radius_of_earth
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

def ParseLLH(pos_string):
    '''parse a lat,lon,alt string and return a PosLLH'''
    a = pos_string.split(',')
    if len(a) != 3:
        return None
    return PosLLH(float(a[0]), float(a[1]), float(a[2]))

def correctWeeklyTime(time):
    '''correct the time accounting for beginning or end of week crossover'''
    half_week       = 302400 # seconds
    corrTime        = time
    if time > half_week:
        corrTime    = time - 2*half_week
    elif time < -half_week:
        corrTime    = time + 2*half_week
    return corrTime


def gpsTimeToTime(week, sec):
    '''convert GPS week and TOW to a time in seconds since 1970'''
    epoch = 86400*(10*365 + (1980-1969)/4 + 1 + 6 - 2)
    return epoch + 86400*7*week + sec

def saveObject(filename, object):
    '''save an object to a file'''
    import pickle
    h = open(filename + '.tmp', mode='wb')
    pickle.dump(object, h)
    h.close()
    os.rename(filename + '.tmp', filename)


def loadObject(filename):
    '''load an object from a file'''
    import pickle
    try:
        h = open(filename, mode='rb')
	obj = pickle.load(h)
	h.close()
	return obj
    except Exception as e:
        return None
