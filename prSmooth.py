'''
pseudo-range smoothing based on:
http://home-2.worldonline.nl/~samsvl/smooth.htm
'''

class prSmooth:
    '''hold state of PR smoothing'''
    def __init__(self):
        # history length for a SV
        self.N = {}
        self.P = {}
        self.C = {}
        self.prSmoothed = {}
        self.slipmax = 15.0
        self.Nmax = 200

    def reset(self, svid):
        '''reset the history for a svid - used on IODE change'''
        if svid in self.prSmoothed:
            print("RESET IODE for SVID=%u" % svid)
            self.N.pop(svid)
            self.P.pop(svid)
            self.C.pop(svid)
            self.prSmoothed.pop(svid)

    def weight(self, svid):
        '''return weighting to be used in position least squares'''
        N = self.N
        if not svid in N:
            return 0.01
        if N[svid] > 20:
            return 1.0
        return 1.0 - (20 - N[svid])/20.0

    def step(self, raw):
        '''calculate satinfo.prSmoothed'''

        N = self.N
        P = self.P
        C = self.C
        S = self.prSmoothed

        k = S.keys()
        for svid in k:
            if not svid in raw.prMeasured:
                # the satellite has disappeared - remove its history
                N.pop(svid)
                P.pop(svid)
                C.pop(svid)
                S.pop(svid)
    
        for svid in raw.prMeasured:
            Pn = raw.prMeasured[svid]
            Cn = raw.cpMeasured[svid]
        
            if svid not in N:
                N[svid] = 0
            N[svid] = min(N[svid] + 1, self.Nmax)

            if N[svid] > 1:
                slipdist=abs((Pn - P[svid]) - (Cn - C[svid]))
            else:
                slipdist = 0
            if slipdist > self.slipmax or raw.lli[svid] != 0:
                # cycle slip found, re-initialize filter
                N[svid] = 1 

            if N[svid] == 1:
                # first observation
                S[svid] = Pn
            else:
                S[svid] = Pn / N[svid] + (S[svid] + Cn - C[svid]) * (N[svid] - 1) / N[svid]

            '''
            if svid in P:
                print("svid=%u N=%u Sdiff=%g slip=%f lli=%u Cn=%f Pn=%f Cdiff=%f Pdiff=%f" % (
                    svid, N[svid], S[svid] - Pn, slipdist, raw.lli[svid], Cn, Pn, Cn-C[svid], Pn-P[svid]))
            '''

            # store Pn and Cn for next epoch
            P[svid] = Pn
            C[svid] = Cn
