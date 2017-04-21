import time
import ublox
import struct
import datetime

class MGATool(object):

    def configure_dev_ack_aiding(self):
        start = time.time()
        last_poll_sent = 0
        while True:
            now = time.time()
            if now-last_poll_sent > 1:
                self.dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5)
                last_poll_sent = now
            msg = self.dev.receive_message()
            if msg is None:
                time.sleep(0.01)
                continue
            if msg.msg_type() == (ublox.CLASS_CFG, ublox.MSG_CFG_NAVX5):
                print("Received NAVX5 message")
                if msg.ackAiding:
                    print("ack-aiding set")
                    break
                print("No aiding set")
            else:
                print("Waiting for NAVX5 message")
                time.sleep(0.1)

    def sendtime(self):
        '''upload a time to the receiver.  ack-aiding must be set!'''
        start = time.time()
        last_poll_sent = 0
        while True:
            now = time.time()
            if now-last_poll_sent > 1:
                msg = ublox.mga.MGA.msg_ini_time_utc()
                self.dev.send(msg)
                last_poll_sent = now
            msg = self.dev.receive_message()
            if msg.msg_type() == (ublox.CLASS_MGA, ublox.MSG_MGA_ACK):
                print("Got ack (%s)" % str(msg))
                if (msg.msgId == ublox.MSG_MGA_INI_TIME_UTC):
                    print("Correct ack (%s)" % str(msg))
                    if msg.infoCode == 0:
                        print("Infocode is good")
                    else:
                        print("Infocode is bad (%u)", msg.infoCode)
                    break

    def sendposition(self, position):
        '''upload a position to the receiver.  ack-aiding must be set!'''
        '''position must be a tuple of lat/lon/alt e.g. (149.0420946, -35.2103418, 652.954)'''
        last_poll_sent = 0
        while True:
            now = time.time()
            if now-last_poll_sent > 1:
                msg = ublox.mga.MGA.msg_ini_pos_llh(position)
                print("message: %s" % str(msg))
                self.dev.send(msg)
                last_poll_sent = now
            msg = self.dev.receive_message()
            if msg.msg_type() == (ublox.CLASS_MGA, ublox.MSG_MGA_ACK):
                print("Got ack (%s)" % str(msg))
                if (msg.msgId == ublox.MSG_MGA_INI_TIME_UTC):
                    print("Correct ack (%s)" % str(msg))
                    if msg.infoCode == 0:
                        print("Infocode is good")
                    else:
                        print("Infocode is bad (%u)", msg.infoCode)
                    break

    def configure_dev(self):
#        self.dev.set_logfile(opts.log, append=opts.append)
        self.dev.set_binary()
        self.dev.configure_poll_port()
#        self.dev.configure_poll(ublox.CLASS_CFG, ublox.MSG_CFG_USB)
#        self.dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_HW)
        self.dev.configure_poll(ublox.CLASS_MON, ublox.MSG_MON_VER)
        self.dev.configure_port(port=ublox.PORT_SERIAL1, inMask=1, outMask=1)
#        self.dev.configure_port(port=ublox.PORT_USB, inMask=1, outMask=1)
#        self.dev.configure_port(port=ublox.PORT_SERIAL2, inMask=1, outMask=1)
        self.dev.configure_poll_port()
        self.dev.configure_poll_port(ublox.PORT_SERIAL1)
#        self.dev.configure_poll_port(ublox.PORT_SERIAL2)
#        self.dev.configure_poll_port(ublox.PORT_USB)
        self.dev.configure_solution_rate(rate_ms=1000)

        # self.dev.set_preferred_dynamic_model(opts.dynModel)
        # self.dev.set_preferred_usePPP(opts.usePPP)

        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSLLH, 1)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_STATUS, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SOL, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELNED, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_SVINFO, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_VELECEF, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_POSECEF, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_RAW, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SFRB, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_SVSI, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_ALM, 0)
        self.dev.configure_message_rate(ublox.CLASS_RXM, ublox.MSG_RXM_EPH, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_TIMEGPS, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_CLOCK, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_DOP, 0)
        self.dev.configure_message_rate(ublox.CLASS_NAV, ublox.MSG_NAV_PVT, 0)

        self.configure_dev_ack_aiding()
