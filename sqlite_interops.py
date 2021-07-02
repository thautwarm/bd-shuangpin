# -*- coding: utf-8 -*-
"""
Created on Fri Jul  2 08:36:29 2021

@author: twshe
"""
import sqlite3

def create(conn):
    try:
        with conn:
            conn.execute('''
        CREATE TABLE T1(
          word VARCHAR(100) NOT NULL,
          code VARCHAR(50)  NOT NULL,
          freq INT NOT NULL,
          PRIMARY KEY (word, code)
         );''')
            conn.commit()
    except:
        pass

class SQLCache:
    def __init__(self, path:str):
        self.conn = sqlite3.connect(path)
        self.is_instantiated = False
    def instantiate(self):
        create(self.conn)
        self.is_instantiated = True
    
    def add(self, code: str, word: str, freq: int):
        if not self.is_instantiated:
            self.instantiate()
        with self.conn:
            self.conn.executemany(
                "insert into T1 (code, word, freq) values (?, ?, ?)",
                [(code, word, freq)])
            self.conn.commit()
    
    def add_many(self, seq):
        if not self.is_instantiated:
            self.instantiate()
        with self.conn:
            self.conn.executemany(
                "insert into T1 (word, code, freq) values (?, ?, ?)",
                seq)
            self.conn.commit()
    
    
    def fetchall(self):
        if not self.is_instantiated:
            self.instantiate()
        with self.conn:
            return self.conn.execute("select code, word, freq from T1")
            

