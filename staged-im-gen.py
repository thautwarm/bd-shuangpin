#!/usr/bin/env python
"""
Created on Thu Jul  1 04:45:21 2021

@author: twshe
"""

import re
import os
import wisepy2
from collections import defaultdict
from hanzidentifier import is_simplified as _is_simplified
from pypinyin import pinyin, Style, load_single_dict, load_phrases_dict
from itertools import product, accumulate
from pypinyin.style.tone import ToneConverter
from linq import Flow
from functools import lru_cache
from im_db.db_kXHC1983 import pinyin_dict as _pinyin_dict
from im_db.db_kTGHZ2013 import pinyin_dict
from im_db.db_hanzi_endstroke import endstroke
from im_db.db_hanzi_spell import hanzi_spell
from im_db.db_hanzi_wubi86 import hanzi_wubi86_spell

stroke_map = {
    '1': 'g',
    '2': 'h',
    '3': 't',
    '4': 'y',
    '5': 'n'
}

pinyin_dict.update(_pinyin_dict)
pinyin_dict.update({ord('的'): 'de', ord('耶'): 'yē,yé,yè', ord('地'): 'dì'})
load_single_dict(pinyin_dict)
load_phrases_dict({"好耶": [["hǎo"], ["yè"]]})

to_tone3 = ToneConverter().to_tone3
tone_re = re.compile('[0-4]')


def _split_spells(spells: list[str]):
    res = set()
    for spell in spells:
        if spell[-1] in '01234':
            tone = int(spell[-1]) or 1
            spell = spell[:-1]
        else:
            tone = 1
        res.add((tone, spell))
    return list(res)


tone_map = {1: 'a', 2: 's', 3: 'd', 4: 'f'}


@lru_cache(maxsize=150)
def get_toned_spells(word):
    """
    in> "好耶"
    out: [((3, "hao"), (4, "ye")), ...<其他读音>]
    """
    word = pinyin(word, heteronym=True, style=Style.TONE3,
                  v_to_u=False, errors=lambda x: 1/0, strict=True)
    res = list(product(*map(_split_spells, word)))
    return res


def _normalize_pinyin(one_py):
    """ 规范化
    ue -> ve
    """
    if 'ue' in one_py:
        return one_py.replace('ue', 've')
    if 'ng' == one_py:   # 嗯
        return 'en'
    return one_py


shuangpin_table = [
    ('iu', 'q'),
    ('ei', 'w'),
    ('uan', 'r'),
    ('ue', 't'),
    ('ve', 't'),
    ('un', 'y'),
    ('sh', 'u'),
    ('ch', 'i'),
    ('uo', 'o'),
    ('ie', 'p'),
    ('ong', 's'),
    ('iong', 's'),
    ('ai', 'd'),
    ('en', 'f'),
    ('eng', 'g'),
    ('ng', 'g'),
    ('ang', 'h'),
    ('an', 'j'),
    ('uai', 'k'),
    ('ing', 'k'),
    ('uang', 'l'),
    ('iang', 'l'),
    ('ou', 'z'),
    ('ua', 'x'),
    ('ia', 'x'),
    ('ao', 'c'),
    ('zh', 'v'),
    ('ui', 'v'),
    ('in', 'b'),
    ('iao', 'n'),
    ('ian', 'm')
]
shuangpin_table.sort(key=lambda xs: xs[0], reverse=True)


@lru_cache(maxsize=2000)
def to_shuangpin(s: str):
    if s in ('m', 'n', 'hn'):
        raise ValueError
    n = len(s)
    if n == 2:
        return s
    i = 0
    elts = []
    while i < n:
        for orig, fold in shuangpin_table:
            if s.startswith(orig, i):
                elts.append(fold)
                i += len(orig)
                break
        else:
            elts.append(s[i])
            i += 1

    spell = ''.join(elts)
    if len(spell) != 2:
        assert len(spell) == 1, spell
    return spell


@lru_cache(maxsize=2000)
def all_simplified(word):
    return all(_is_simplified(c) for c in word)


