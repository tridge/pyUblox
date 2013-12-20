#!/usr/bin/env python
'''
NTRIP -> RTCMv2 transcode, UDP link
'''

import time, socket
import RTCMv3_decode

from optparse import OptionParser

parser = OptionParser("ntrip_to_udp.py [options]")

parser.add_option("--ntrip-server", default='192.104.43.25')
parser.add_option("--ntrip-port", type='int', default=2101)
parser.add_option("--ntrip-user")
parser.add_option("--ntrip-password")
parser.add_option("--ntrip-mount", default='TID10')

parser.add_option("--udp-port", type='int', default=13320)
parser.add_option("--udp-addr", default="127.0.0.1")


(opts, args) = parser.parse_args()

packet_count = 0

def send_rtcm(msg):
    global packet_count
    packet_count += 1
    msg = msg[:-2] # Trim off \r\n that the RTCM encoder puts there
    port.sendto(msg,(opts.udp_addr, opts.udp_port))
    print(len(msg), msg)

RTCMv3_decode.run_RTCM_converter(opts.ntrip_server, opts.ntrip_port, opts.ntrip_user, opts.ntrip_password, opts.ntrip_mount, rtcm_callback=send_rtcm)

port = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# port.setsockopt...


while True:
	print(packet_count)
	time.sleep(10)
