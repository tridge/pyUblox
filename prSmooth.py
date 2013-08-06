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

    def step(self, raw):
        '''calculate satinfo.prSmoothed'''
        slipmax = 15.0 # criterion for cycle slip determination
        Nmax = 100  # limit value for number of observations

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
        
            if svid not in N or raw.quality[svid] < 5:
                N[svid] = 0
            N[svid] = min(N[svid] + 1, Nmax)

            if N[svid] > 1:
                slipdist=abs((Pn - P[svid]) - (Cn - C[svid]))
            else:
                slipdist = 0
            if slipdist > slipmax:
                # cycle slip found, re-initialize filter
                N[svid] = 1 

            if N[svid] == 1:
                # first observation
                S[svid] = Pn
            else:
                S[svid] = Pn / N[svid] + (S[svid] + Cn - C[svid]) * (N[svid] - 1) / N[svid]

            '''
            if svid in P:
                print("svid=%u N=%u Sdiff=%g slip=%f Cn=%f Pn=%f Cdiff=%f Pdiff=%f" % (
                    svid, N[svid], S[svid] - Pn, slipdist, Cn, Pn, Cn-C[svid], Pn-P[svid]))
            '''

            # store Pn and Cn for next epoch
            P[svid] = Pn
            C[svid] = Cn
