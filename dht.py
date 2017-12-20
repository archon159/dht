import asyncio

import network
import timer
from enum import Enum
import logging
import datetime
import time
import hashlib
import os

_SHORT = datetime.timedelta(seconds=5)
_LONG = datetime.timedelta(seconds=20)
_MARGIN = 2
_REPEAT = _MARGIN * (_LONG / _SHORT)


class DHT(network.Network, timer.Timer):
    class State(Enum):
        START = 1
        MASTER = 2
        SLAVE = 3


    # Broadcast information of node to peers.
    def update_peer_list(self):

        for (_, timer) in self._context.heartbeat_timer.items():
            timer.cancel()
        self._context.heartbeat_timer.clear()
        self._context.timestamp = time.time()

        message = {
            "type": "leader_is_here",
            "uuid": self.uuid,
            "timestamp": self._context.timestamp,
            "peer_count": len(self._context.peer_list) + 1 #self include
        }
        self.send_message(message, (network.NETWORK_BROADCAST_ADDR, network.NETWORK_PORT))

        index = 0

        # Assign index to each peer.
        for (uuid, addr) in self._context.peer_list:
            self._context.heartbeat_timer[uuid] = \
                self.async_trigger(lambda: self.master_heartbeat_timeout(uuid), _LONG / 2)
            index += 1
            message = {
                "type": "peer_list",
                "uuid": self.uuid,
                "timestamp": self._context.timestamp,
                "peer_index": index,
                "peer_uuid": uuid,
                "peer_addr": addr,
            }
            self.send_message(message, (network.NETWORK_BROADCAST_ADDR, network.NETWORK_PORT))

    def message_arrived(self, message, addr):
        if message["uuid"] == self.uuid and (message["type"] != "insert") and (message["type"] != "delete") and (message["type"] != "search"):
            return
        logging.debug("Message received from {addr}, {message}".format(addr=addr, message=message))

        print(message)
        #print(message["type"])
        # In master case, add a node and broadcast it.
        if message["type"] == "hello":
            if self._state == self.State.START:
                self._context.messages.append((message, addr))
            elif self._state == self.State.MASTER:
                #print("message uid = "+str(message["uuid"]))
                #print("message addr = "+str(addr))
                #print(self._context.peer_list)
                if not (message["uuid"], addr) in self._context.peer_list:
                    #print("New Node!!")
                    self._context.peer_list.append((message["uuid"], addr))
                    self._context.peer_list.sort(reverse=True)
                    self.update_peer_list()

                    self.master_peer_list_updated()
                    #print("Updated for Hello Message")
        # if ping, pong
        elif message["type"] == "heartbeat_ping":
            message = {
                "type": "heartbeat_pong",
                "uuid": self.uuid,
                "timestamp": time.time(),
            }
            self.send_message(message, addr)

        # In master case, timer reset.
        # In slave case, master timer reset.
        elif message["type"] == "heartbeat_pong":
            if self._state == self.State.MASTER:
                client_uuid = message["uuid"]
                if client_uuid in self._context.heartbeat_timer:
                    prev = self._context.heartbeat_timer[client_uuid]
                    prev.cancel()
                    self._context.heartbeat_timer[client_uuid] = \
                        self.async_trigger(lambda: self.master_heartbeat_timeout(client_uuid), _LONG/2)
            elif self._state == self.State.SLAVE:
                master_uuid = message["uuid"]
                if self._context.master_uuid == master_uuid:
                    self._context.heartbeat_timer.cancel()
                    self._context.heartbeat_timer = self.async_trigger(self.slave_heartbeat_timeout, _LONG/2)

        # if I am start node, or new master was selected,
        # Reset self context with new master info
        elif message["type"] == "leader_is_here":
            if self._state == self.State.START or \
                    (self._state == self.State.SLAVE and self._context.master_timestamp < message["timestamp"]):
                self._context.cancel()
                self._state = self.State.SLAVE
                self._context = self.SlaveContext()
                self._context.master_uuid = message["uuid"]
                self._context.master_addr = addr
                self._context.peer_count = int(message["peer_count"])
                self._context.master_timestamp = message["timestamp"]
                asyncio.ensure_future(self.slave(), loop=self._loop)
                pass

        # if I am a slave,
        # And message was sent after my master,
        # list contains set of (uuid, peer_addr), index makes list
        elif message["type"] == "peer_list":
            if self._state == self.State.SLAVE:
                if self._context.master_timestamp == message["timestamp"]:
                    self._context.peer_index[message["peer_index"]] = (message["peer_uuid"], message["peer_addr"])

                    if (len(self._context.peer_index) + 1) == self._context.peer_count:
                        self._context.peer_list = []
                        for i in range(1, self._context.peer_count):
                            self._context.peer_list.append(self._context.peer_index[i])
                        self.slave_peer_list_updated()
        elif message["type"] == "search":
            logging.info("Client request: search")
            ret = self.search_item(message["key"])
            print("search complete")
            if message["uuid"] == self.uuid:
                if not os.path.isfile(message["output"]):
                    self.print_output(message["output"],str(ret))
            else:
                response_message = {
                    "type": "client_response",
                    "uuid": self.uuid,
                    "client": message["client"],
                    "key": message["key"],
                    "result": ret,
                    "output": message["output"]
                }
                self.send_message(response_message, addr)
            
        elif message["type"] == "client_response":
            if not os.path.isfile(message["output"]):
            	self.print_output(message["output"],str(ret))

        elif message["type"] == "insert":
            logging.info("Client request: insert")
            ret = self.insert_item(message["key"], message["value"])
            print("insert complete")
            if message["uuid"] == self.uuid:
                pass
                #self.print_output(message["output"],str(ret))
            else:
                response_message = {
                    "type": "client_response",
                    "uuid": self.uuid,
                    "client": message["client"],
                    "key": message["key"],
                    "value": message["value"],
                    "result": ret,
                    "output": message["output"]
                }

        elif message["type"] == "delete":
            logging.info("Client request: delete")
            ret = self.delete_item(message["key"])
            print("delete complete")
            if message["uuid"] == self.uuid:
                pass
                #self.print_output(message["output"],str(ret))
            else:
                response_message = {
                    "type": "client_response",
                    "uuid": self.uuid,
                    "client": message["client"],
                    "key": message["key"],
                    "result": ret,
                    "output": message["output"]
                }

        elif message["type"] == "client_request":
            if self._state == self.State.START:
                if not os.path.isfile(message["output"]):
                    output = message["output"]
                    f = open(output,"w+")
                    f.write("Sorry, I'm not ready to serve your request.\r\n")
                    f.close()

            else:
                client = self.uuid
                new_message = {
                    "type": message["command"],
                    "uuid": self.uuid,
                    "client": client,
                    "key": message["key"],
                    "output": message["output"]
                }
                if "value" in message:
                    new_message.setdefault("value", message["value"])
                self.send_message(new_message, (network.NETWORK_BROADCAST_ADDR, network.NETWORK_PORT))
