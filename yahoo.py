#! /usr/bin/env python

# Yahoo Transport June 2004
from xmpp import *
from xmpp.protocol import *
from xmpp.simplexml import Node
from curphoo import cpformat
import ConfigParser, time, select, shelve, ylib, os, roomlist, sha, base64
from toolbox import *
#import dummy_threading as _threading

VERSTR = 'XMPPPY Yahoo! Transport (Dev)'

NS_MUC = 'http://jabber.org/protocol/muc'
NS_MUC_USER = NS_MUC+'#user'
NS_MUC_ADMIN = NS_MUC+'#admin'
NS_MUC_OWNER = NS_MUC+'#owner'
rdsocketlist = {}
wrsocketlist = {}
userlist = {}
#each item is a tuple of 4 values, 0 == frequency in seconds, 1 == offset from 0, 2 == function, 3 == arguments
timerlist = []

# colour parsing re: re.sub('\x1b\[([0-9]+)])m','<asci colour=\\1>',string)

def connectxmpp():
    global connection
    connection = client.Component(hostname,port)
    try: connection.auth(hostname,secret)
    except: pass
    connection.connect((server,port))
    while 1:
        time.sleep(5)
        connected=connection.reconnectAndReauth()
        if connected: break
    connection.UnregisterDisconnectHandler(connection.DisconnectHandler)
    return connected
    
class Transport:
    def __init__(self,jabber):
        self.jabber = jabber
        self.register_handlers()
        self.chatcat = {0:(0,{})}
        self.catlist = {}
    
    def jabberqueue(self,packet):
        if not wrsocketlist.has_key(self.jabber.Connection._sock):
            wrsocketlist[self.jabber.Connection._sock]=[]
        wrsocketlist[self.jabber.Connection._sock].append(packet)
    
    def yahooqueue(self,fromjid,packet):
        if packet != None:
            s = userlist[fromjid].sock
            if not wrsocketlist.has_key(s):
                wrsocketlist[s]=[]
            wrsocketlist[s].append(packet)

    def findbadconn(self):
        #print rdsocketlist
        for each in userlist:
            print each, userlist[each].sock.fileno()
            if userlist[each].sock.fileno() == -1:
                #print each, userlist[each].sock.fileno()
                self.y_closed(userlist[each])
            else:
                try:
                    a,b,c = select.select([userlist[each].sock],[userlist[each].sock],[userlist[each].sock],0)
                except:
                    self.y_closed(userlist[each])
        badlist = []
        for each in wrsocketlist.keys():
            if each.fileno() == -1:
                badlist.append(each)
        for each in badlist:
            del wrsocketlist[each]
        return
    
    def register_handlers(self):
        self.jabber.RegisterHandler('message',self.xmpp_message)
        self.jabber.RegisterHandler('presence',self.xmpp_presence)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_discoinfo,typ = 'get', ns=NS_DISCO_INFO)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_discoitems,typ = 'get', ns=NS_DISCO_ITEMS)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_version,typ = 'get', ns=NS_VERSION)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_agents,typ = 'get', ns=NS_AGENTS)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_browse,typ = 'get', ns=NS_BROWSE)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_register_get, typ = 'get', ns=NS_REGISTER)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_register_set, typ = 'set', ns=NS_REGISTER)
        self.jabber.RegisterHandler('iq',self.xmpp_iq_avatar, typ = 'get', ns='jabber:iq:avatar')
        #self.jabber.RegisterHandler('iq',self.xmpp_iq_notimplemented)
        #self.jabber.RegisterHandler('iq',self.xmpp_iq_mucadmin_set,typ = 'set', ns=NS_MUC_ADMIN)
        #self.jabber.RegisterHandler('iq',self.xmpp_iq_mucadmin_get,typ = 'get', ns=NS_MUC_ADMIN)
    
    def register_ymsg_handlers(self, con):
        con.handlers['online']= self.y_online
        con.handlers['offline']= self.y_offline
        con.handlers['chatonline']= self.y_chatonline
        con.handlers['chatoffline']= self.y_chatoffline
        con.handlers['login'] = self.y_login
        con.handlers['logout'] = self.y_loginfail
        con.handlers['subscribe'] = self.y_subscribe
        con.handlers['message'] = self.y_message
        con.handlers['messagefail'] = self.y_messagefail
        con.handlers['chatmessage'] = self.y_chatmessage
        con.handlers['ping'] = self.y_ping
        con.handlers['calendar'] = self.y_calendar
        con.handlers['email'] = self.y_email
        con.handlers['closed'] = self.y_closed
        con.handlers['avatar'] = self.y_avatar
        #chatroom handlers
        con.handlers['reqroom'] = self.y_chat_login
        con.handlers['roominfo'] = self.y_chat_roominfo
        con.handlers['chatjoin'] = self.y_chat_join
        con.handlers['chatleave'] = self.y_chat_leave
        con.handlers['roommessage'] = self.y_roommessage
        #con.handlers['roommessagefail'] = self.y_roommessagefail
        
        
    def xmpp_message(self, con, event):
        resource = 'messenger'
        fromjid = event.getFrom()
        fromstripped = fromjid.getStripped().encode('utf8')
        if event.getBody() == None:
            return
        if event.getTo().getNode() != None:
            if userlist.has_key(fromstripped):
                if event.getTo().getDomain() == hostname:
##                    if event.getTo().getResource() == None or event.getTo().getResource() == '':
##                        #print "no resource", userlist[fromstripped].resources
##                        if userlist[fromstripped].resources.has_key(event.getTo().getNode()):
##                            if 'messenger' in userlist[fromstripped].resources[event.getTo().getNode()]:
##                                resource= 'messenger'
##                            elif 'chat' in userlist[fromstripped].resources[event.getTo().getNode()]:
##                                resource = 'chat'
##                    elif event.getTo().getResource() == 'chat':
##                        resource = 'chat'
##                    elif event.getTo().getResource() == 'messenger':
##                        resource = 'messenger'
##                    else:
##                        resource = 'messenger'
                    resource = 'messenger'
                        # normal non-groupchat or conference cases
                    if resource == 'messenger':
                        if event.getType() == None or event.getType() =='normal':
                            # normal message case
                            #print 'got message'
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_message(event.getTo().getNode().encode('utf-8'),event.getBody().encode('utf-8')))
                        elif event.getType() == 'chat':
                            # normal chat case
                            #print 'got message'
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_message(event.getTo().getNode().encode('utf-8'),event.getBody().encode('utf-8')))
                        else:
                            #print 'type error'
                            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
                    elif resource == 'chat':
                        if event.getType() == None or event.getType() =='normal':
                            # normal message case
                            #print 'got message'
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatmessage(event.getTo().getNode().encode('utf-8'),event.getBody().encode('utf-8')))
                        elif event.getType() == 'chat':
                            # normal chat case
                            #print 'got message'
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatmessage(event.getTo().getNode().encode('utf-8'),event.getBody().encode('utf-8')))
                        else:
                            #print 'type error'
                            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
                    else:
                        #print 'resource error'
                        self.jabberqueue(Error(event,ERR_BAD_REQUEST))
                elif event.getTo().getDomain() == chathostname:
                    if event.getSubject():
                        self.jabberqueue(Error(event,ERR_NOT_IMPLEMENTED))
                        return
                    if event.getTo().getResource() == None or event.getTo().getResource() == '':
                        print userlist[fromstripped].roomlist, userlist[fromstripped].roomnames
                        if userlist[fromstripped].roomlist.has_key(event.getTo().getNode().encode('utf-8').decode('base64')):
                            room = event.getTo().getNode().encode('utf-8').decode('base64')
                        elif userlist[fromstripped].roomnames.has_key(event.getTo().getNode()):
                            room = userlist[fromstripped].roomnames[event.getTo().getNode()].encode('utf-8')
                        else:
                            room = None
                        print "groupchat room: ",room
                        if room != None:
                            if event.getBody()[0:3] == '/me':
                                type = 2
                                body = event.getBody()[4:].encode('utf-8')
                            else:
                                type = 1
                                body = event.getBody().encode('utf-8')
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_roommsg(room,body,type))
                            to = '%s/%s'%(event.getTo(),userlist[fromstripped].username)
                            self.jabberqueue(Message(to=event.getFrom(), frm= to, typ='groupchat',body=event.getBody()))
                        else:
                            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
            else:
                print 'no item error'
                self.jabberqueue(Error(event,ERR_REGISTRATION_REQUIRED))
        else:
            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
    
    
    def xmpp_presence(self, con, event):
        yobj = None
        yrost = None
        fromjid = event.getFrom()
        fromstripped = fromjid.getStripped().encode('utf8')
        if userfile.has_key(fromstripped):
            if event.getTo().getDomain() == hostname:
                if event.getType() == 'subscribed': 
                    if userlist.has_key(fromstripped):
                        if event.getTo() == hostname:   
                            conf = userfile[fromstripped]
                            conf['subscribed']=True
                            userfile[fromstripped]=conf
                            m = Message(to = fromjid, frm = hostname, subject= 'Yahoo Roster Items', body = 'Items from Yahoo Roster')
                            p=None
                            p= m.setTag('x',namespace = 'jabber:x:roster')
                            yrost = userlist[fromstripped].buddylist
                            print yrost
                            for each in yrost.keys():
                                for i in yrost[each]:
                                    p.addChild(name='item', attrs={'jid':'%s@%s'%(i,hostname),'name':i},payload=[Node('group',payload=each)])
                            self.jabberqueue(m)
                            print m
                            m = Presence(to = fromjid, frm = hostname)
                            self.jabberqueue(m)
                            self.y_send_online(fromstripped)
                            self.register_ymsg_handlers(userlist[fromstripped])
                    else:
                        self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
                elif event.getType() == 'subscribe':
                    if userlist.has_key(fromstripped):
                        if event.getTo() == hostname:
                            conf = userfile[fromstripped]
                            conf['usubscribed']=True
                            userfile[fromstripped]=conf
                            m = Presence(to = fromjid, frm = hostname, typ = 'subscribed')
                            self.jabberqueue(m)
                        elif userlist[fromstripped].roster.has_key(event.getTo().getNode().encode('utf-8')):
                            m = Presence(to = fromjid, frm = event.getTo(), typ = 'subscribed')
                            self.jabberqueue(m)
                        else:
                            #add new user case.
                            if event.getStatus() != None:
                                print event.getStatus()
                                status = event.getStatus().encode('utf-8')
                            else:
                                status = ''
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_addbuddy(event.getTo().getNode().encode('utf-8'), status))
                            self.jabberqueue(Presence(frm=event.getTo(), to = event.getFrom(), typ = 'subscribed'))
                    else:
                        self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
                elif event.getType() == 'unsubscribe':
                    if userlist.has_key(fromstripped):
                        if userlist[fromstripped].roster.has_key(event.getTo().getNode()):
                            if event.getStatus() != None:
                                msg = event.getStatus().encode('utf-8')
                            else:
                                msg = ''
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_delbuddy(event.getTo().getNode().encode('utf-8'), msg))
                            self.jabberqueue(Presence(frm=event.getTo(), to = event.getFrom(), typ = 'unsubscribed'))
                    else:
                        self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
                elif event.getType() == 'unsubscribed':
                    # should do something more elegant here
                    pass
                elif event.getType() == None or event.getType() == 'available' or event.getType() == 'invisible':
                    # code to add yahoo connection goes here
                    if userlist.has_key(fromstripped):
                        # update status case
                        print fromstripped, event.getShow(), event.getStatus()
                        if event.getShow() == None:
                            if event.getStatus() != None:
                                self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_away(None,event.getStatus()))
                            elif userlist[fromstripped].away == None:
                                self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_back())
                        elif event.getShow() == None and userlist[fromstripped].away != None:
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_away(None,event.getStatus()))
                            userlist[fromstripped].away = None
                        elif event.getShow() == 'xa' or event.getShow() == 'away':
                            self.yahooqueue(fromstripped, userlist[fromstripped].ymsg_send_away('away',event.getStatus()))
                            userlist[fromstripped].away = 'away'
                        elif event.getShow() == 'dnd':
                            self.yahooqueue(fromstripped, userlist[fromstripped].ymsg_send_away('dnd',event.getStatus()))
                            userlist[fromstripped].away= 'dnd'
                        elif event.getType() == 'invisible':
                            self.yahooqueue(fromstripped, userlist[fromstripped].ymsg_send_away('invisible',None))
                            userlist[fromstripped].away= 'invisible'
                    else:
                        # open connection case
                        conf = userfile[fromstripped]
                        yobj = ylib.YahooCon(conf['username'].encode('utf-8'),conf['password'].encode('utf-8'), fromstripped,localaddress)
                        #userlist[fromstripped]=yobj
                        s = yobj.connect()
                        if s != None:
                            rdsocketlist[s]=yobj
                            userlist[yobj.fromjid]=yobj
                            self.register_ymsg_handlers(userlist[fromstripped])
                            #self.yahooqueue(fromstripped,yobj.ymsg_send_challenge())
                            self.yahooqueue(fromstripped,yobj.ymsg_send_init())
                            yobj.event = event
                            if event.getShow() == 'xa' or event.getShow() == 'away':
                                yobj.away = 'away'
                            elif event.getShow() == 'dnd':
                                yobj.away = 'dnd'
                            elif event.getShow() == 'invisible':
                                yobj.away = 'invisible'
                            else:
                                yobj.away = None
                            yobj.showstatus = event.getStatus()
                        else:
                            self.jabberqueue(Error(event,ERR_REMOTE_CONNECTION_FAILED))
                elif event.getType() == 'unavailable':
                    if userlist.has_key(fromstripped):
                        self.y_send_offline(fromstripped)
                        yobj=userlist[fromstripped]
                        self.jabberqueue(Presence(to = fromjid, frm = hostname, typ='unavailable'))
                        if yobj.pripingobj in timerlist:
                            timerlist.remove(yobj.pripingobj)
                        if yobj.secpingobj in timerlist:
                            timerlist.remove(yobj.secpingobj)
                        del userlist[yobj.fromjid]
                        del rdsocketlist[yobj.sock]
                        yobj.sock.close()
                        del yobj
                    else:
                        self.jabberqueue(Presence(to=fromjid,frm = hostname, typ='unavailable'))
            elif event.getTo().getDomain() == chathostname:
                if userlist.has_key(fromstripped):
                    print "chat presence"
                    try:
                        #print event.getTo().getNode().encode('utf-8').decode('base64')
                        room = unicode(event.getTo().getNode().encode('utf-8').decode('base64'),'utf-8','strict')
    
                    except:
                        if userlist[fromstripped].roomnames.has_key(event.getTo().getNode()):
                            room = userlist[fromstripped].roomnames[event.getTo().getNode()]
                        else:
                            self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
                            print "decode error"
                            return
                    userlist[fromstripped].roomnames[event.getTo().getNode().lower()] = room
                    if event.getType() == 'available' or event.getType() == None or event.getType() == '':
                        nick = event.getTo().getResource()
                        userlist[fromstripped].nick = nick
                        if not userlist[fromstripped].chatlogin:
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_conflogon())
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatlogin(None))
                            userlist[fromstripped].roomtojoin = room.encode('utf-8')
                        else:
                            self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatjoin(room.encode('utf-8')))
                    elif event.getType() == 'unavailable':
                        self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatleave(room.encode('utf-8')))
                        self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_chatlogout())
                        self.yahooqueue(fromstripped,userlist[fromstripped].ymsg_send_conflogoff())
                    else:
                        self.jabberqueue(Error(event,ERR_FEATURE_NOT_IMPLEMENTED))
                else:
                    self.jabberqueue(Error(event,ERR_BAD_REQUEST))
        else:
            self.jabberqueue(Error(event,ERR_REGISTRATION_REQUIRED))
                
    def xmpp_iq_notimplemented(self, con, event):
        self.jabberqueue(Error(event,ERR_FEATURE_NOT_IMPLEMENTED))

    
    def xmpp_iq_discoinfo(self, con, event):
        fromjid = event.getFrom()
        to = event.getTo()
        id = event.getID()
        if event.getTo() == hostname:
            m = Iq(to=fromjid,frm=to, typ='result', queryNS=NS_DISCO_INFO, payload=[Node('identity',attrs={'category':'gateway','type':'yahoo','name':VERSTR}),Node('feature',attrs={'var':NS_REGISTER})])
            m.setID(id)
            self.jabberqueue(m)
            raise dispatcher.NodeProcessed
        elif event.getTo().getDomain() == hostname:
            if userlist.has_key(fromjid.getStripped()):
                #print userlist[fromjid.getStripped()].roster
                if userlist[fromjid.getStripped()].roster.has_key(to.getNode()):
                    m = Iq(to=fromjid, frm=to,typ='result',queryNS=NS_DISCO_INFO)
                    p = [Node('identity',attrs={'category':'client','type':'yahoo','name':'Yahoo! User'})]
                    m.setQueryPayload(p)
                    m.setID(id)
                    self.jabberqueue(m)
                else:
                    self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
            else:
                self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
        elif event.getTo().getDomain() == chathostname:
            print (event.getTo().getNode()), type(event.getQuerynode())
            if event.getTo().getNode() == None or event.getTo().getNode() == '':
                if event.getQuerynode() == None:
                    print 'catagory case'
                    m = Iq(to=fromjid,frm=to,typ='result',queryNS=NS_DISCO_INFO, payload=[Node('identity',attrs={'category':'conference','type':'yahoo','name':'Yahoo public chat rooms'}),Node('feature',attrs={'var':NS_MUC})])
                    m.setID(id)
                    self.jabberqueue(m)
                    raise dispatcher.NodeProcessed
                else:
                    print 'catagory item case ',self.chatcat[0][1]
                    if self.chatcat[0][1].has_key(event.getQuerynode()):
                        m = Iq(to=fromjid,frm=to,typ='result',queryNS=NS_DISCO_INFO, payload=[Node('identity',attrs={'name':self.chatcat[0][1][event.getQuerynode()]})])
                        m.setID(id)
                        self.jabberqueue(m)
                        raise dispatcher.NodeProcessed
            else:
                print 'item case', event.getQuerynode()
                try:
                    str = unicode(event.getTo().getNode().encode('utf-8').decode('base64'),'utf-8','strict')
                    info = None
                    if self.catlist.has_key(event.getQuerynode()):
                        lobby,room = str.split(':')
                        if self.catlist[event.getQuerynode()][1].has_key(lobby):
                            t = self.catlist[event.getQuerynode()][1][lobby]
                            print t
                            data = {'muc#roominfo_description':t['name'],'muc#roominfo_subject':t['topic'],'muc#roominfo_occupants':t['rooms']['%s'%room]['users']}
                            print data
                            info = DataForm(typ = 'result', data= data)
                            field = info.setField('FORM_TYPE')
                            field.setType('hidden')
                            field.setValue('http://jabber.org/protocol/muc#roominfo')
                            print info
                    payload = [Node('identity',attrs={'category':'conference','type':'yahoo','name':str}),Node('feature',attrs={'var':NS_MUC})]
                    if info != None:
                        payload.append(info)
                    m = Iq(to=fromjid,frm=to,typ='result',queryNS=NS_DISCO_INFO, payload=payload)
                    m.setID(id)
                    self.jabberqueue(m)
                except:
                    #pass
                    self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
                raise dispatcher.NodeProcessed
                
                
                    
    def xmpp_iq_discoitems(self, con, event):
        fromjid = event.getFrom()
        to = event.getTo()
        id = event.getID()
        if event.getTo() == hostname:
            m = Iq(to=fromjid,frm=to, typ='result', queryNS=NS_DISCO_ITEMS)
            b = [Node('item',attrs={'jid':chathostname,'name':"Yahoo public chat rooms"})]
            if userlist.has_key(fromjid.getStripped()):
                for each in userlist[fromjid.getStripped()].roster.keys():
                    b.append(Node('item', attrs={'jid':'%s@%s' %(each,hostname),'name':each}))                
            m.setQueryPayload(b)
            m.setID(id)
            self.jabberqueue(m)
            raise dispatcher.NodeProcessed
        elif event.getTo().getDomain() == hostname:
            if userlist.has_key(fromjid.getStripped()):
                #print userlist[fromjid.getStripped()].roster
                if userlist[fromjid.getStripped()].roster.has_key(to.getNode()):
                    m = Iq(to=fromjid, frm=to,typ='result',queryNS=NS_DISCO_ITEMS)
                    m.setID(id)
                    self.jabberqueue(m)
                else:
                    self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
            else:
                self.jabberqueue(Error(event,ERR_NOT_ACCEPTABLE))
        elif event.getTo() == chathostname:
            if event.getQuerynode() == None:
                #print self.chatcat
                if self.chatcat[0][0] < (time.time() - (5*60)):
                    t = roomlist.getcata(0)
                    if t != None:
                        for each in t.keys():
                            self.chatcat[each] = (time.time(),t[each])
                payload = []
                for each in self.chatcat[0][1]:
                    payload.append(Node('item', attrs={'jid':to,'node':each,'name':self.chatcat[0][1][each]}))
                m = Iq(to=fromjid,frm=to, typ='result',queryNS=NS_DISCO_ITEMS,payload=payload)
                m.setID(id)
                self.jabberqueue(m)
                raise dispatcher.NodeProcessed
            else:
                # Do get room item
                if not self.catlist.has_key(event.getQuerynode()):
                    t = roomlist.getrooms(event.getQuerynode())
                    if t != None:
                        self.catlist[event.getQuerynode()] = (time.time(),t)
                else:
                    if self.catlist[event.getQuerynode()][0] < (time.time() - 5*60):
                        t = roomlist.getrooms(event.getQuerynode())
                        #print t
                        if t != None:
                            self.catlist[event.getQuerynode()] = (time.time(),t)
                # Do get more categories
                print event.getQuerynode()
                if not self.chatcat.has_key(event.getQuerynode()):
                    t = roomlist.getcata(event.getQuerynode())
                    #print t
                    if t != None:
                        self.chatcat[event.getQuerynode()] = (time.time(),t)
                else:
                    if self.chatcat[event.getQuerynode()][0] < (time.time() - 5*60):
                        t = roomlist.getcata(event.getQuerynode())
                        #print t
                        if t != None:
                            self.chatcat[event.getQuerynode()] = (time.time(),t)
                payload = []
                if len(event.getQuerynode().split('/')) == 1:
                    #add catagories first
                    if self.chatcat.has_key(event.getQuerynode()):
                        for each in self.chatcat[event.getQuerynode()][1].keys():
                            payload.append(Node('item', attrs={'jid':to,'node':each,'name':self.chatcat[event.getQuerynode()][1][each]}))
                    # First level of nodes
                    #print self.catlist[event.getQueryNode()]
                    for z in self.catlist[event.getQuerynode()][1].keys():
                        each = self.catlist[event.getQuerynode()][1][z]
                        if each.has_key('type'):
                            if each['type'] == 'yahoo':
                                if each.has_key('rooms'):
                                    for c in each['rooms'].keys():
                                        n = ('%s:%s' % (each['name'],c)).encode('base64').strip()
                                        payload.append(Node('item',attrs={'jid':'%s@%s'%(n,chathostname),'node':event.getQuerynode(),'name':'%s:%s'%(each['name'],c)}))
                                        #print payload
                m = event.buildReply('result')
                m.setQueryNS(NS_DISCO_ITEMS)
                m.setQuerynode(event.getQuerynode())
                m.setQueryPayload(payload)
                self.jabberqueue(m)
                raise dispatcher.NodeProcessed
        elif event.getTo().getDomain() == chathostname:
            m = event.buildReply('result')
            m.setQueryNS(NS_DISCO_ITEMS)
            self.jabberqueue(m)
        else:
            self.jabberqueue(Error(event,ERR_FEATURE_NOT_IMPLEMENTED))
            raise dispatcher.NodeProcessed
    
    
    
    def xmpp_iq_agents(self, con, event):
        m = Iq(to=event.getFrom(), frm=event.getTo(), typ='result', payload=[Node('agent', attrs={'jid':hostname},payload=[Node('service',payload='yahoo'),Node('name',payload=VERSTR),Node('groupchat')])])
        m.setID(event.getID())
        self.jabberqueue(m)
        raise dispatcher.NodeProcessed
    
    def xmpp_iq_register_get(self, con, event):
        if event.getTo() == hostname:
            username = []
            password = []
            fromjid = event.getFrom().getStripped().encode('utf8')
            if userfile.has_key(fromjid):
                username = userfile[fromjid]['username']
                password = userfile[fromjid]['password']
            m = event.buildReply('result')
            m.setQueryNS(NS_REGISTER)
            m.setQueryPayload([Node('instructions', payload = 'Please provide your Yahoo! username and password'),Node('username',payload=username),Node('password',payload=password)])
            self.jabberqueue(m)                                             
        else:
            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
            
    def xmpp_iq_register_set(self, con, event):
        if event.getTo() == hostname:
            remove = False
            username = False
            password = False
            fromjid = event.getFrom().getStripped().encode('utf8')
            for each in event.getQueryPayload():
                if each.getName() == 'username':
                    username = each.getData()
                    print "Have username ", username
                elif each.getName() == 'password':
                    password = each.getData()
                    print "Have password ", password
                elif each.getName() == 'remove':
                    remove = True
            if not remove and username and password:
                if userfile.has_key(fromjid):
                    conf = userfile[fromjid]
                else:
                    conf = {}
                conf['username']=username
                conf['password']=password
                userfile[fromjid]=conf
                if userlist.has_key(fromjid):
                    self.y_closed(userlist[fromjid])
                if not userlist.has_key(fromjid):
                    yobj = ylib.YahooCon(username.encode('utf-8'),password.encode('utf-8'), fromjid,localaddress)
                    userlist[fromjid]=yobj
                    print "try connect"
                    s = yobj.connect()
                    if s != None:
                        print "conect made"
                        rdsocketlist[s]=yobj
                        userlist[fromjid]=yobj
                        self.yahooqueue(fromjid,yobj.ymsg_send_challenge())
                    yobj.handlers['login']=self.y_reg_login
                    yobj.handlers['loginfail']=self.y_reg_loginfail
                    yobj.handlers['ping']=self.y_ping
                    yobj.event = event
                    yobj.showstatus = None
                    yobj.away = None
            elif remove and not username and not password:
                if userlist.has_key(fromjid):
                    self.y_closed(userlist[fromjid])
                if userfile.has_key(fromjid):
                    del userfile[fromjid]
                    m = event.buildReply('result')
                    self.jabberqueue(m)
                    m = Presence(to = event.getFrom(), frm = hostname, typ = 'unsubscribe')
                    self.jabberqueue(m)
                    m = Presence(to = event.getFrom(), frm = hostname, typ = 'unsubscribed')
                    self.jabberqueue(m)
                else:
                    self.jabberqueue(Error(event,ERR_BAD_REQUEST))
            else:
                self.jabberqueue(Error(event,ERR_BAD_REQUEST))
        else:
            self.jabberqueue(Error(event,ERR_BAD_REQUEST))
    
    def xmpp_iq_avatar(self, con, event):
        fromjid = event.getFrom()
        fromstripped = fromjid.getStripped()
        if userfile.has_key(fromstripped):
            if userfile[fromstripped].has_key('avatar'):
                if userfile[fromstripped]['avatar'].has_key(event.getTo().getNode()):
                    m = Iq(to = event.getFrom(), frm=event.getTo(), typ = 'result', queryNS='jabber:iq:avatar', payload=[Node('data',attrs={'mimetype':'image/png'},payload=base64.encodestring(userfile[fromstripped]['avatar'][event.getTo().getNode()][1]))])
                    m.setID(event.getID())
                    self.jabberqueue(m)
                else:
                    self.jabberqueue(Error(event,ERR_NOT_FOUND))
            else:
                self.jabberqueue(Error(event,ERR_NOT_FOUND))
        else:
            self.jabberqueue(Error(event,ERR_NOT_FOUND))
    
    def y_avatar(self,fromjid,yid,avatar):
        if avatar != None:
            a = sha.new(avatar)
            hex = a.hexdigest()
        conf = userfile[fromjid]
        if not conf.has_key('avatar'):
            conf['avatar']={}
        conf['avatar'][yid]=(hex,avatar)
        userfile[fromjid] = conf
    
    def y_closed(self, yobj):
        if userlist.has_key(yobj.fromjid):
            if not yobj.connok:
                if yobj.moreservers():
                    del rdsocketlist[yobj.sock]
                    if wrsocketlist.has_key(yobj.sock):
                        del wrsocketlist[yobj.sock]
                    yobj.sock.close()
                    s= yobj.connect()
                    if s != None:
                        rdsocketlist[s]=yobj
                        userlist[yobj.fromjid]=yobj
                        self.yahooqueue(yobj.fromjid,yobj.ymsg_send_challenge())
                        return # this method terminates here - all change please
            self.jabberqueue(Presence(to = yobj.fromjid, frm = hostname, typ='unavailable'))
            self.jabberqueue(Error(Presence(frm = yobj.fromjid, to = hostname),ERR_REMOTE_CONNECTION_FAILED))
            if yobj.pripingobj in timerlist:
                timerlist.remove(yobj.pripingobj)
            if yobj.secpingobj in timerlist:
                timerlist.remove(yobj.secpingobj)
            del userlist[yobj.fromjid]
            del rdsocketlist[yobj.sock]
            if wrsocketlist.has_key(yobj.sock):
                del wrsocketlist[yobj.sock]
            #yobj.sock.close()
            del yobj
    
    def y_ping(self, yobj):
        print "got ping!"
        freq = yobj.pripingtime*60
        offset = int(time.time())%freq
        yobj.pripingtime = time.time()
        yobj.pripingobj=(freq,offset,self.yahooqueue,[yobj.fromjid, yobj.ymsg_send_priping()])
        timerlist.append(yobj.pripingobj)
        freq = yobj.secpingtime*60
        offset = int(time.time())%freq
        yobj.secpingtime = time.time()
        yobj.secpingobj=(freq,offset,self.yahooqueue,[yobj.fromjid, yobj.ymsg_send_secping()])
        timerlist.append(yobj.secpingobj)
        self.jabberqueue(Presence(to = yobj.fromjid, frm = hostname))
        yobj.handlers['loginfail']= self.y_closed
        yobj.handlers['login']= self.y_closed
        yobj.connok = True
        self.yahooqueue(yobj.fromjid,yobj.ymsg_send_online(yobj.away, yobj.showstatus))
    
    def y_login(self,yobj):
        print "got login"
        
    def y_loginfail(self,yobj):
        print "got login fail"
        print yobj.conncount, yobj.moreservers()
        if yobj.moreservers():
            del rdsocketlist[yobj.sock]
            yobj.sock.close()
            s = yobj.connect()
            if s != None:
                rdsocketlist[s]=yobj
                userlist[yobj.fromjid]=yobj
                self.yahooqueue(fromstripped,yobj.ymsg_send_challenge())
                return # this method terminates here - all change please
        else:        
            self.jabberqueue(Error(yobj.event,ERR_NOT_AUTHORIZED))
            del userlist[yobj.fromjid]
            del rdsocketlist[yobj.sock]
            yobj.sock.close()
            del yobj
        
    def y_online(self,yobj,name):
        b = Presence(to = yobj.fromjid, frm = '%s@%s/messenger'%(name, hostname),priority = 10, show=yobj.roster[name][1], status=yobj.roster[name][2])
        if userfile[yobj.fromjid].has_key('avatar'):
            print userfile[yobj.fromjid]['avatar'].keys(), name
            if userfile[yobj.fromjid]['avatar'].has_key(name):
                b.addChild(node=Node('x',attrs={'xmlns':'jabber:x:avatar'},payload=[Node('hash',payload=userfile[yobj.fromjid]['avatar'][name][0])]))
        self.jabberqueue(b)
    
    def y_chatonline(self,yobj, name):
        b = Presence(to = yobj.fromjid, frm = '%s@%s/chat' %(name,hostname), priority = 5)
        self.jabberqueue(b)
    
    def y_offline(self,yobj,name):
        self.jabberqueue(Presence(to = yobj.fromjid, frm = '%s@%s/messenger'%(name, hostname),typ='unavailable'))    
    
    def y_chatoffline(self,yobj,name):
        self.jabberqueue(Presence(to =yobj.fromjid, frm = '%s@%s/chat'%(name, hostname),typ='unavailable'))
    
    def y_subscribe(self,yobj,nick,msg):
        self.jabberqueue(Presence(typ='subscribe',frm = '%s@%s' % (nick, hostname), to=yobj.fromjid,payload=msg))
    
    def y_message(self,yobj,nick,msg):
        self.jabberqueue(Message(typ='chat',frm = '%s@%s/messenger' %(nick,hostname), to=yobj.fromjid,body=cpformat.do(msg)))
        
    def y_messagefail(self,yobj,nick,msg):
        self.jabberqueue(Error(Message(typ='chat',to = '%s@%s' %(nick,hostname), frm=yobj.fromjid,body=msg),ERR_SERVICE_UNAVAILABLE))
    
    def y_chatmessage(self,yobj,nick,msg):
        self.jabberqueue(Message(typ='chat',frm = '%s@%s/chat' %(nick,hostname), to=yobj.fromjid,body=cpformat.do(msg)))
    
    def y_roommessage(self,yobj,yid,room,msg):
        txt = cpformat.do(msg)
        if yobj.roomlist[room]['byyid'].has_key(yid):
            nick = yobj.roomlist[room]['byyid'][yid]['nick']
        else:
            nick = yid
        self.jabberqueue(Message(typ = 'groupchat', frm = '%s@%s/%s' % (room.encode('base64').strip(),chathostname,nick),to=yobj.fromjid,body=txt))
    
    def y_calendar(self,yobj,url,desc):
        m = Message(to=yobj.fromjid,typ='headline', subject = "Yahoo Calendar Event", body = desc)
        p = m.setTag('x', namespace = 'jabber:x:oob')
        p.addChild(name = 'url',payload=url)
        self.jabberqueue(m)
    
    def y_email(self,yobj, fromtxt, fromaddr, subj):
        if fromtxt != None:
            bfrom = fromtxt
        else:
            bfrom = ''
        if fromaddr != None:
            bfrom = bfrom + ' < ' + fromaddr + ' > '
        m = Message(to=yobj.fromjid,typ='headline', subject = "Yahoo Email Event", body = 'From: %s\nSubject: %s'% (unicode(bfrom,'utf-8','replace'),unicode(subj,'utf-8','replace')))
        self.jabberqueue(m)
        
    def y_reg_login(self,yobj):
        # registration login handler
        print "got reg login"
        m = yobj.event.buildReply('result')
        self.jabberqueue(m)
        self.jabberqueue(Presence(typ='subscribe',to=yobj.fromjid, frm=hostname))
            
    def y_reg_loginfail(self,yobj):
        print "got reg login fail"
        if yobj.moreservers():
            del rdsocketlist[yobj.sock]
            yobj.sock.close()
            s= yobj.connect()
            if s != None:
                rdsocketlist[s]=yobj
                userlist[yobj.fromjid]=yobj
                self.yahooqueue(yobj.fromjid,yobj.ymsg_send_challenge())
                return # this method terminates here - all change please
        # registration login failure handler
        self.jabberqueue(Error(yobj.event,ERR_NOT_ACCEPTABLE)) # will not work, no event object
        del userlist[yobj.fromjid]
        del rdsocketlist[yobj.sock]
        yobj.sock.close()
        del yobj
         
    def y_send_online(self,fromjid):
        print fromjid,userlist[fromjid].roster
        for each in userlist[fromjid].roster:
            if userlist[fromjid].roster[each][0] == 'available':
                self.jabberqueue(Presence(frm = '%s@%s' % (each,hostname), to = fromjid))
    
    def y_send_offline(self,fromjid):
        print fromjid,userlist[fromjid].roster
        for each in userlist[fromjid].roster:
            if userlist[fromjid].roster[each][0] == 'available':
                self.jabberqueue(Presence(frm = '%s@%s' % (each,hostname), to = fromjid, typ='unavailable'))    
    
    #chat room functions
    def y_chat_login(self,fromjid):
        userlist[fromjid].chatlogin=True
        self.yahooqueue(fromjid,userlist[fromjid].ymsg_send_chatjoin(userlist[fromjid].roomtojoin))
        del userlist[fromjid].roomtojoin
        
    def y_chat_roominfo(self,fromjid,info):
        if not userlist[fromjid].roomlist.has_key(info['room']):
            userlist[fromjid].roomlist[info['room']]={'byyid':{},'bynick':{},'info':info}
            self.jabberqueue(Presence(frm = '%s@%s' %(info['room'].encode('base64').strip(),chathostname),to=fromjid))
            self.jabberqueue(Presence(frm = '%s@%s' %(info['room'].encode('base64').strip(),chathostname),to=fromjid, typ='groupchat', subject= info['topic']))
            
    def y_chat_join(self,fromjid,room,info):
        if userlist[fromjid].roomlist.has_key(room):
            if not userlist[fromjid].roomlist[room]['byyid'].has_key(info['yip']):
                userlist[fromjid].roomlist[room]['byyid'][info['yip']] = info
                if not info.has_key('nick'):
                    info['nick'] = info['yip']
                #print info['yip'],userlist[fromjid].username
                if info['yip'] == userlist[fromjid].username:
                    jid = fromjid
                    print info['nick'], userlist[fromjid].nick
                    if info['nick'] != userlist[fromjid].nick:
                        p = Presence(frm = '%s@%s/%s' % (room.encode('base64').strip(),chathostname,userlist[fromjid].nick), typ='unavailable')
                        p.addChild(node=MucUser(jid = jid, nick = info['nick'], role = 'participant', affiliation = 'none', status = 303))
                        self.jabberqueue(p)
                else:
                    jid = '%s@%s' % (info['yip'],hostname)
                userlist[fromjid].roomlist[room]['bynick'][info['nick']]= info['yip']
                self.jabberqueue(Presence(frm = '%s@%s/%s' % (room.encode('base64').strip(),chathostname,info['nick']), to = fromjid, payload=[MucUser(role='participant',affiliation='none',jid = jid)]))
    
    def y_chat_leave(self,fromjid,room,yid,nick):
        # Need to add some cleanup code
        #
        #
        if userlist[fromjid].roomlist.has_key(room):
            if userlist[fromjid].roomlist[room]['byyid'].has_key(yid):
                del userlist[fromjid].roomlist[room]['bynick'][userlist[fromjid].roomlist[room]['byyid'][yid]['nick']]
                del userlist[fromjid].roomlist[room]['byyid'][yid]
                self.jabberqueue(Presence(frm = '%s@%s/%s' % (room.encode('base64').strip(),chathostname,nick), to= fromjid, typ = 'unavailable'))
                
    def xmpp_iq_browse(self, con, event):
        m = Iq(to = event.getFrom(), frm = event.getTo(), typ = 'result', queryNS = NS_BROWSE)
        if event.getTo() == hostname:
            #m.setTagAttr('query','catagory','conference')
            #m.setTagAttr('query','name','xmpp Yahoo Transport')
            #m.setTagAttr('query','type','yahoo')
            #m.setTagAttr('query','jid','hostname')
            m.setPayload([Node('service',attrs = {'type':'yahoo','name':'xmpp Yahoo Transport','jid':hostname},payload=[Node('ns',payload=NS_MUC),Node('ns',payload=NS_REGISTER)])])
        self.jabberqueue(m)
        #raise xmpp.NodeProcessed
    
    def xmpp_iq_version(self, con, event):
        fromjid = event.getFrom()
        to = event.getTo()
        id = event.getID()
        m = Iq(to = fromjid, frm = to, typ = 'result', queryNS=NS_VERSION, payload=[Node('name',payload=VERSTR), Node('version',payload='0.1'),Node('os',payload='%s %s %s' % (os.uname()[0],os.uname()[2],os.uname()[4]))])
        m.setID(id)
        self.jabberqueue(m)
        #raise xmpp.NodeProcessed    


