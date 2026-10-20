# -*- coding: utf-8 -*-
"""Writes data/<out>.json: unmeasured v3 candidates with a supplier price that can still reach 4x at <= 200 SAR,
for the in-browser Amazon.sa worker. Usage: python model/make_queue.py <out_name> [exclude_queue.json ...]"""
import json, sys, glob, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_1500 import pack_count, listing_is_pack
work = '..'
c = json.load(open(f'{work}/v3_candidates.json', encoding='utf8'))
a = json.load(open('data/amz_comp.json', encoding='utf8'))
mic = json.load(open('data/mic_1500.json', encoding='utf8'))
skip = set()
for q in sys.argv[2:]:
    skip |= {x[0] for x in json.load(open(q, encoding='utf8'))}
extra = {}
for f in glob.glob(f'{work}/out3/*.json'):
    for x in json.load(open(f, encoding='utf8')):
        extra[x['en'].strip()] = x
norm = {}
for f in glob.glob(f'{work}/norm_out2/*.jsonl'):
    for l in open(f, encoding='utf8'):
        try:
            x = json.loads(l); norm[x['en'].strip()] = x
        except Exception:
            pass
bs = {}
for name in ('bs_sa.json', 'nr_com.json', 'bs_com.json'):
    try: bs.update(json.load(open('data/' + name, encoding='utf8')))
    except Exception: pass
Q = []
for x in c:
    en = x['en']
    if en in a or en in skip: continue
    ev = mic.get(en, {}); e = extra.get(en, {}); nx = norm.get(en, {})
    has = ev.get('mic_usd') and ev.get('n_priced', 0) >= 3
    n = pack_count(en, e.get('ar') or nx.get('ar', ''))
    m = ev['mic_usd'] * (n if has and n > 1 and not any(listing_is_pack(t.get('title') or '', n) for t in ev.get('top', [])) else 1) if has else None
    usd = max([v for v in (m, e.get('buy_usd')) if v] or [0])
    if not usd or usd * 3.75 * 4 > 200: continue
    ref = e.get('sell_sar') or (bs.get(nx.get('asin'), {}) or {}).get('price_sar')
    Q.append([en, round(usd, 2), ref, float(e.get('kg') or nx.get('kg') or 0.5)])
json.dump(Q, open(f'data/{sys.argv[1]}.json', 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
print(len(Q))
