
import pynmea.streamer, pynmea.nmea
import util, os

class FakeUbloxMessage:

    def __init__(self, name, fields):
        self.name = name
        self._fields = fields

    def __getattr__(self, name):
        '''allow access to message fields'''
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError(name)

    def __str__(self):
        return name + ":" + str(self._fields)

    def name(self):
        return self.name

    def unpack(self):
        pass

class NMEAModule:
    def __init__(self, port, baudrate=38400, timeout=0.01):
        self.serial_device = port
        self.baudrate = baudrate
        self.read_only = False

        if os.path.isfile(self.serial_device):
            self.read_only = True
            self.dev = open(self.serial_device, mode='rb')
        else:
            import serial
            self.dev = serial.Serial(self.serial_device, baudrate=self.baudrate,
                                     dsrdtr=False, rtscts=False, xonxoff=False, timeout=timeout)
        self.logfile = None
        self.log = None
        self.debug_level = 0

        self.streamer = pynmea.streamer.NMEAStream()

        self.obj_buffer = []

    def close(self):
	'''close the device'''
        self.dev.close()
	self.dev = None

    def set_debug(self, debug_level):
        '''set debug level'''
        self.debug_level = debug_level

    def debug(self, level, msg):
        '''write a debug message'''
        if self.debug_level >= level:
            print(msg)

    def set_logfile(self, logfile, append=False):
	'''setup logging to a file'''
        if self.log is not None:
            self.log.close()
            self.log = None
        self.logfile = logfile
        if self.logfile is not None:
            if append:
                mode = 'ab'
            else:
                mode = 'wb'
            self.log = open(self.logfile, mode=mode)

    def receive_message(self, ignore_eof=False):
        l = self.dev.readline()

        if l is None or len(l) == 0:
            return None

        self.debug(0, l)

        obs = self.streamer.get_objects(data=l)

        if len(obs) == 0:
            self.debug(1, "No object in line {}".format(l))

        for o in obs:
            try:
                # We're looking for something that quacks like a GGA message with LLH and DGPS status

                # GGA contains both position and DGPS info, create the position message first
                ecef = util.PosLLH(o.lattitude, o.longitude, o.altitude_units).ToECEF()
                fields = dict([('ecefX', ecef.X * 100.), ('ecefY', ecef.Y * 100.), ('ecefZ', ecef.Z * 100.)])

                m = FakeUbloxMessage('NAV_POSECEF', fields)
                self.obj_buffer.append(m)
                self.debug(0, str(m))

                # DGPS info.  Cheats slightly by giving the number of active sats, not corrected ones
                fields = dict([('numCh', o.num_sats), ('age', o.age_gps_data)])

                m = FakeUbloxMessage('NAV_DGPS', fields)
                self.obj_buffer.append(m)
                self.debug(0, str(m))
            except AttributeError as e:
                self.debug(0, e)

        if len(self.obj_buffer) > 0:
            return self.obj_buffer.pop()

        return None

    def receive_message_noerror(self, ignore_eof=False):
        try:
            return self.receive_message(ignore_eof)
        except (AttributeError, OSError) as e:
            print(e)
            return None


    def write(self, buf):
        if not self.read_only:
            self.dev.write(buf)

    def module_reset(self):
        pass



