import ublox.mga

import datetime
import struct
import threading
import time
import urllib
import urllib2
import os
import sys

class OfflineRequester(ublox.mga.Requester):
    def __init__(self,
                 token=None,
                 gnss=["gps","glo"],
                 period=None):
        self.token = token
        self.gnss = gnss
        self.period = period
        pass

    def scriptpath(self):
        return 'GetOfflineData.ashx'

    def request_params(self):
        params = {
            "token": self.token,
            "gnss": ','.join(self.gnss),
        };
        if self.period is not None:
            params["period"] = self.period
        return params

class OfflineCache(object):
    def __init__(self, token=None, cachefile=None):
        self.should_quit = False
        self.data = None
        self.cachefile = cachefile
        self.last_request_time_utc = datetime.date(2000,1,1) #!
        if token is None:
            try:
                token = self.set_token_from_dotfile()
            except IOError as e:
                if e.errno != 2:
                    raise
        self.requester = OfflineRequester(token=token)

    def token_filepath(self):
        from os.path import expanduser
        home = expanduser("~")
        return os.path.join(home, ".pyublox", "api_token")

    def set_token_from_dotfile(self):
        fh = open(self.token_filepath(), "r")
        content = fh.read()
        fh.close()
        content = content.rstrip()
        return content

    def date_utc_for_message(self, msg):
        msg.unpack()
        return datetime.date(msg.year+2000,msg.month,msg.day)

    def cache_fh(self):
        try:
            fh = open(self.cachefile, 'r')
        except IOError as e:
            if e.errno == 2:
                return None
            raise e
        return fh

    def cache_dev(self):
        fh = self.cache_fh()
        if fh is None:
            return
        return ublox.UBlox(fh)

    def get_data_date_closest_to(self, date_utc):
        '''retrieve data from cache closest to supplied date; returns None if
        the cache is empty
        '''

        # first find date in the cache closest to today
        dev = self.cache_dev()
        if dev is None:
            return

        now_date_utc = self.now_date_utc()
        closest = None
        closest_date = None
        while True:
            msg = dev.receive_message()
            if msg is None:
                break
#            print("received message: %s" % str(msg))

            data_date_utc = self.date_utc_for_message(msg)
#            print("date: %s" % str(data_date_utc))

            delta = abs(now_date_utc - data_date_utc)
#            print("Delta: %s" % str(delta))
            if (closest is None or delta < closest_delta):
                closest = data_date_utc
                closest_delta = delta

        return closest

    '''Return date of last offline data message we have'''
    def get_last_date(self):
        dev = self.cache_dev()
        if dev is None:
            return
        now_date_utc = self.now_date_utc()
        lastmsg = None
        while True:
            msg = dev.receive_message()
            if msg is None:
                break
            lastmsg = msg
        return self.date_utc_for_message(lastmsg)

    '''return all messages with specific date'''
    def messages_for_date(self, date):
        dev = self.cache_dev()
        now_date_utc = self.now_date_utc()
        ret = []
        while True:
            msg = dev.receive_message()
            if msg is None:
                break
#            print("received message: %s" % str(msg))
            if self.date_utc_for_message(msg) != now_date_utc:
                continue
            ret.append(msg)
        return ret

    def get_data_date_closest_to_now(self):
        now = self.now_date_utc()
        return self.get_data_date_closest_to(now)

    def now_date_utc(self):
        '''return a datetime.date object for now (utc time)'''
        now_utc = datetime.datetime.utcnow()
        return datetime.date(now_utc.year,now_utc.month, now_utc.day)

    def is_today(self, date):
        return date == self.now_date_utc()

    def should_request_fresh_data(self):
        now_date_utc = self.now_date_utc()
        if now_date_utc - self.last_request_time_utc < datetime.timedelta(1000):
            # no more than 1 request per hour (no idea what API limits are!)
            return False;

        last_date = self.get_last_date()
        if last_date is None:
            return True
        delta = now_date_utc - last_date
        print("Delta: %s" % str(delta))
        if abs(delta.days) > 1000:
            print("Time not set yet?")
            # this almost certainly means the system we are running on
            # hasn't got a good idea of what the current time is, so
            # we can't tell whether our data is stale or not.  Err on
            # the safe side of not making a request.
            return False
        if delta.days > 14: # I made that up
            return False
        return True

