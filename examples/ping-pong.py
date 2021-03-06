## Copyright (c) 2010, Coptix, Inc.  All rights reserved.
## See the LICENSE file for license terms and warranty disclaimer.

"""ping-pong -- a ping/pong client and server

The example demonstrates how to write a basic Plugin (PingPong) that
can be combined with other plugins (Client or Server) to create an
Application.

A Plugin handles incoming stanzas, manages state, triggers Events that
can be subscribed to by other Plugins, and probably writes stanzas in
reply.  There can only be one handler for each stanza in an
Application, but many listeners for each Event.

A good way to design a Plugin is to:

  1. Watch for stanzas

  2. When a stanza arrives, update state and trigger an Event.

  3. When the Event has been handled, check for changes listeners
     might have made to the state and act accordingly.

  4. Provide methods for creating stanzas and writing them to the
     stream.

There's also an example of a fake "stream" that simply passes data
between Application instances.  This can be used to test Application
interaction without using sockets.
"""

import os, time, xmpp


### PingPong "plugin"

class ReceivedPong(xmpp.Event): pass
class ReceivedPing(xmpp.Event): pass

class PingPong(xmpp.Plugin):

    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True
        return self

    @xmpp.stanza
    def ping(self, elem):
        self.trigger(ReceivedPing)
        if self.stopped:
            return self.close()
        return self.send_pong()

    @xmpp.stanza
    def pong(self, elem):
        self.trigger(ReceivedPong)
        if self.stopped:
            return self.close()
        return self.send_ping()

    def send_ping(self):
        return self.write(self.E('ping'))

    def send_pong(self):
        return self.write(self.E('pong'))

class Client(xmpp.Plugin):

    PONG_LIMIT = 2

    def __init__(self):
        self.pongs = 0
        self.plugin(PingPong).send_ping()

    @xmpp.bind(ReceivedPong)
    def on_pong(self, pingpong):
        self.pongs += 1
        if self.pongs > self.PONG_LIMIT:
            pingpong.stop()


### Fake Stream

class Stream(object):
    SCHEDULE = []

    @classmethod
    def loop(cls):
        while cls.SCHEDULE:
            (callback, data, done) = cls.SCHEDULE[0]
            del cls.SCHEDULE[0]
            if callback:
                callback(data)
                done and done()
            elif isinstance(data, float) and data < time.time():
                if cls.SCHEDULE:
                    cls.SCHEDULE.append((callback, data, done))
                else:
                    done and done()
            else:
                done and done()

    class IO(object):
        def add_timeout(self, when, callback):
            Stream.SCHEDULE.append((None, time.time(), callback))

    def __init__(self, name, app, dest):
        self.name = name
        self.dest = dest
        self.reader = None
        self.closed = None
        self.socket = None
        self.io = self.IO()

        print '%s: OPEN' % self.name
        self.target = app.Core(self, **app.settings)

    def read(self, callback):
        self.reader = callback
        return self

    def shutdown(self, callback=None):
        self.on_close(callback)
        self.SCHEDULE.append((None, None, self.close))

    def on_close(self, callback):
        self.closed = callback

    def write(self, data, callback=None):
        print '%s:' % self.name, data
        if self.dest:
            self.SCHEDULE.append((self.dest, data, callback))
        return self

    def close(self):
        print '%s: CLOSED' % self.name
        self.closed and self.closed()

if __name__ == '__main__':
    client = xmpp.Client({
        'plugins': [PingPong, Client],
        'host': 'example.net',
        'username': 'user@example.net',
        'password': 'secret'
    })

    server = xmpp.Server({
        'plugins': [PingPong],
        'host': 'example.net',
        'users': { 'user@example.net': 'secret' },
        'certfile': os.path.join(os.path.dirname(__file__), 'certs/self.crt'),
        'keyfile': os.path.join(os.path.dirname(__file__), 'certs/self.key')
    })

    CP = Stream('C', client, lambda d: SP.reader(d))
    SP = Stream('S', server, lambda d: CP.reader(d))
    Stream.loop()

    # SP = xmpp.TCPServer(server).bind('127.0.0.1', '9000')
    # CP = xmpp.TCPClient(client).connect('127.0.0.1', '9000')
    # xmpp.start([SP, CP])

