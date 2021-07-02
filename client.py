# -*- coding: utf-8 -*-
"""
Created on Fri Jul  2 09:19:41 2021

测试用

@author: twshe
"""

import socket
import json
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sock.connect(("127.0.0.1", 51515))

def complete(inp):
    a = json.dumps({"request": "completion", "input": inp}).encode()
    sock.send(b'00'+str(len(a)).encode())
    sock.send(a)
    b = sock.recv(4)
    print(b)
    print(json.loads(sock.recv(int(b))))
