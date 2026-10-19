# -*- coding: utf-8 -*-
"""Builds the 1500-opportunity dataset and dashboard (opportunities.html).
Steps: merge agent research (../out/*.json) -> hard filters -> dedupe vs existing 890 and within
-> supplier evidence from Made-in-China (data/mic_1500.json, made by model/mic_enrich.py)
-> 4x rule on the verified supplier price -> Noon/Amazon fees -> score -> top N.
Run from the repo root:  python model/build_1500.py [--prep]
  --prep  only writes ../candidates.json (input for mic_enrich.py) and stops."""
import json, os, re, sys, glob, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fees import commission_rate, fbn_fee

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = os.path.dirname(root)
N = 1500
FX = 3.75

CATS = {"إكسسوارات الجوال والإلكترونيات": "E", "المنزل والمطبخ": "H", "الرياضة واللياقة": "S", "السيارات والدراجات": "C", "التخييم والسفر": "T",
        "الأطفال والألعاب": "K", "الأدوات والصيانة": "D", "الحيوانات الأليفة": "P", "المكتب والدراسة": "O", "رمضان والمناسبات": "R",
        "التنظيف والغسيل": "W", "الإضاءة والديكور": "L", "الحديقة والخارج": "G", "الحقائب والسفر": "B", "الأمان المنزلي": "Z"}
# Amazon.sa referral fee (approximate, most categories 15%)
AMZ = {"C": 0.12, "D": 0.12, "O": 0.12, "G": 0.12}
BANNED = re.compile(r"\b(serum|cream|lotion|shampoo|perfume|fragrance|cosmetic|makeup|lipstick|skincare|skin care|hair growth|supplement|vitamin|"
                    r"medical|blood pressure|thermometer|glucose|pill|tooth|dental|razor|shaver|epilator|nail|eyelash|beard|wig|massage oil|essential oil|"
                    r"massage|massager|carbon monoxide|smoke detector|battery pack|rechargeable batteries|baby bottle|pacifier|teether|breast|drone|walkie|knife sharpener rod|taser|stun|pepper spray|e-cig|vape)\b", re.I)
STOP = {"for", "with", "and", "the", "a", "of", "in", "to", "set", "pcs", "pack", "kit"}


def toks(s):
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def jacc(a, b):
    return len(a & b) / max(1, len(a | b))


def num(v, d=None):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return d


def load_raw():
    out = []
    for f in sorted(glob.glob(os.path.join(work, "out", "*.json"))):
        try:
            arr = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print("BAD FILE", f, e); continue
        for x in arr:
            x["_src"] = os.path.basename(f)
        out += arr
    return out


def clean(raw):
    existing = [toks(l) for l in open(os.path.join(work, "existing", "ALL.txt"), encoding="utf-8").read().splitlines() if l.strip()]
    seen, keep, why = [], [], {}
    def drop(k):
        why[k] = why.get(k, 0) + 1
    for x in raw:
        en = str(x.get("en", "")).strip(); ar = str(x.get("ar", "")).strip()
        sell, buy, kg = num(x.get("sell_sar")), num(x.get("buy_usd")), num(x.get("kg"), 0.5)
        if not en or not ar or sell is None or buy is None: drop("missing"); continue
        if not x.get("problem") or not x.get("top_competitor"): drop("incomplete research"); continue
        if not 50 <= sell <= 200: drop("price range"); continue
        if kg > 3: drop("too heavy"); continue
        if BANNED.search(en): drop("excluded category"); continue
        if x.get("cat") not in CATS: x["cat"] = "المنزل والمطبخ"
        t = toks(en)
        if any(jacc(t, e) >= 0.75 for e in existing): drop("dup of existing 890"); continue
        if any(jacc(t, s) >= 0.75 for s in seen): drop("dup within new"); continue
        seen.append(t)
        x.update(en=en, ar=ar, sell_sar=round(sell), buy_usd=buy, kg=kg)
        keep.append(x)
    print("raw", len(raw), "kept", len(keep), "dropped", why)
    return keep


