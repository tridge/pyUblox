#! /usr/bin/env python

import ublox
import sys

from pylab import *

dev = ublox.UBlox(sys.argv[1])

raw = []
svi = []
pos = []

while True:
    msg = dev.receive_message()

    if msg is None:
        break

    n = msg.name()

    if n not in ['RXM_RAW', 'NAV_SVINFO']:
        continue

    msg.unpack()

    if n == 'RXM_RAW':
        raw.append(msg.numSV)
    elif n == 'NAV_SVINFO':
        svi.append(msg.numCh)

        # count how many of the active channels are used in the pos solution
        c = 0
        for s in msg.recs:
            if s.flags & 1:
                c += 1

        pos.append(c)

plot(raw, label="Raw")
plot(svi, label="SVI")
plot(pos, label="Pos")
legend()
show()
