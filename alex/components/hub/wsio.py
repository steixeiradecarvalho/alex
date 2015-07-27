#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jinja2.loaders import FileSystemLoader
from jinja2 import Environment

import wave
import multiprocessing
import sys
import os.path
from datetime import datetime
import urlparse
import Queue
import BaseHTTPServer
import threading
import time

from alex.utils.audio import load_wav
import alex.utils.various as various

from alex.components.hub.messages import Command, Frame


class WSIO(multiprocessing.Process):
    """
    WebSocket IO.
    """

    def __init__(self, cfg, commands, audio_record, audio_play, close_event):
        """ Initialize WebIO

        cfg - configuration dictionary

        audio_record - inter-process connection for sending recorded audio.
          Audio is divided into frames, each with the length of samples_per_frame.

        audio_play - inter-process connection for receiving audio which should to be played.
          Audio must be divided into frames, each with the length of samples_per_frame.

        """

        multiprocessing.Process.__init__(self)

        self.cfg = cfg
        self.commands = commands
        self.audio_record = audio_record
        self.audio_play = audio_play
        self.close_event = close_event

    def process_pending_commands(self):
        """Process all pending commands.

        Available commands:
          stop() - stop processing and exit the process
          flush() - flush input buffers.
            Now it only flushes the input connection.
            It is not able flush data already send to the sound card.

        Return True if the process should terminate.
        """

        # TO-DO: I could use stream.abort() function to flush output buffers of pyaudio()

        if self.commands.poll():
            command = self.commands.recv()
            if self.cfg['AudioIO']['debug']:
                self.cfg['Logging']['system_logger'].debug(command)

            if isinstance(command, Command):
                if command.parsed['__name__'] == 'stop':
                    # discard all data in play buffer
                    while self.audio_play.poll():
                        self.audio_play.recv()

                    return True

                if command.parsed['__name__'] == 'flush':
                    # discard all data in play buffer
                    while self.audio_play.poll():
                        self.audio_play.recv()

                    return False

        return False

    def read_write_audio(self): #, p, stream, wf, play_buffer):
        """Send some of the available data to the output.
        It should be a non-blocking operation.

        Therefore:
          1) do not send more then play_buffer_frames
          2) send only if stream.get_write_available() is more then the frame size
        """
        if self.audio_play.poll():
            while self.audio_play.poll(): # \
                #and len(play_buffer) < self.cfg['AudioIO']['play_buffer_size']:

                # send to play frames from input
                data_play = self.audio_play.recv()
                if isinstance(data_play, Frame):
                    msg = AlexToClient()
                    msg.speech.body = data_play.payload
                    self.ws_conn.send(self.ws_protocol, msg.SerializeToString())

                #if isinstance(data_play, Frame):
                #    stream.write(data_play.payload)
                #
                #    play_buffer.append(data_play)
                #
                #    if self.cfg['AudioIO']['debug']:
                #        print '.',
                #        sys.stdout.flush()

                #elif isinstance(data_play, Command):
                #    if data_play.parsed['__name__'] == 'utterance_start':
                #        self.commands.send(Command('play_utterance_start()', 'AudioIO', 'HUB'))
                #    if data_play.parsed['__name__'] == 'utterance_end':
                #        self.commands.send(Command('play_utterance_end()', 'AudioIO', 'HUB'))

    def run(self):
        try:
            self.cfg['Logging']['session_logger'].cancel_join_thread()

            global logger
            logger = self.cfg['Logging']['system_logger']

            #factory = WebSocketServerFactory("ws://0.0.0.0:9000", debug=False)
            #factory.protocol = create_alex_websocket_protocol(self)

            #def run_ws():
            #    print 'running ws'
            #    reactor.listenTCP(9000, factory)
            #    reactor.run(installSignalHandlers=0)

            #t = Thread(target=run_ws) #lambda *args: run_ws())
            #t.setDaemon(True)
            #print 'starting thread'
            #t.start()
            self.ws_conn = Connection(self)
            self.ws_conn.daemon = True
            self.ws_conn.start()

            # process incoming audio play and send requests
            while 1:
                time.sleep(1)
                # Check the close event.
                if self.close_event.is_set():
                    return

                #import ipdb; ipdb.set_trace()

                # process all pending commands
                if self.process_pending_commands():
                    return

                print '.'

                # process each web request
                #while not self.web_queue.empty():
                #    for filename in self.web_queue.get():
                #        try:
                #            self.send_wav(filename, stream)
                #        except:
                #            self.cfg['Logging']['system_logger'].exception(
                #                'Error processing file: ' + filename)

                ## process audio data
                self.read_write_audio() #p, stream, wf, play_buffer)
        except:
            self.cfg['Logging']['system_logger'].exception('Uncaught exception in VAD process.')
            self.close_event.set()
            raise

    def on_client_connected(self, protocol, request):
        self.commands.send(Command('client_connected()', 'WSIO', 'HUB'))
        self.ws_protocol = protocol

from twisted.internet import reactor
from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

#from wshub_messages_pb2
from wsio_messages_pb2 import ClientToAlex, AlexToClient


class Connection(threading.Thread):
    def __init__(self, hub_instance):
        super(Connection, self).__init__()
        self.factory=WebSocketServerFactory("ws://localhost:9000", debug=True)
        self.hub_instance = hub_instance

    def run(self):
        self.factory.protocol = create_ws_protocol(self.hub_instance)
        reactor.listenTCP(9000, self.factory)
        reactor.run(installSignalHandlers=0)

    def send(self, proto, data):
        reactor.callFromThread(proto.sendMessage, data, True)




def create_ws_protocol(hub):
    class AlexWebsocketProtocol(WebSocketServerProtocol):
        hub_instance = hub

        def onConnect(self, request):
            print self.factory, id(self)
            print("Client connecting: {0}".format(request.peer))
            self.hub_instance.on_client_connected(self, request)

        def onOpen(self):
            print("WebSocket connection open.")

        def onMessage(self, payload, isBinary):
            if isBinary:
                msg = ClientToAlex()
                msg.ParseFromString(payload)
                self.hub_instance.audio_record.send(Frame(msg.speech.body))


        def onClose(self, wasClean, code, reason):
            print("WebSocket connection closed: {0}".format(reason))

    return AlexWebsocketProtocol