AR_NUM = {"حبتين": 2, "قطعتين": 2}


def pack_count(en, ar):
    """Units per sold pack, from names like 'set of 5', '3-pack', '10 pcs', '(3 حبات)'."""
    m = (re.search(r"(?:set|pack|kit) of (\d+)", en, re.I) or re.search(r"(\d+)\s*-?\s*(?:pack|pcs|pieces|pc|count|ct)\b", en, re.I)
         or re.search(r"(\d+)\s*(?:حبات|قطع|حبة|قطعة)", ar))
    if m:
        return max(1, min(50, int(m.group(1))))
    return next((v for k, v in AR_NUM.items() if k in ar), 1)


def listing_is_pack(title, n):
    """True when a supplier listing title already describes a pack of n (so its price is per pack)."""
    return bool(re.search(rf"(?<!\d){n}\s*(?:pcs|pc|pieces|pack|packs|set|sets|in 1|-pack|count|ct)\b|(?:set|pack|kit) of {n}\b", title, re.I))


def score(p):
    """0–100 opportunity score: margin, competition, daily sales, evidence."""
    m = max(0, min(1, (p["noon_margin"] + 0.05) / 0.45))
    c = (10 - p["comp"]) / 9
    d = min(1, p["daily"] / 6)
    e = {"verified": 1, "partial": 0.6, "estimate": 0.3}.get(p["conf"], 0.3) * 0.5 + (0.5 if p["cost_src"] != "est" else 0)
    mult = min(1, max(0, (p["mult"] - 4) / 4))
    return round(100 * (0.30 * m + 0.25 * c + 0.20 * d + 0.15 * e + 0.10 * mult), 1)


