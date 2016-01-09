from twisted.conch import manhole, manhole_ssh
from twisted.cred import portal, checkers

import cyclone.escape
import cyclone.redis
import cyclone.sqlite
import cyclone.util
import cyclone.web
import cyclone.websocket
import cyclone.xmlrpc
from cyclone.bottle import create_app, route
from twisted.spread import pb
from twisted.internet import reactor

import traceback

class Client:
    def __init__(self, e, q, ref):
        self.e = e
        self.q = q
        self.ref = ref

    def ping(self,x):
        pass
        #print "Ping %s" % str(x)

    def err(self, *args):
        print "Err is ", str(args)
        del self.e.clients[self.q]

def dorint(s):
    print s

from datetime import datetime

class Echoer(pb.Root):
    def __init__(self):
        self.clients = {}
        self.webSockets = []

    def pingClients(self):
        print "PingClients"
        for q,v in self.clients.items():
            s =  "%s Pinging %s %s %s" % (datetime.now().isoformat(),q,v, str(self.webSockets))
            print s
            for ws in self.webSockets:
                ws.sendMessage(s)
            try:
                v.ref.callRemote('ping' ,s).addCallback( v.ping).addErrback(v.err)
            except pb.DeadReferenceError:
                traceback.print_exc()
                print "Killing %s" % q
                del self.clients[q]
                pass
        reactor.callLater(1, self.pingClients)

    def remote_register(self, name, client):
        print "Beep %s %s" % (name, client)
        c = Client(self, name, client)
        self.clients[name] = c
    
    def remote_echo(self, st, ref):
        print 'echoing:', st, ref
        x = ref.callRemote('beep', "Woot")
        def beep(x):
            print "Echo ", x

        x.addCallback( beep)
        return (st, self)
    
# TODO - something like this.
# https://gist.github.com/ismasan/299789

htm = open('resources/websock.htm', 'r').read()
websockjs = open('resources/websock.js', 'r').read()

print "Loaded %s" % htm

class BaseHandler(cyclone.web.RequestHandler):
    @property
    def redisdb(self):
        return self.settings.db_handlers.redis

    def get_current_user(self):
        print "Getting user cookie"
        return self.get_secure_cookie("user")

@route("/")
def index(web):
    web.write("Hello, world")

@route("/resources/websock.js")
def index(web):
    web.write(websockjs)
    
@route("/demo")
def index(web):
    print "Returning %s" % htm
    web.write(htm)

from pprint import pprint as pp
import json
    
@route("/jobs/add", method = 'post') 
def index(web, *args, **kwargs):
    #print web, args, kwargs
    #pp(vars(web))
    pp( json.loads(web.request.body))
    #pp(vars(web))
    web.write('Ok')

class WebSocketHandler(cyclone.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        cyclone.websocket.WebSocketHandler.__init__(self, *args, **kwargs)
        print "Created with %s %s" % (args, kwargs)
        self.connected = False
    
    def connectionMade(self, *args, **kwargs):
        print "connection made:", args, kwargs
        self.connected = True

    def messageReceived(self, message):
        self.sendMessage("echo: %s" % message)

    def doSend(self, x):
        if self.connected:
            self.sendMessage(x)

    def connectionLost(self, why):
        print "connection lost:", why
        self.connected = False

def webSocket(*args, **kwargs):
    print "Woot"
    ret = WebSocketHandler(*args, **kwargs)
    e.webSockets.append(ret)
    return ret

try:
    raise Exception("COMMENT_THIS_LINE_AND_LOG_TO_DAILY_FILE")
    from twisted.python.logfile import DailyLogFile
    logFile = DailyLogFile.fromFullPath("server.log")
    print("Logging to daily log file: server.log")
except Exception, e:
    import sys
    logFile = sys.stdout

def getManholeFactory(namespace, passwords):
    realm = manhole_ssh.TerminalRealm()
    def getManhole(_): return manhole.Manhole(namespace)
    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)
    return f
    
if __name__ == '__main__':
    e = Echoer()
    reactor.listenTCP(9011, pb.PBServerFactory(e))
    reactor.listenTCP(8790, getManholeFactory(globals(), passwords = { 'andy' : 'pandy' }))
    settings = dict(
        more_handlers=[
            #(r"/websocket", WebSocketHandler),
            (r"/websocket", webSocket),
            #(r"/xmlrpc",    XmlrpcHandler),
        ] )
    
    port = 8888
    interface = '0.0.0.0'
    reactor.listenTCP(port, create_app( **settings ), interface=interface)
    reactor.callLater(0, e.pingClients)
    reactor.run()
