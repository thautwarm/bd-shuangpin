#!/usr/bin/env python
# author: thautwarm<twshere@outlook.com>
# license: BSD-3

from os import defpath
import time
import json
import socket
from wisepy2 import wise
from sqlite_interops import SQLCache
from sortedcontainers.sortedlist import SortedKeyList
_undef = None


REMOVE = 0
ADD = 1

MAX = ...
LEAF = None

def _visit_elements(prefix, db: dict):
    for k, child in db.items():
        if child is LEAF:
            yield prefix, k
        else:
            yield from _visit_elements(prefix + k, child)

def fst(x):
    return x[0]

_cnt = 0
def create_large_dirty_trie(pairs):
    global _cnt
    groups = {}
    for k, name, freq in pairs:
        if not k:
            group = groups.setdefault("", [])
            group.append((None, name, freq))
            continue

        group = groups.setdefault(k[0], [])
        group.append((k[1:], name, freq))

    negmax = 0
    pairs = []
    for k, group in groups.items():
        if not k:
            for _, name, freq in group:
                _cnt += 1
                nfreq = -freq
                negmax = min(nfreq, negmax)
                pairs.append((nfreq, (name, LEAF)))
                if _cnt %1000 == 0:
                    print(f"{_cnt}...")
            continue
        
        trie, negmax_ = create_large_dirty_trie(group)
        pairs.append((negmax_, (k, trie)))
        negmax = min(negmax, negmax_)
    
    pairs.sort(key=fst)
    return {k: v for _, (k, v) in pairs}, negmax

def prefixed(db: dict, seq: str):
    assert seq    
    try:
        for c in seq:
            db = db[c]
    except (KeyError, TypeError):
        return
    yield from _visit_elements('', db)
    

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
    def __init__(self, trie, addr=("127.0.0.1", 51515), white_list=('127.0.0.1', )):
        self.init(addr, white_list)
        self.packets = bytearray()
        self.trie = trie
        self.n_max_completions = 6
    

    def on_interrupt(self, _):
        self.packets.clear()
    
    def on_each(self, packet: bytes):
        self.packets.extend(packet)
        print(self.packets)
    
    def query(self, inp, n_max_completions):
        options = prefixed(self.trie, inp)
        return [record for _, record in zip(range(n_max_completions), options)]
                                 
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


def main(*,
    sepath: str = None,
    dbpath: str = None):
    global server
    
    if sepath is not None:
        import pickle
        trie = pickle.load(open(sepath, 'rb'))
    elif dbpath is not None:
        sql_db = SQLCache(dbpath)
        records = list(sql_db.fetchall())
        trie, _ = create_large_dirty_trie(records)
    else:
        raise ValueError
    
    server = IMESever(trie)
    try:
        server.run()
    finally:
        server.sock.close()

if __name__ == '__main__':
    wise(main)()