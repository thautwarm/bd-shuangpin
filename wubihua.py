import yaml
from hanzidentifier import is_simplified
from sqlite_interops import SQLCache
from wisepy2 import wise

@wise
def main(*, dbpath: str):
    mapping = {ord(a): b for a, b in dict(h='a', s='s',p='d',n='f', z='c').items()}
    records = []
    for line in open("./stroke.dict.yaml"):
        line = line.strip()
        if not line: continue
        try:
            a, b = line.split('\t')
        except ValueError:
            continue
        if not is_simplified(a): continue
        b = b.translate(mapping)
        records.append((a, b, 1))
    SQLCache(dbpath).add_many(records)

if '__main__' == __name__:
    main()