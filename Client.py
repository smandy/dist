# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.spread import pb
from twisted.internet import reactor
#from twisted.python import util

class Client(pb.Root, pb.Referenceable):
    def __init__(self, name):
        self.name = name
        
    def remote_ping(self, *args):
        #print "Ping!"
        pass
    
factory = pb.PBClientFactory()

reactor.connectTCP("localhost", 9011, factory)
d = factory.getRootObject()

import sys
clients = [ Client(x) for x in sys.argv[1:] ]

def success(*args):
    print "Successs %s" % str(args)

def fail(*args):
    print "Fail %s" % str(args)

def getConnected(server):
    print "GetConnected"
    for c in clients:
        server.callRemote( 'register', c.name, c).addCallback(success).addErrback(fail)
        
d.addCallback(getConnected)
#d.addCallback(lambda s: 'server echoed: '+str(s))
#d.addCallback(lambda s: 'server echoed2: '+str(s))
d.addErrback(lambda reason: 'error: '+str(reason.value))
#d.addCallback(util.println)
#d.addCallback(lambda _: reactor.stop())
reactor.run()
