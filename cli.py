import socket
import json
import os
import copy
import time

NETWORK_MAGIC_VALUE= "Sound body, sound code."

UDPSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
addr = ("localhost", 9999)
data = {}

print("Hello, This is CLI program for easy use of DHT.")
print("Please set your timeout for search in unit of seconds.")
timeout = input()
while(1):
	data = {
		"type": "client_request",
		"command": None,
		"uuid": "self_client",
		"key": None,
		"value": None,
               	"_magic": NETWORK_MAGIC_VALUE,
               	"output": None
	}
	print("Type your command and press enter. (insert, search, delete)")
	command_type = input()
	data["command"] = command_type
	print("Type your key and press enter.")
	key = input()
	data["key"] = key
	if command_type == "insert":
		print("Type your value and press enter.")
		value = input()
		data["value"] = value
	if command_type == "search":
		print("Type the file name that you will get output and press enter.")
		output = input()
		data["output"] = output
		if os.path.isfile(output):
	    		os.remove(output)
#f = open(output,"w")
#f.close()
	print(data)

	exist_flag = False
	if command_type == "insert":
		if os.path.isfile("temp_search_result"):
			os.remove("temp_search_result")
		search_data = copy.deepcopy(data) 
		search_data["command"] = "search"
		search_data["value"] = None
		search_data["output"] = "temp_search_result"
		search_message = json.dumps(search_data)
		UDPSock.sendto(search_message.encode(encoding='utf-8', errors='strict'), addr)
		prev_time = time.time()
		print("Searching for if there is any node who has the key.")
		current_time = time.time()
		while (current_time - prev_time) < int(timeout):
			if os.path.isfile("temp_search_result"):
				print("There is the key already.")
				exist_flag = True
				os.remove("temp_search_result")
				break
			else:
				current_time = time.time()
	if exist_flag is False:
		message = json.dumps(data)
		UDPSock.sendto(message.encode(encoding='utf-8', errors='strict'), addr)
		print("Sended Your Request")
		print()
