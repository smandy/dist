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

    def err(self, err):
        print "Err is ", err
        #print "Removing client %s" % self.q
        del self.e.clients[self.q]

def dorint(s):
    print s
        
class Echoer(pb.Root):
    def __init__(self):
        self.clients = {}
        self.webSocket = None
        #reactor.callLater(1000, self.pingClients)

    def pingClients(self):
        print "PingClients"
        for q,v in self.clients.items():
            print "Pinging %s %s" % (q,v)
            if self.webSocket:
                self.webSocket.sendMessage("Pinging %s %s" % (q,v))
                
            try:
                v.ref.callRemote('ping').addCallback( v.ping).addErrback(v.err)
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

htm = """<html>
    <head>
        <title>Echo Chamber</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width">
    </head>
    <body>
        
        <div>
            <input type="text" id="messageinput"/>
        </div>
        <div>
            <button type="button" onclick="openSocket();" >Open</button>
            <button type="button" onclick="send();" >Send</button>
            <button type="button" onclick="closeSocket();" >Close</button>
        </div>
        <!-- Server responses get written here -->
        <div id="messages"></div>
        
        <!-- Script to utilise the WebSocket -->
        <script type="text/javascript">
                        
            var webSocket;
            var messages = document.getElementById("messages");
            
            
            function openSocket(){
                // Ensures only one connection is open at a time
                if(webSocket !== undefined && webSocket.readyState !== WebSocket.CLOSED){
                    writeResponse("WebSocket is already opened.");
                    return;
                }
                // Create a new instance of the websocket
                webSocket = new WebSocket("ws://localhost:8888/websocket");
                 
                /**
                 * Binds functions to the listeners for the websocket.
                 */
                webSocket.onopen = function(event){
                    // For reasons I can't determine, onopen gets called twice
                    // and the first time event.data is undefined.
                    // Leave a comment if you know the answer.
                    if(event.data === undefined) 
                        return;

                    writeResponse(event.data);
                };

                webSocket.onmessage = function(event){
                    writeResponse(event.data);
                };

                webSocket.onclose = function(event){
                    writeResponse("Connection closed");
                };
            }
            
            /**
             * Sends the value of the text input to the server
             */
            function send(){
                var text = document.getElementById("messageinput").value;
                webSocket.send(text);
            }
            
            function closeSocket(){
                webSocket.close();
            }

            function writeResponse(text){
                messages.innerHTML = text + "<br/>" + messages.innerHTML;
            }
            
        </script>
        
    </body>
</html>"""

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

@route("/demo")
def index(web):
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
    e.webSocket = ret
    return ret

class XmlrpcHandler(cyclone.xmlrpc.XmlrpcRequestHandler):
    allowNone = True
    
    def xmlrpc_echo(self, text):
        return text

try:
    raise Exception("COMMENT_THIS_LINE_AND_LOG_TO_DAILY_FILE")
    from twisted.python.logfile import DailyLogFile
    logFile = DailyLogFile.fromFullPath("server.log")
    print("Logging to daily log file: server.log")
except Exception, e:
    import sys
    logFile = sys.stdout

#reactor.run()

def getManholeFactory(namespace, passwords):
    realm = manhole_ssh.TerminalRealm()
    def getManhole(_): return manhole.Manhole(namespace)
    realm.chainedProtocolFactory.protocolFactory = getManhole
    p = portal.Portal(realm)
    p.registerChecker(
        checkers.InMemoryUsernamePasswordDatabaseDontUse(**passwords))
    f = manhole_ssh.ConchFactory(p)
    return f
    
if __name__ == '__main__':
    e = Echoer()
    reactor.listenTCP(8789, pb.PBServerFactory(e))
    reactor.listenTCP(8790, getManholeFactory(globals(), passwords = { 'andy' : 'pandy' }))
    settings = dict(
        more_handlers=[
            #(r"/websocket", WebSocketHandler),
            (r"/websocket", webSocket),
            (r"/xmlrpc",    XmlrpcHandler),
        ] )
    
    port = 8888
    interface = '0.0.0.0'
    reactor.listenTCP(port, create_app( **settings ), interface=interface)

    
    #x = pb.getRootObject()
    reactor.callLater(0, e.pingClients)
    reactor.run()
