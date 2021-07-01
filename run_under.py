#!/usr/bin/env python
from subprocess import check_call
import os
from wisepy2 import wise

def main(dir: str, command: str):
    os.chdir(dir)
    check_call(command)

if __name__ == '__main__':
    wise(main)()