import socket
import json

NETWORK_MAGIC_VALUE= "Sound body, sound code."

UDPSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

data = {}

print("Hello, This is CLI program for easy use of DHT.")
print("Type your command and press enter. (insert, search, delete)")
command_type = input()
print("Type your key and press enter.")
key = input()
print("Type your value and press enter.")
value = input()
data.setdefault("type", command_type)
data.setdefault("uuid", "self_client")
data.setdefault("key", key)
data.setdefault("value", value)
data.setdefault("_magic", NETWORK_MAGIC_VALUE)

message = json.dumps(data)

addr = ("localhost", 9999)

UDPSock.sendto(message.encode(encoding='utf-8', errors='strict'), addr)
