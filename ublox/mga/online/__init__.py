import ublox.mga

# working request:
# http://offline-live1.services.u-blox.com/GetOfflineData.ashx?gnss=gps;token=REDACTED
class MGAOnlineReqestor(ublox.mga.MGARequester):
    def __init__(self,
                 token=None,
                 gnss=["gps","glo"],
                 datatype=["eph","alm"],
                 lat=None,
                 lon=None,
                 alt=None,
                 pacc=None,
                 tacc=None,
                 latency=None,
                 filteronpos=None,
                 filteronsv=None):
        self.cachefile= cachefile
        self.token = token
        self.gnss = gnss
        self.datatype = datatype
        self.alt = alt
        self.pacc = pacc
        self.tacc = tacc
        self.latency = latency
        self.filteronpos = filteronpos
        self.filteronsv = filteronsv
        pass