if __name__ == '__main__':
    userfile = shelve.open('user.dbm')
    configfile = ConfigParser.ConfigParser()
    configfile.add_section('yahoo')
    try:
        cffile = open('transport.ini','r')
    except IOError:
        print "Transport requires configuration file, please supply"    
        sys.exit(1)
    configfile.readfp(cffile)
    server = configfile.get('yahoo','Server')
    #print server
    hostname = configfile.get('yahoo','Hostname')
    #print hostname
    chathostname = 'chat.'+hostname
    confhostname = 'conf.'+hostname
    port = int(configfile.get('yahoo','Port'))
    secret = configfile.get('yahoo','Secret')
    if configfile.has_option('yahoo','LocalAddress'):
        localaddress = configfile.get('yahoo','LocalAddress')
    else:
        localaddress = '0.0.0.0'
    if configfile.has_option('yahoo','Charset'):
        charset = configfile.get('yahoo','Charset')
    
    if not connectxmpp():
        print "Password mismatch!"
        sys.exit(1)
    trans = Transport(connection)
    rdsocketlist[connection.Connection._sock]='xmpp'
    while 1:
        #print 'poll',rdsocketlist
        try:
            (i , o, e) = select.select(rdsocketlist.keys(),wrsocketlist.keys(),[],1)
        except ValueError:
            print "Value Error", rdsocketlist, wrsocketlist
            trans.findbadconn()