def main():
    keep = clean(load_raw())
    if "--prep" in sys.argv:
        json.dump([{"en": x["en"]} for x in keep], open(os.path.join(work, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("candidates written", len(keep)); return
    mic = json.load(open(os.path.join(root, "data", "mic_1500.json"), encoding="utf-8"))
    A = dict(fx=FX, agent=0.08, ship=8.0, customs=0.05, vat=0.15, ads=0.08, ret=0.03)
    prods, fail4 = [], []
    for x in keep:
        ev = mic.get(x["en"], {})
        # conservative: the higher of the supplier median and the researcher's estimate
        # (single-piece listings can undercut a multi-piece set, so never go below the estimate)
        has_mic = bool(ev.get("mic_usd")) and ev.get("n_priced", 0) >= 3
        n = pack_count(x["en"], x["ar"])
        if has_mic and n > 1 and not any(listing_is_pack(t.get("title") or "", n) for t in ev.get("top", [])):
            ev = dict(ev, mic_usd=round(ev["mic_usd"] * n, 2), pack=n)   # listings priced per piece, product is a pack
        if has_mic and ev["mic_usd"] >= x["buy_usd"] * 0.8:
            cost_src, usd = "mic", max(ev["mic_usd"], x["buy_usd"])
        else:
            cost_src, usd = ("est_mic_lower" if has_mic else "est"), x["buy_usd"]
        sell = x["sell_sar"]
        mult = sell / (usd * FX)
        letter = CATS[x["cat"]]
        size = "S" if x.get("size") == "صغير" else "M"
        c = {"en": x["en"].lower(), "cat": letter, "kg": x["kg"], "size": size}
        pct = commission_rate(c, sell); fbn = fbn_fee(c, sell)
        landed = (usd * FX * (1 + A["agent"]) + x["kg"] * A["ship"]) * (1 + A["customs"])
        net = sell / (1 + A["vat"])
        noon_profit = net - landed - max(1, pct * sell) - fbn - sell * (A["ads"] + A["ret"])
        daily = max(0.3, min(12, num(x.get("ksa_daily_est"), 2) or 2))
        img = ev.get("img") if ev.get("img_score", 0) >= 0.5 else ""
        img = img or (x.get("img") or "")
        p = dict(
            ar=x["ar"], en=x["en"], cat=x["cat"], type=x.get("type") if x.get("type") in ("weak_comp", "us_gap", "improve") else "weak_comp",
            problem=x.get("problem", ""), price=sell, usd=round(usd, 2), usd_agent=x["buy_usd"], cost_src=cost_src,
            mic_usd=ev.get("mic_usd"), pack=ev.get("pack"), mic_range=ev.get("mic_range", ""), mic_moq=ev.get("mic_moq"), mic_n=ev.get("n_priced", 0), mic_top=ev.get("top", []),
            buy_range=x.get("buy_range", ""), moq=num(x.get("moq")), kg=x["kg"], size=x.get("size") or "صغير",
            comp=int(max(1, min(10, num(x.get("comp_score"), 5)))), top_comp=x.get("top_competitor", ""), subs=x.get("substitutes", ""),
            comp_ev=x.get("comp_evidence", ""), comp_url=x.get("comp_url", ""), demand_ev=x.get("demand_evidence", ""),
            us_units=int(num(x.get("us_monthly_units"))) if num(x.get("us_monthly_units")) else None, demand_url=x.get("demand_url", ""),
            daily=daily, improve=x.get("improvement", ""), review_url=x.get("review_url", ""),
            supplier_url=ev.get("supplier_url") or x.get("supplier_url", ""), img=img, img_title=ev.get("img_title", "") if img == ev.get("img") else "",
            cert=x.get("cert") or "لا", season=x.get("season") or "طوال السنة", conf=x.get("confidence") if x.get("confidence") in ("verified", "partial", "estimate") else "estimate",
            pct=pct, fbn=fbn, amz_pct=AMZ.get(letter, 0.15), amz_fee=fbn + 1.0, mult=round(mult, 2), noon_margin=noon_profit / net)
        (prods if mult >= 4 else fail4).append(p)
    for p in prods:
        p["score"] = score(p)
    prods.sort(key=lambda p: -p["score"])
    json.dump([{"en": p["en"], "price": p["price"]} for p in prods], open(os.path.join(work, "amz_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("pass 4x:", len(prods), "fail 4x:", len(fail4), "(verified cost fails:", sum(1 for p in fail4 if p["cost_src"] == "mic"), ")")
    top = prods[:N]
    for i, p in enumerate(top):
        p["id"] = 1001 + i
        p["rank"] = i + 1
        del p["noon_margin"]
    from collections import Counter
    print("selected", len(top), Counter(p["type"] for p in top), Counter(p["cost_src"] for p in top), "img", sum(1 for p in top if p["img"]))
    print(Counter(p["cat"] for p in top))
    notice = ("تنبيه: سعر الشراء لكل منتج «موثّق من المورد» هو متوسط أسعار قوائم مطابقة على Made-in-China (جُمعت أكتوبر 2026)، والباقي تقدير. "
              "سعر البيع والمنافسة والمبيعات اليومية تقديرات بحثية من أمازون أمريكا والسعودية ونون وليست أرقام مبيعات فعلية. "
              "رسوم أمازون السعودية تقريبية. افحص كل منتج على نون وأمازون واطلب عينات قبل الشراء.")
    assumptions = dict(fx=FX, agent=0.08, ship=8.0, customs=0.05, vat=0.15, ads=0.08, ret=0.03, target=0.30, ok=0.20, qty=100,
                       prep=2.0, samples=250, launch=600, certcost=1500, salesk=1.0)
    data = dict(assumptions=assumptions, notice=notice, products=top)
    json.dump(data, open(os.path.join(root, "data", "products_1500.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(fail4, open(os.path.join(root, "data", "rejected_4x.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    tpl = open(os.path.join(root, "model", "template_1500.html"), encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(os.path.join(root, "opportunities.html"), "w", encoding="utf-8").write(tpl.replace("__DATA__", payload))
    print("wrote opportunities.html")


if __name__ == "__main__":
    main()
