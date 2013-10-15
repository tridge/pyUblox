#!/usr/bin/env python

import socket
import base64
import sys

dummy, server, port, username, password, mountpoint = sys.argv

pwd = base64.b64encode("{}:{}".format(username, password))

header =\
"GET /{} HTTP/1.1\r\n".format(mountpoint) +\
"Host \r\n".format(server) +\
"Ntrip-Version: Ntrip/2.0\r\n" +\
"User-Agent: NTRIP pyUblox/0.0\r\n" +\
"Connection: close\r\n" +\
"Authorization: Basic {}\r\n\r\n".format(pwd)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((server,int(port)))
s.send(header)

resp = s.recv(1024)

if resp.startswith("STREAMTABLE"):
    raise NTRIPError("Invalid or No Mountpoint")
elif not resp.startswith("HTTP/1.1 200 OK"):
    raise NTRIPError("Invalid Server Response")

try:
    while True:
        # There are some length bytes at the head here but it actually
        # seems more robust to simply let the higher level RTCMv3 parser
        # frame everything itself and bin the garbage as required.

        #length = s.recv(4)

        #try:
        #    length = int(length.strip(), 16)
        #except ValueError:
        #    continue

        data = s.recv(1024)
        print(data)
        #print >>sys.stderr, [ord(d) for d in data]
        sys.stdout.flush()

finally:
    s.close()


