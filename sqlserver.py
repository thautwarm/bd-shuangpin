#!/usr/bin/env python
# author: thautwarm<twshere@outlook.com>
# license: BSD-3

import json
import socket
from wisepy2 import wise
from sqlite_interops import SQLCache

class SocketServer:
    def init(self, addr=("127.0.0.1", 51515), white_list=('127.0.0.1', )):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(addr)
        sock.listen(1)
        self.sock = sock
        self.white_list = white_list

    def on_each(self, data_packet):
        print(data_packet)
        
    def on_interrupt(self):
        print("interrupt!")

    def on_summary(self):
        print("summary!")

    def run(self):
        sock = self.sock
        while True:
            try:
                conn, (client_host, _) = sock.accept()
            except socket.timeout:
                continue
            if client_host not in self.white_list:
                continue
            try:
                while True:
                    received: bytes = conn.recv(4)
                    if not received:
                        conn.close()
                        break
                    if not received.isdigit():
                        continue
                    n_bytes = int(received)
                    while n_bytes:
                        n_recv = min(n_bytes, 512)
                        received = conn.recv(n_recv)
                        n_bytes -= len(received)
                        self.on_each(received)
                    self.on_summary(conn)
            except OSError:
                pass
            finally:
                self.on_interrupt(conn)
                conn.close()

class IMESever(SocketServer):
    def __init__(self, sql_db, addr=("127.0.0.1", 51515), white_list=('127.0.0.1', )):
        self.init(addr, white_list)
        self.packets = bytearray()
        self.sql_db = sql_db
        self.n_max_completions = 6

    
    def on_interrupt(self, _):
        self.packets.clear()
    
    def on_each(self, packet: bytes):
        self.packets.extend(packet)
        print(self.packets)
    
    def query(self, inp, n_max_completions):
        options = self.sql_db.conn.execute(
            "select code, word from T1 where "
            "code LIKE ? || '%' order by freq DESC limit ?",
            (inp, n_max_completions))
        return list(options)
    def on_summary(self, conn):
        data = json.loads(self.packets)
        self.packets.clear()
        req = data.get("request", "completion")
        
        if req == "completion":
            inp = data.get("input")
            if not inp:
                return
            options = list(self.query(inp, self.n_max_completions))
            print(options)
            buff = json.dumps(options).encode(encoding="gbk")
            x = len(buff)
            
            if x < 10000:
                digits = str(x)
                digits = (None, '000', '00', '0', '')[len(digits)] + digits
                conn.send(digits.encode())
                conn.send(buff)
            else:
                conn.send(b'0002')
                conn.send(b'[]')


def main(*, dbpath: str = r"C:\Users\twshe\AppData\Roaming\Rime\t_shuangpin.db"):
    global server
    sql_db = SQLCache(dbpath)
    server = IMESever(sql_db)

    try:
        server.run()
    finally:
        server.sock.close()

if __name__ == '__main__':
    wise(main)()
