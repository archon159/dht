import socket
import json
import os

NETWORK_MAGIC_VALUE= "Sound body, sound code."

UDPSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

data = {}

print("Hello, This is CLI program for easy use of DHT.")
print("Type your command and press enter. (insert, search, delete)")
command_type = input()
print("Type your key and press enter.")
key = input()
if command_type == "insert":
	print("Type your value and press enter.")
	value = input()
print("Type the file name that you will get output and press enter.")
output = input()
data.setdefault("type", "client_request")
data.setdefault("command", command_type)
data.setdefault("uuid", "self_client")
data.setdefault("key", key)
if command_type == "insert":
	data.setdefault("value", value)
data.setdefault("_magic", NETWORK_MAGIC_VALUE)
data.setdefault("output", output)

if os.path.isfile(output):
    os.remove(output)
#f = open(output,"w")
#f.close()
message = json.dumps(data)

addr = ("localhost", 9999)

UDPSock.sendto(message.encode(encoding='utf-8', errors='strict'), addr)