def generate(gen_func, *vocab_filenames: str):
    delay_records = []

    def _delay_gen(word, spell, freq):
        delay_records.append([word, spell, freq])

    def _apply_delay_gen():
        order_(delay_records)
        for word, spell, freq in delay_records:
            gen_func(word, spell, freq)

    check_dup = set()
    wubis = Flow(hanzi_wubi86_spell).group_by(lambda x: x[0])._
    cnt_hanzi = 0
    for (ch, target_spell, freq) in hanzi_spell:
        if ch not in wubis:
            continue
        try:
            cases = list(get_toned_spells(ch))
        except:
            continue
        for [(tone, spell)] in cases:
            spell = _normalize_pinyin(spell)
            if spell != target_spell:
                continue
            try:
                sp_spell = to_shuangpin(spell)

            except:
                print(f'invalid spelling: {ch}={spell}')
                continue
            try:
                endstroke_code = stroke_map[endstroke[ch]]
            except:
                print(f'unknown shape: {ch}')
                continue

            tone_code = tone_map[tone]
            freq = int(freq)
            cnt_hanzi += 1
            for _, wubi_spell in wubis.get(ch, ()):
                code = 'o'+sp_spell+tone_code+wubi_spell[0]+endstroke_code
                dup_key = (ch, code)
                if dup_key in check_dup:
                    continue
                else:
                    check_dup.add(dup_key)
                _delay_gen(ch, code, freq)
    _apply_delay_gen()
    check_dup.clear()
    del delay_records, _apply_delay_gen, _delay_gen
    print(f"{cnt_hanzi}单字已处理完毕...")
    cnt_word = 0
    for vocab_filename in vocab_filenames:
        with open(vocab_filename, 'r', encoding='utf8') as f:
            while word := next(f, '').strip():
                try:
                    word, freq = word.split("\t")
                except:
                    print(repr(word))
                    raise

                if len(word) < 2:
                    continue
                if not all_simplified(word):
                    continue

                try:
                    cases = get_toned_spells(word)
                except:
                    continue
                freq = int(freq)
                cnt_word += 1
                for case in cases:
                    if len(case) < 2:
                        raise ValueError(case, word)
                    try:
                        code = ''.join(to_shuangpin(each_spell)
                                       for _, each_spell in case)
                    except:
                        continue
                    tone1, _ = case[-1]
                    tone2, _ = case[-2]
                    tone_fst, _ = case[0]
                    code += tone_map[tone1] + \
                        tone_map[tone_fst] + tone_map[tone2]
                    dup_key = (word, code)
                    if dup_key in check_dup:
                        continue
                    else:
                        check_dup.add(dup_key)
                    gen_func(word, code, int(freq))
    print(f"{cnt_word}词语已处理完毕...")


def order_(results: list[list[tuple[str, str, int]]]):
    unique_filter = defaultdict(lambda: 1)
    for (_, spell, freq) in results:
        for spell in accumulate(spell):
            unique_filter[spell] += 1

    for record in results:
        ch, spell, freq = record
        freq = int(freq)
        score = 1 + int(freq / (unique_filter[spell] ** 3))
        record[2] = score

    results = [tuple(record) for record in results]
    results.sort(key=lambda x: tuple((c, x[2]) for c in x[1]), reverse=True)


def get_gen_func(name: str, path: str):
    build = os.path.join(path, "build", f"{name}.table.bin")
    if os.path.exists(build):
        os.remove(build)
    f = open(os.path.join(path, name+".dict.yaml"), 'w', encoding='utf-8')
    f.write(f"""\
---
name: {name}
version: "0.1"
sort: original
...
""")

    def direct_gen(word, spell, freq):
        f.write(f"{word}\t{spell}\t{freq}\n")
    return direct_gen


def main(im_name: str, user_path: str, *vocab_files: str):
    gen_func = get_gen_func(im_name, user_path)

    generate(gen_func, *vocab_files)


if __name__ == '__main__':
    wisepy2.wise(main)()
