# -*- coding: utf-8 -*-
"""Measured pre-check for 100–200 SAR ideas (same rules as build_v3.py).
Usage: python model/check100.py <file.json>
Input: list of {"en", "ar", ...}. For each product: Amazon.sa search (Saudi price, competition) and
Made-in-China supplier price, then PASS/FAIL with the measured numbers. Also rejects duplicates of
earlier lists. Network results are cached, so re-runs are fast."""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_1500 import pack_count, listing_is_pack, toks, jacc, BANNED, work
from mic_enrich import evidence
from amz_comp import analyse

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX, MIN_SELL = 3.75, 100
path = sys.argv[1]
P = json.load(open(path, encoding="utf-8"))
seen = [toks(l) for l in open(os.path.join(work, "existing", "ALL.txt"), encoding="utf-8").read().splitlines() if l.strip()]
for f in ("products_v2.json", "products_v3.json"):
    fp = os.path.join(root, "data", f)
    if os.path.exists(fp):
        seen += [toks(p["en"]) for p in json.load(open(fp, encoding="utf-8"))["products"]]
for f in glob.glob(os.path.join(work, "out3", "*.json")):
    if os.path.abspath(f) != os.path.abspath(path):
        try:
            seen += [toks(x["en"]) for x in json.load(open(f, encoding="utf-8"))]
        except Exception:
            pass
ok = 0
for x in P:
    en = x["en"]
    bad = []
    if BANNED.search(en): bad.append("excluded category")
    if any(jacc(toks(en), s) >= 0.75 for s in seen): bad.append("DUPLICATE of an earlier list")
    az = analyse({"en": en, "price": 150})
    if az is None or az.get("n", 0) < 10:
        print("RETRY " + en + " (Amazon.sa returned no/too few results, run again later)"); continue
    med = az.get("med_price") if az.get("n_rel", 0) >= 3 else None
    if med:   # re-score cheap substitutes against the real price
        az = analyse({"en": en, "price": med * 0.95}) or az
    ref = med or x.get("sell_sar")
    sell, bundle = (min(200, ref * 0.95) if med else ref) if ref else 0, 1
    if sell and sell < MIN_SELL and med and float(x.get("kg") or 0.5) <= 1 and sell * 2 * 0.9 >= MIN_SELL:
        bundle, sell = 2, min(200, sell * 2 * 0.9)
    if not sell or sell < MIN_SELL: bad.append(f"Saudi price under 100 (median {med})")
    ev = evidence({"en": en})
    mic = ev["mic_usd"] if ev.get("mic_usd") and ev.get("n_priced", 0) >= 3 else None
    n = pack_count(en, x.get("ar", ""))
    if mic and n > 1 and not any(listing_is_pack(t.get("title") or "", n) for t in ev.get("top", [])):
        mic *= n
    usd = max([v for v in (mic, x.get("buy_usd")) if v] or [0]) * bundle
    if not usd: bad.append("no supplier price found")
    mult = sell / (usd * FX) if usd and sell else 0
    if usd and sell and mult < 4: bad.append(f"under 4x (x{mult:.1f})")
    if az["comp"] > 6 and not (az["comp"] <= 7 and az.get("weak_incumbent")): bad.append(f"competition {az['comp']}/10")
    ok += not bad
    print(("PASS " if not bad else "FAIL ") + f"{en[:55]:55} sa_median {med} sell {sell:.0f}{' (2-pack)' if bundle > 1 else ''} supplier ${usd:.2f} x{mult:.1f} comp {az['comp']}/10 "
          f"(rel {az['n_rel']}, strong {az['n_strong']}, local strong {az['n_strong_local']}) " + "; ".join(bad))
print(f"\n{ok}/{len(P)} pass")
