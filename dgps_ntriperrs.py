#!/usr/bin/env python
'''
two receiver DGPS test code
'''

import ublox, sys, time, struct
import ephemeris, util
import RTCMv3_decode
import nmea_wrapper

from optparse import OptionParser

parser = OptionParser("dgps_test.py [options]")
parser.add_option("--port2", help="serial port 2", default='/dev/ttyACM1')
parser.add_option("--port3", help="serial port 3", default=None)
parser.add_option("--baudrate", type='int',
                  help="serial baud rate", default=38400)
parser.add_option("--log2", help="log file2", default=None)
parser.add_option("--log3", help="log file3", default=None)
parser.add_option("--nmea-2", action='store_true', default=False, help='Port 2 is an NMEA receiver')
parser.add_option("--nmea-3", action='store_true', default=False, help='Port 3 is an NMEA receiver')
parser.add_option("--reopen", action='store_true', default=False, help='re-open on failure')
parser.add_option("--nortcm", action='store_true', default=False, help="don't send RTCM to receiver2")
parser.add_option("--reference", help="reference position (lat,lon,alt)")
parser.add_option("--ecef-reference", help="reference position (X,Y,Z)")
parser.add_option("--dynmodel2", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv2")
parser.add_option("--dynmodel3", type='int', default=ublox.DYNAMIC_MODEL_AIRBORNE4G, help="dynamic model for recv3")
parser.add_option("--module-reset", action='store_true', help="cold start all the modules")

parser.add_option("--ntrip-server")
parser.add_option("--ntrip-port", type='int', default=2101)
parser.add_option("--ntrip-user")
parser.add_option("--ntrip-password")
parser.add_option("--ntrip-mount")

(opts, args) = parser.parse_args()

if opts.reference is not None:
    reference_position = util.ParseLLH(opts.reference).ToECEF()
elif opts.ecef_reference is not None:
    reference_position = util.PosVector(*opts.ecef_reference.split(','))
else:
    reference_position = None

def setup_port(port, log, append=False):
    dev = ublox.UBlox(port, baudrate=opts.baudrate, timeout=0.01)
    dev.set_logfile(log, append=append)
    dev.set_binary()
    dev.configure_poll_port()
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
    dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
    dev.configure_poll(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS)
    dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_VER)
    dev.configure_port(port=ublox.PORT_SERIAL1, inMask=0x7, outMask=1)
    dev.configure_port(port=ublox.PORT_USB, inMask=0x7, outMask=1)
    dev.configure_port(port=ublox.PORT_SERIAL2, inMask=0x7, outMask=1)
    dev.configure_poll_port()
    dev.configure_poll_port(ublox.PORT_SERIAL1)
    dev.configure_poll_port(ublox.PORT_SERIAL2)
    dev.configure_poll_port(ublox.PORT_USB)
    return dev

if opts.nmea_2:
    dev2 = nmea_wrapper.NMEAModule(opts.port2, opts.baudrate)
    dev2.set_logfile(opts.log2)
else:
    dev2 = setup_port(opts.port2, opts.log2)

if opts.port3 is not None:
    if opts.nmea_3:
        dev3 = nmea_wrapper.NMEAModule(opts.port3, opts.baudrate)
        dev3.set_logfile(opts.log3)
    else:
        dev3 = setup_port(opts.port3, opts.log3)
else:
    dev3 = None

last_msg2_time = time.time()
last_msg3_time = time.time()

rx2_pos = None
rx3_pos = None

if opts.module_reset:
    dev2.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    if dev3 is not None:
        dev3.module_reset(ublox.RESET_COLD, ublox.RESET_HW)

    time.sleep(1)
    dev2.close()

    if dev3 is not None:
        dev3.close()

    time.sleep(1)

    if opts.nmea_2:
        dev2 = None
    else:
        dev2 = setup_port(opts.port2, opts.log2)

    if opts.port3 is not None:
        if opts.nmea_3:
            dev3 = None
        else:
            dev3 = setup_port(opts.port3, opts.log3)
    else:
        dev3 = None


if not opts.nmea_2:
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DGPS, 1)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 1)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
    dev2.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
    dev2.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
    dev2.configure_solution_rate(rate_ms=1000)

if dev3 is not None and not opts.nmea_3:
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 1)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
    dev3.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 1)
    dev3.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
    dev3.configure_solution_rate(rate_ms=1000)

# we want the ground station to use a stationary model, and the roving
# GPS to use a highly dynamic model
if not opts.nmea_2:
    dev2.set_preferred_dynamic_model(opts.dynmodel2)
    dev2.set_preferred_dgps_timeout(60)

if dev3 is not None and not opts.nmea_3:
    dev3.set_preferred_dynamic_model(opts.dynmodel3)

errlog = open(time.strftime('errlog-%y%m%d-%H%M.txt'), mode='w')
errlog.write("normal DGPS normal-XY DGPS-XY\n")

def display_diff(name, pos1, pos2):
    print("%13s err: %6.2f errXY: %6.2f pos=%s" % (name, pos1.distance(pos2), pos1.distanceXY(pos2), pos1.ToLLH()))

def handle_device2(msg):
    global rx2_pos
    '''handle message from rover GPS'''
    if msg.name() == 'NAV_DGPS':
        msg.unpack()
        print("DGPS: age=%u numCh=%u" % (msg.age, msg.numCh))
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        rx2_pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)

        print("-----------------")
        display_diff("REF<->RECV2", rx2_pos, reference_position)
        
        if dev3 is not None and rx3_pos is not None:
            display_diff("REF<->RECV3", reference_position, rx3_pos)
            errlog.write("%f %f %f %f\n" % (
                reference_position.distance(rx3_pos),
                reference_position.distance(rx2_pos),
                reference_position.distanceXY(rx3_pos),
                reference_position.distanceXY(rx2_pos)))
            errlog.flush()

def handle_device3(msg):
    global rx3_pos
    '''handle message from uncorrected rover GPS'''
    if msg.name() == "NAV_POSECEF":
        msg.unpack()
        pos = util.PosVector(msg.ecefX*0.01, msg.ecefY*0.01, msg.ecefZ*0.01)
        rx3_pos = pos
                                            
def send_rtcm(msg):
    print(msg)
    dev2.write(msg)

RTCMv3_decode.run_RTCM_converter(opts.ntrip_server, opts.ntrip_port, opts.ntrip_user, opts.ntrip_password, opts.ntrip_mount, rtcm_callback=send_rtcm)

while True:
    # get a message from the reference GPS
    msg = dev2.receive_message_noerror()
    if msg is not None:
        handle_device2(msg)
        last_msg2_time = time.time()

    if dev3 is not None:
        msg = dev3.receive_message_noerror()
        if msg is not None:
            handle_device3(msg)
            last_msg3_time = time.time()

    if opts.reopen and time.time() > last_msg2_time + 5:
        dev2.close()
        dev2 = setup_port(opts.port2, opts.log2, append=True)
        last_msg2_time = time.time()
        sys.stdout.write('R2')

    if dev3 is not None and opts.reopen and time.time() > last_msg3_time + 5:
        dev3.close()
        dev3 = setup_port(opts.port3, opts.log3, append=True)
        last_msg3_time = time.time()
        sys.stdout.write('R3')

    sys.stdout.flush()
