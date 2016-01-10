import sys
sys.path.insert(0, '/home/andy/repos/cyclone')

from twisted.conch import manhole, manhole_ssh
from twisted.cred import portal, checkers

import cyclone
print cyclone.__file__

import cyclone.escape
import cyclone.redis
import cyclone.sqlite
import cyclone.util
import cyclone.web
import cyclone.websocket
import cyclone.xmlrpc
from   cyclone.bottle import create_app, route
from   twisted.spread import pb
from   twisted.internet import reactor
from   twisted.python import log
import traceback
import json

class Client:
    def __init__(self, e, name, ref):
        self.e = e
        self.name = name
        self.ref = ref

    def ping(self,x):
        pass
        #print "Ping %s" % str(x)

    def err(self, *args):
        print "Err is ", str(args)
        del self.e.clients[self.name]

def dorint(s):
    print s

from datetime import datetime

class Echoer(pb.Root):
    def __init__(self):
        self.clients = {}
        self.webSockets = []

    def wsSuccess(self, ws):
        print "Success %s"

    def wsFailed( self, ws):
        print "WS Failed %s" % ws
        
    def pingClients(self):
        print "PingClients"
        for ws in self.webSockets:
            x = ws.sendMessage( json.dumps(
                {
                    "type" : "serverInfo" ,
                    "peers"   : [ x.name for x in self.clients.values() ],
                    "clients" : [ x.id for x in self.webSockets],
                    "time"    : datetime.now().isoformat()
                }
            ))
            #print "Retval is %s" % x
        for q,v in self.clients.items():
            s =  "%s Pinging %s %s %s" % (datetime.now().isoformat(),q,v, str(self.webSockets))
            print s
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
        x.addCallback( beep )
        return (st, self)
    
# TODO - something like this.
# https://gist.github.com/ismasan/299789
class BaseHandler(cyclone.web.RequestHandler):
    @property
    def redisdb(self):
        return self.settings.db_handlers.redis

    def get_current_user(self):
        print "Getting user cookie"
        return self.get_secure_cookie("user")

@route("/jobs/add", method = 'post') 
def addJob(web, *args, **kwargs):
    #print web, args, kwargs
    #pp(vars(web))
    pp( json.loads(web.request.body))
    #pp(vars(web))
    web.write('Ok')

from pprint import pprint as pp
    
class WebSocketHandler(cyclone.websocket.WebSocketHandler):
    def onLogonRequest(self, j):
        self.id = j['id']
        self.server.webSockets.append(self)
        self.dispatchMap = self.normalDispatch
        print "Accepted logon for client %s" % self.id
    
    def initialize(self, server):
        print "Start initialise"
        self.awaitingLogon  = { "logon" : self.onLogonRequest }
        self.normalDispatch = { }
        print "In initialize"
        self.connected = False
        self.id = None
        self.dispatch = self.awaitingLogon
        self.server = server
        print "End initialise"
        
    def connectionMade(self, *args, **kwargs):
        print "connection made:", args, kwargs
        self.connected = True

    def messageReceived(self, message):
        print "Received %s" % message
        try:
            xs = json.loads(message)
            thaip = xs['type']
            if self.dispatch.has_key(thaip):
                self.dispatch[thaip](xs)
            else:
                print "Danger out of bound type %s\n%s" % (thaip, xs)
        except:
            print "Expunge server"
            if self in self.server.webSockets:
                self.server.webSockets.remove(self)
            
    # def doSend(self, x):
    #     if self.connected:
    #         self.sendMessage(x)

    def connectionLost(self, why):
        print "connection lost:", why
        self.connected = False
        if self in self.server.webSockets:
            print "Deregistering from server"
            self.server.webSockets.remove(self) # TODO - method on server?

def webSocket(*args, **kwargs):
    print "Woot %s %s" % (str(args), str(kwargs))
    ret = WebSocketHandler(*args, **kwargs)
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
    
    log.startLogging(sys.stdout)
    settings = dict(
        log = logFile,
        more_handlers=[
            (r"/websocket"  , webSocket, { 'server' : e }),
            (r"/static/(.*)", cyclone.web.StaticFileHandler , { "path" : "static" }),
            (r"/demo"       , cyclone.web.RedirectHandler  , { "url"  : "static/websock.htm"})
        ] )
    
    port = 8888
    interface = '0.0.0.0'
    reactor.listenTCP(port, create_app( **settings ), interface=interface)
    reactor.callLater(0, e.pingClients)
    reactor.run()
