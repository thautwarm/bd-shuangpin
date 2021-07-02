#!/usr/bin/env python
# author: thautwarm<twshere@outlook.com>
# license: BSD-3

import time
import json
import socket
from wisepy2 import wise
from sqlite_interops import SQLCache
from sortedcontainers.sortedlist import SortedKeyList
_undef = None


REMOVE = 0
ADD = 1

def is_undef(x):
    return x is _undef


def mk_undef(): return _undef


def set_undef(db: 'DirtySortedDict', x):
    x.value = _undef


def negmax_key(x):
    return x.negmax


class DirtySortedDict:
    def __init__(self, key_func):
        self.key_func = key_func
        self.mapped = {}
        self.ranked = SortedKeyList(key=negmax_key)
        self.negmax = 0
        self.dirty_key = None
        self.seg = None
        self.value = mk_undef()

    def __repr__(self):
        return f'{self.mapped!r}[{self.value}]'


def update_connect(last_db, db, ch):
    if db.seg in last_db.mapped:
        last_db.ranked.remove(db)
    db.seg = ch
    if db.dirty_key is not None:
        db.negmax = db.dirty_key
        db.dirty_key = None
    v_negmax = db.negmax
    assert db.negmax is not None, db.seg
    last_db.ranked.add(db)
    last_db.mapped[ch] = db
    return v_negmax


def _neg_max(self: DirtySortedDict):
    if not is_undef(self.value):
        negmax = self.key_func(self.value)
    else:
        negmax = 0
    for _, v in self.mapped.items():
        assert isinstance(v, DirtySortedDict)
        negmax = min(negmax, v.negmax)
    return negmax


def _modify(db: DirtySortedDict, seq, i, modify_func, key_func):
    new_key = None
    any_change = False
    try:
        ch = seq[i]
        if sub_db := db.mapped.get(ch):
            pass
        else:
            sub_db = db.mapped[ch] = DirtySortedDict(key_func)
        any_change = any_change or _modify(
            sub_db,
            seq,
            i+1,
            modify_func,
            key_func
        )
        if (not sub_db.mapped
                and is_undef(sub_db.value)):

            del db.mapped[ch]
            try:
                db.ranked.remove(sub_db)
                any_change = True
            except ValueError:
                pass
            if sub_db.negmax == db.negmax:
                new_key = _neg_max(db)
        else:
            new_key = min(
                db.negmax,
                update_connect(db, sub_db, ch)
            )
    except IndexError:
        orig_value = db.value
        value = modify_func(orig_value)
        db.value = value
        new_key = db.key_func(value)
        any_change = orig_value != value

    if new_key != db.negmax:
        any_change = True
        db.dirty_key = new_key

    return any_change


def _visit_elements(prefix, db):
    consumed_mid = False
    for v in db.ranked:
        if not consumed_mid and v.negmax > db.negmax:
            consumed_mid = True
            if not is_undef(db.value):
                yield prefix, db.value
        yield from _visit_elements((*prefix, v.seg), v)
    if not consumed_mid:
        if not is_undef(db.value):
            yield prefix, db.value


def _get_neg_freq(d):
    if is_undef(d):
        return 0
    return -d


def _create_leaf(mapped, ranked, name, freq):
    trie = object.__new__(DirtySortedDict)
    trie.seg = name
    trie.value = freq
    trie.dirty_key = None
    trie.negmax = -freq
    trie.mapped = {}
    trie.ranked = SortedKeyList(key=negmax_key)
    trie.key_func = _get_neg_freq
    ranked.add(trie)
    mapped[name] = trie
    return trie


def create_large_dirty_trie(pairs):
    groups = {}
    for k, name, freq in pairs:
        if not k:
            group = groups.setdefault("", [])
            group.append((None, name, freq))
            continue

        group = groups.setdefault(k[0], [])
        group.append((k[1:], name, freq))

    negmax = 0
    mapped = {}
    ranked = SortedKeyList(key=negmax_key)
    for k, group in groups.items():
        if not k:
            for _, name, freq in group:
                leaf = mapped[name] = _create_leaf(mapped, ranked, name, freq)
                negmax = min(leaf.negmax, negmax)
            continue
        trie = mapped[k] = create_large_dirty_trie(group)
        ranked.add(trie)
        trie.seg = k
        negmax = min(negmax, trie.negmax)

    root = object.__new__(DirtySortedDict)
    root.value = mk_undef()
    root.dirty_key = None
    root.negmax = negmax
    root.mapped = mapped
    root.ranked = ranked
    root.key_func = _get_neg_freq
    return root


class Trie:
    def __init__(self, disk_db, sync_time_period=0.5, db=None):
        self.last_time = time.time()
        self.sync_time_period = sync_time_period
        self.actions = []
        self.disk_db = disk_db
        self.db = db or create_large_dirty_trie(list(disk_db.fetchall()))
        # self.add(code, name, freq)

        self.actions.clear()

    def publish(self):
        def ap():
            if time.time() - self.last_time > self.sync_time_period:
                for each in self.actions:
                    if each[0] is REMOVE:
                        code, name = each[1]
                        self.disk_db.remove(*each[1])
                    elif each[0] is ADD:
                        self.disk_db.add(each[1], each[2])
                self.last_time = time.time()
                self.actions.clear()
        return ap

    def remove(self, seq: str, name: str):
        assert seq
        ACTION_ARGS = (REMOVE, (seq, name))
        seq = (*seq, name)

        def ap(x):
            if is_undef(x):
                return x
            self.actions.append(ACTION_ARGS)
            return mk_undef()
        self._modify(seq, ap)

    def _modify(self, seq: str, func):
        assert seq
        _modify(self.db, seq, 0, func, _get_neg_freq)

    def add(self, seq: str, name: str, freq: int):
        ACTION_ARGS = (ADD, (seq, name), freq)
        assert seq
        seq = (*seq, name)

        def ap(x):
            self.actions.append(ACTION_ARGS)
            return freq
        self._modify(seq, ap)

    def prefixed(self, seq: str):
        assert seq
        seq = tuple(seq)
        db = self.db
        steps = list(reversed(seq))
        while steps:
            db = db.mapped.get(steps.pop())
            if not db:
                return
        yield from _visit_elements(seq, db)

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
        options = self.trie.prefixed(inp)
        return [(''.join(chs), word) for _, ((*chs, word), freq) in zip(range(n_max_completions), options)]
                                 
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
    trie = Trie(sql_db)
    server = IMESever(trie)

    try:
        server.run()
    finally:
        server.sock.close()

if __name__ == '__main__':
    wise(main)()