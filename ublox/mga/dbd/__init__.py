import ublox

class DBD(object):
    def __init__(self):
        self.state_download_messages = 2
        self.state_download_done = 3

        self.state_upload_sending_message = 1
        self.state_upload_waiting_for_ack = 2
        self.state_upload_done = 3

        self.last_dbd_config_message_sent = 0;
        self.messages = []
        pass

    def dbd_poll(self):
        now = time.time()
        if (self.last_dbd_config_message_sent == 0 or
            now - self.last_dbd_config_message_sent > 2):
            self.dev.configure_poll(ublox.CLASS_MGA, ublox.MSG_MGA_DBD)
            self.last_dbd_config_message_sent = now

    def download_mga_dbd(self):
        self.state_download = self.state_download_messages
        while self.state_download != self.state_download_done:
            msg = self.dev.receive_message()
            if msg is None:
                print("No message")
                self.dbd_poll()
                time.sleep(0.1)
                continue
            print("msg=%s" % msg);
            if self.state_download == self.state_download_messages:
                if msg.msg_type() == (ublox.CLASS_MGA, ublox.MSG_MGA_DBD):
                    self.messages.append(msg)
                    continue
                if msg.msg_type() == (ublox.CLASS_MGA, ublox.MSG_MGA_ACK):
                    print("Received final ack (%s)" % str(msg))
                    count = (msg.msgPayloadStart[0] +
                             (msg.msgPayloadStart[1] << 8) +
                             (msg.msgPayloadStart[2] << 16) +
                             (msg.msgPayloadStart[3] << 24))
                    if len(self.messages) != count:
                        print("ACK: my-count=%u  ack-count=%u; retrying" % (self.len(self.messages), count))
                        self.messages = []
                    else:
                        self.state_download = self.state_download_done
                    continue
                if len(self.messages) == 0:
                    self.dbd_poll()

    def write_messages_to_filepath(self, filepath):
        fh = open(filepath, "w")
        for message in self.messages:
            fh.write(message.raw())
        fh.close()

    def messages_fh(self):
        ret = StringIO.StringIO()
        for message in self.messages:
            ret.write(message.raw)
        ret.seek(0)
        return ret

    def upload_mga_dbd(self, source_dev):
        msg_to_send = source_dev.receive_message()
        self.state_upload = self.state_upload_sending_message

        msg_sent = None
        while self.state_upload != self.state_upload_done:
            if self.state_upload == self.state_upload_sending_message:
                if msg_to_send is None:
                    print("No more messages")
                    self.state_upload = self.state_upload_done
                    continue
                print("Sending message (%s)" % str(msg_to_send))
                self.dev.send(msg_to_send)
                self.state_upload = self.state_upload_waiting_for_ack
                continue
            if self.state_upload == self.state_upload_waiting_for_ack:
                if time.time()-msg_sent > 5:
                    print("Resending")
                    state = self.state_upload_sending_message
                    continue
                msg = self.dev.receive_message()
                if msg is None:
                    print("No message")
                    time.sleep(0.1)
                    continue
                if msg.msg_type() == (ublox.CLASS_MGA, ublox.MSG_MGA_ACK):
                    # TODO: check ack of appropriate message!
                    print("Got ack (%s)" % str(msg))
                    if (msg.msgId == ublox.MSG_MGA_ANO):
                        print("Got correct ack (%s)" % str(msg))
                        if msg.infoCode == 0:
                            print("message accepted" % str(msg))
                            self.state_upload = self.state_upload_sending_message
                            msg_to_send = source_dev.receive_message()
                    continue
                print("msg: %s" % (str(msg)))

#     def run(self):
#         from optparse import OptionParser

#         parser = OptionParser("mga.py upload|download FILEPATH")
#         parser.add_option("--port", help="serial port", default='/dev/ttyACM0')
#         parser.add_option("--baudrate", type='int',
#                           help="serial baud rate", default=115200)
#         parser.epilog = "upload: upload to device\ndownload: download from device"
#         (opts, args) = parser.parse_args()
#         if len(args) != 2:
#             print(parser.usage)
#             sys.exit(1)
#         self.direction = args[0]
#         if self.direction != "upload" and self.direction != "download":
#             print(parser.usage)
#             sys.exit(1)
#         self.filepath = args[1]

#         self.dev = ublox.UBlox(opts.port, baudrate=opts.baudrate, timeout=2)
#         self.configure_dev()

#         # request Multiple GNSS AssistNow DataBaseDump
#         if self.direction == "download":
#             self.download_mga_dbd()
#             print("Downloaded %u messages" % len(self.messages))
#             self.write_messages_to_filepath(self.filepath)
#         elif self.direction == "upload":
#             fh = open(self.filepath, "r")
#             fh_dev = ublox.UBlox(fh)
#             self.upload_mga_dbd(fh_dev)

# if __name__ == "__main__":
#     mga_dbd = MGA_DBD()
#     mga_dbd.run()