##            for each in rdsocketlist.keys():
##                try:
##                    (ii,io,ie) = select.select([each],[],[])
##                except ValueError:
##                    try:
##                        if rdsocketlist[each] != 'xmpp':
##                            trans.y_closed(rdsocketlist[each])
##                        else:
##                            print "We shouldn't get a bad xmpp socket here"
##                    except KeyError:
##                        print "badconn"
##                        trans.findbadconn()
##            for each in wrsocketlist.keys():
##                try:
##                    (ii,io,ie) = select.select([],[each],[])
##                except ValueError:
##                    try:
##                        if rdsocketlist[each] != 'xmpp':
##                            trans.y_closed(rdsocketlist[each])
##                        else:
##                            print "We shouldn't get a bad xmpp socket here"
##                    except KeyError:
##                        print "badconn"
##                        trans.findbadconn()
        for each in i:
            try:
                if rdsocketlist[each] == 'xmpp':
                    connection.Process(1)
                    if not connection.isConnected():  transport.xmpp_disconnect()
                else:
                    rdsocketlist[each].Process()
            except KeyError:
                pass
        for each in o:
            try:
                if rdsocketlist[each] == 'xmpp':
                    while select.select([],[each],[])[1] and wrsocketlist[each] != []:
                        connection.send(wrsocketlist[each].pop(0))
                else:
                    #print wrsocketlist 
                    each.send(wrsocketlist[each].pop(0))
                if wrsocketlist[each] == []:
                    del wrsocketlist[each]
            except KeyError:
                pass
        #delayed execution method modified from python-irclib written by Joel Rosdahl <joel@rosdahl.net>
        for each in timerlist:
            #print int(time.time())%each[0]-each[1]
            if not (int(time.time())%each[0]-each[1]):
                apply(each[2],each[3])