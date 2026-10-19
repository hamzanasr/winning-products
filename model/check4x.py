# -*- coding: utf-8 -*-
"""Pre-check a research file with the same rules as build_1500.py.
Usage: python model/check4x.py <file.json>
Prints PASS/FAIL per product: Made-in-China supplier median (pack-adjusted), cost used, multiple, duplicates."""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_1500 import pack_count, listing_is_pack, toks, jacc, BANNED, work
from mic_enrich import evidence

FX = 3.75
path = sys.argv[1]
P = json.load(open(path, encoding="utf-8"))
others = []
for f in glob.glob(os.path.join(work, "out", "*.json")):
    if os.path.abspath(f) != os.path.abspath(path):
        try:
            others += [toks(x["en"]) for x in json.load(open(f, encoding="utf-8"))]
        except Exception:
            pass
others += [toks(l) for l in open(os.path.join(work, "existing", "ALL.txt"), encoding="utf-8").read().splitlines() if l.strip()]
ok = 0
for x in P:
    ev = evidence(x)
    sell, buy = float(x["sell_sar"]), float(x["buy_usd"])
    mic = ev["mic_usd"] if ev["mic_usd"] and ev["n_priced"] >= 3 else None
    n = pack_count(x["en"], x.get("ar", ""))
    if mic and n > 1 and not any(listing_is_pack(t.get("title") or "", n) for t in ev["top"]):
        mic *= n
    usd = max(mic, buy) if mic and mic >= buy * 0.8 else buy
    mult = sell / (usd * FX)
    t = toks(x["en"])
    dup = any(jacc(t, o) >= 0.75 for o in others)
    bad = []
    if mult < 4: bad.append(f"4x FAIL (x{mult:.2f})")
    if not 50 <= sell <= 200: bad.append("price range")
    if float(x.get("kg", 0)) > 3: bad.append("too heavy")
    if dup: bad.append("DUPLICATE")
    if BANNED.search(x["en"]): bad.append("excluded category")
    ok += not bad
    print(("PASS " if not bad else "FAIL ") + f"{x['en'][:55]:55} sell {sell:>5.0f} agent ${buy:<6} mic {('$%.2f' % mic) if mic else 'n/a':>7} ({ev['n_priced']} listings, range {ev['mic_range'] or '-'}) used ${usd:.2f} x{mult:.2f} " + "; ".join(bad))
print(f"\n{ok}/{len(P)} pass")