#        if best_date == now_date_utc:
        # waiting for a day-rollover, but need to check should_quit
#            print("Good data; waiting for roll-over")

    def freshen(self):
        self.last_request_time_utc = self.now_date_utc()
        fh = self.requester.make_request()
        content = fh.read()
        new_cachefile_name = self.cachefile + "-new"
        cache_fh = open(new_cachefile_name, "w")
        cache_fh.write(content)
        cache_fh.close()
        os.rename(new_cachefile_name, self.cachefile)

    def update_thread_main(self):
        '''thread main for updating the cache from uBlox servers'''
        while (True):
            if self.should_quit:
                break
#            if (last_update is not None and
            if not self.should_request_fresh_data():
                time.sleep(1)
                continue
            try:
                self.freshen()
            except Exception as e:
                print("Caught generic exception (%s)" % str(e))
                time.sleep(1)

    def start_update_thread(self):
        self.update_thread = threading.Thread(target=self.update_thread_main)
        self.update_thread.start()

    def stop_update_thread(self):
        self.update_thread.should_quit = True
        self.update_thread.join() # should we just skip this bit?

class Offline(object):
    def __init__(self, token=None, cachefile=None):
        self.cache = OfflineCache(cachefile=cachefile, token=token)

    def freshen(self):
        self.cache.freshen()

    def get_data_quick(self):
        '''return any data we have, even if it is ancient.  Some data is
        better than no data, assuming we can give the uBlox a date/time
        '''
        now_utc = datetime.datetime.utcnow()
        now_date_utc = datetime.date(now_utc.year,now_utc.month, now_utx.day)
        return self.cache.data_closest_to(now_date_utc)

    def upload(self, dev):
        date = self.cache.get_data_date_closest_to_now()
        if date is None:
#            print("Updating cache (no data?)")
            self.cache.update_cache()
            date = self.cache.get_data_date_closest_to_now()

#        print("Got date (%s)" % str(date))
        msgs = self.cache.messages_for_date(date)
#        print("Filtered messages: %s" % str(msgs))

        # upload to GPS unit:
        acked_by_sv = {}
        msgs_by_sv = {}
        for msg in msgs:
            msgs_by_sv[(msg.gnssId,msg.svId)] = msg

        count_outstanding = 0
        outstanding_max = 10
        while True:
            msgs_to_send = {}
            for x in msgs_by_sv.keys():
                if acked_by_sv.get(x, None) == None:
#                    print("%s not acked yet" % str(x))
                    msgs_to_send[x] = msgs_by_sv[x]
            if len(msgs_to_send.keys()) == 0:
                break

            while len(msgs_to_send.keys()):
                now = time.time()
                for x in msgs_to_send.keys():
                    dev.send(msgs_to_send[x])
                    del msgs_to_send[x]
                    count_outstanding += 1
                    if count_outstanding >= outstanding_max:
                        break

                # handle acks (if any)
                got_ack = False
                while True:
                    msg = dev.receive_message()
                    print("msg: %s" % str(msg))
                    if msg.msg_type() != (ublox.CLASS_MGA, ublox.MSG_MGA_ACK):
                        break
                    got_ack = True
                    gnss = msg.msgPayloadStart[3]
                    svid = msg.msgPayloadStart[2]
                    acked_by_sv[(gnss,svid)] = 1
                    count_outstanding -= 1
                    # because we can only do blocking reads for
                    # messages, we break here rather than handling
                    # multiple messages.  Otherwise we have to wait
                    # for a non-mga-ack message to come in, and that
                    # could never happen ('though it happens at 1Hz in
                    # my testing here)
                    break
                if not got_ack:
                    print("No ack")
                    time.sleep(0.1)