#        elif message["type"] == "client_response":
#            if message["client"] == self.uuid:


    # state info func
    def print_output(self, filename, result):
        f = open(filename, "w+")
        f.write(result+"\r\n")
        f.close()

    def search_item(self, key):
        ret = False
        h = hashlib.sha512()
        h.update(key.encode('utf-8'))
        hh = int.from_bytes(h.digest(),byteorder='big')

        if hh in self.dht:
            item_dict = self.dht[hh]
            if key in item_dict:
                ret = item_dict[key]
            else:
                ret = False
        else:
            ret = False
        #value at success, False at fail
        return ret

    def insert_item(self, key, value):
        ret = True

        h = hashlib.sha512()
        h.update(key.encode('utf-8'))
        hh = int.from_bytes(h.digest(),byteorder='big')

        if hh in self.dht:
            item_dict = self.dht[hh]
            if key in item_dict:
                ret = False
            else:
                item_dict.setdefault(key, value)
        else:
            item_dict = {}
            item_dict.setdefault(key, value)
            self.dht.setdefault(hh, item_dict)
        #True at success, False at fail
        return ret
            
    def delete_item(self, key):
        ret = False
        h = hashlib.sha512()
        h.update(key.encode('utf-8'))
        hh = int.from_bytes(h.digest(),byteorder='big')

        if hh in self.dht:
            item_dict = self.dht[hh]
            if key in item_dict:
                del item_dict[key]
                if len(item_dict) == 0:
                    del self.dht[hh]
                ret = True
            else:
                ret = False
        else:
            ret = False
        #True at success, False at fail
        return ret

    def master_peer_list_updated(self):
        logging.info("Peer list updated: I'm MASTER with {peers} peers".format(peers=len(self._context.peer_list)))
        for (uuid, addr) in self._context.peer_list:
            logging.info("Peer list updated: PEER[{peer}]".format(peer=str((uuid, addr))))

    # state info func
    def slave_peer_list_updated(self):
        logging.info("Peer list updated: MASTER[{master}] with {peers} peers".format(
            master=str((self._context.master_uuid, self._context.master_addr)), peers=len(self._context.peer_list)))
        for (uuid, addr) in self._context.peer_list:
            logging.info("Peer list updated: PEER[{peer}]".format(peer=str((uuid,addr))))
        return

    async def slave_heartbeat_timeout(self):
        print("slave_heartbeat_timeout")
        if self._context.heartbeat_send_job is not None:
            self._context.heartbeat_send_job.cancel()
        self._state = self.State.START
        self._context = self.StartContext()
        asyncio.ensure_future(self.start(), loop=self._loop)

    async def master_heartbeat_timeout(self, client_uuid):
        print("master_heartbeat_timeout")
        client = None
        for (uuid, addr) in self._context.peer_list:
            if uuid == client_uuid:
                client = (uuid, addr)
        self._context.peer_list.remove(client)
        self.update_peer_list()
        self.master_peer_list_updated()

    class StartContext:
        def __init__(self):
            self.hello_job = None
            self.timeout_job = None
            self.messages = []

        def cancel(self):
            if self.hello_job is not None:
                self.hello_job.cancel()
            if self.timeout_job is not None:
                self.timeout_job.cancel()
            pass

    class MasterContext:
        def __init__(self):
            self.peer_list = []
            self.timestamp = time.time()
            self.heartbeat_send_job = None
            self.heartbeat_timer = {}

        def cancel(self):
            if self.heartbeat_send_job is not None:
                self.heartbeat_send_job.cancel()
            for (_, timer) in self.heartbeat_timer.items():
                timer.cancel()
            pass

    class SlaveContext:
        def __init__(self):
            self.peer_list = []
            self.peer_index = {}
            self.peer_count = 0
            self.master_addr = None
            self.master_uuid = None
            self.master_timestamp = None
            self.heartbeat_send_job = None
            self.heartbeat_timer = None

        def cancel(self):
            if self.heartbeat_send_job is not None:
                self.heartbeat_send_job.cancel()
            if self.heartbeat_timer is not None:
                self.heartbeat_timer.cancel()
            pass

    async def master(self):
        async def heartbeat_send():
            for (_, addr) in self._context.peer_list:
                message = {
                    "type": "heartbeat_ping",
                    "uuid": self.uuid,
                    "timestamp": time.time(),
                }
                self.send_message(message, addr)
        self._context.heartbeat_send_job = self.async_period(heartbeat_send, _SHORT)
        pass

    async def slave(self):
        async def heartbeat_send():
            message = {
                "type": "heartbeat_ping",
                "uuid": self.uuid,
                "timestamp": time.time(),
            }
            self.send_message(message, self._context.master_addr)

        self._context.heartbeat_timer = self.async_trigger(self.slave_heartbeat_timeout, _LONG / 2)
        self._context.heartbeat_send_job = self.async_period(heartbeat_send, _SHORT)
        pass

    async def start(self):
        self._context = self.StartContext()
        async def hello():
            message = {
                "type": "hello",
                "uuid": self.uuid,
            }
            logging.debug("Sending HELLO message")
            self.send_message(message, (network.NETWORK_BROADCAST_ADDR, network.NETWORK_PORT))

        async def timeout():
            self._context.hello_job.cancel()
            logging.info("Cannot find any existing leader.")
            if len(self._context.messages) == 0:
                logging.info("Cannot find any peer. I am the leader.")
                self._state = self.State.MASTER
                self._context = self.MasterContext()
                asyncio.ensure_future(self.master(), loop=self._loop)
            else:
                max_val = self.uuid
                max_addr = None
                unique_addr = set()

                # Leader Election, MAX uuid
                for (message, addr) in self._context.messages:
                    if message["uuid"] > max_val:
                        max_val = message["uuid"]
                        max_addr = addr
                    if message["uuid"] != self.uuid:
                        unique_addr.add((message["uuid"], addr))
                if max_addr is None:
                    #I am the leader
                    sorted_list = list(unique_addr)
                    sorted_list.sort(reverse=True)
                    self._context = self.MasterContext()
                    self._state = self.State.MASTER
                    self._context.peer_list = sorted_list
                    asyncio.ensure_future(self.master(), loop=self._loop)
                    logging.info("I am the leader of {peers} peers".format(peers=len(sorted_list)))
                else:
                    #I am the slave
                    #self._context = self.SlaveContext()
                    #self._state = self.State.SLAVE
                    pass

            if self._state == self.State.MASTER:
                self.update_peer_list()
                self.master_peer_list_updated()

        self._context.hello_job = self.async_period(hello, _SHORT)
        self._context.timeout_job = self.async_trigger(timeout, _LONG)

        pass

    def __init__(self, loop):
        network.Network.__init__(self, loop)
        timer.Timer.__init__(self, loop)
        self._state = self.State.START
        self._loop = loop
        self._context = None
        self.dht = {}

        import uuid
        self.uuid = str(uuid.uuid1())

        asyncio.ensure_future(self.start(), loop=self._loop)
