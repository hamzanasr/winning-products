# -*- coding: utf-8 -*-
"""Opportunity list v3 (selling price 100–200 SAR): same measured method as v2, new products only.
Sources: Amazon US best sellers (data/bs_com.json) normalized to generic products (../norm_out/*.jsonl),
plus round-1/2 research candidates (../out/*.json).
Per product: supplier price (Made-in-China, data/mic_1500.json), Saudi competition and Saudi price/sales
(Amazon.sa search, data/amz_comp.json), US demand (best-seller rank and ratings).
Run:  python model/build_v2.py --prep     -> ../v2_candidates.json (input for mic_enrich.py and amz_comp.py)
      python model/build_v2.py            -> data/products_v2.json + opportunities.html"""
import json, os, re, sys, glob, gzip, math, statistics
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fees import commission_rate, fbn_fee
from build_1500 import CATS, AMZ, BANNED, toks, jacc, pack_count, listing_is_pack

# medical / personal care / weapons / veterinary injection gear that slipped past BANNED
V3_BANNED = re.compile(r"\b(syringe|drench|respirator|n95|cpr|choking|speargun|rifle|hair|oximeter|pulse|stethoscope|first aid|bandage|tourniquet|headgear|snow chains|aerosol|fixative|seeds?|gas regulator|thermostat|sword|wine|roulette|matches|spray paint|lube spray|head guard|desert gauge|desert kit)\b", re.I)

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = os.path.dirname(root)
FX = 3.75
N = 2000
MIN_SELL = 100
MAX_MULT = 20
REVIEW_MULT = 10          # above this, a supplier match must be reviewed (data/cost_fix_v3.json) or the product is dropped
TYPES = ("weak_comp", "us_gap", "improve")


def load_candidates():
    bs = {}
    for name in ("bs_sa.json", "nr_com.json", "bs_com.json"):
        bp = os.path.join(root, "data", name)
        if os.path.exists(bp):
            bs.update(json.load(open(bp, encoding="utf-8")))
        elif os.path.exists(bp + ".gz"):
            bs.update(json.load(gzip.open(bp + ".gz", "rt", encoding="utf-8")))
    C = []
    for f in sorted(glob.glob(os.path.join(work, "norm_out2", "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            try:
                x = json.loads(line)
            except Exception:
                continue
            b = bs.get(x.get("asin"), {})
            if not x.get("en") or x.get("cat") not in CATS:
                continue
            C.append(dict(en=x["en"].strip(), ar=x.get("ar", ""), cat=x["cat"], kg=float(x.get("kg") or 0.5), size=x.get("size") or "صغير",
                          problem=x.get("problem", ""), src=("sa_bestseller" if b.get("site") == "sa" else "us_new_release" if "new" in b.get("node", "") else "us_bestseller"), asin=x.get("asin"), us_price=b.get("price_sar"), us_ratings=b.get("ratings", 0),
                          us_rank=b.get("rank"), us_stars=b.get("stars"), us_path=b.get("path", ""), us_title=b.get("title", ""), us_img=b.get("img", ""),
                          agent_usd=None, improve="", review_url=""))
    for f in sorted(glob.glob(os.path.join(work, "out3", "*.json"))):
        for x in json.load(open(f, encoding="utf-8")):
            if not x.get("en") or not x.get("problem"):
                continue
            C.append(dict(en=x["en"].strip(), ar=x.get("ar", ""), cat=x.get("cat") if x.get("cat") in CATS else "المنزل والمطبخ",
                          kg=float(x.get("kg") or 0.5), size=x.get("size") or "صغير", problem=x.get("problem", ""), src="research100",
                          asin=None, us_price=None, us_ratings=int(x.get("us_monthly_units") or 0) and 0, us_rank=None, us_stars=None, us_path="", us_title="", us_img="",
                          agent_usd=float(x["buy_usd"]) if x.get("buy_usd") else None, agent_sell=x.get("sell_sar"),
                          improve=x.get("improvement", ""), review_url=x.get("review_url", "")))
    ar_fix_p = os.path.join(root, "data", "ar_fix_v3.json")
    if os.path.exists(ar_fix_p):
        ar_fix = json.load(open(ar_fix_p, encoding="utf-8"))
        for c in C:
            if c["en"] in ar_fix:
                c["ar"] = ar_fix[c["en"]]
    existing = [toks(l) for l in open(os.path.join(work, "existing", "ALL.txt"), encoding="utf-8").read().splitlines() if l.strip()]
    existing += [toks(p["en"]) for p in json.load(open(os.path.join(root, "data", "products_v2.json"), encoding="utf-8"))["products"]]
    C.sort(key=lambda c: -(c["us_ratings"] or 0))            # keep the best-documented version of duplicates
    keep, seen = [], []
    for c in C:
        if c["kg"] > 3 or BANNED.search(c["en"]) or V3_BANNED.search(c["en"]):
            continue
        t = toks(c["en"])
        if not t or any(jacc(t, e) >= 0.75 for e in existing) or any(jacc(t, s) >= 0.75 for s in seen):
            continue
        seen.append(t)
        keep.append(c)
    return keep


def daily_estimate(c, az):
    """Units/day for a new seller on Noon + Amazon.sa. Real Saudi sales badges when shown, else US demand scaled."""
    share = 0.35 if az["comp"] <= 3 else 0.2 if az["comp"] <= 5 else 0.1
    if az.get("bought"):
        return max(0.3, min(10, az["bought"] / 30 * share)), "sa_sales"
    r = c["us_ratings"] or 0
    if r:
        return max(0.5, min(5, 0.6 + 0.9 * math.log10(max(1, r / 300)))), "us_demand"
    base = 1.0 + 0.4 * min(5, az.get("n_rel", 0) / 10)
    return max(0.5, min(3, base)), "sa_listings"


def main():
    cands = load_candidates()
    print("candidates after dedupe:", len(cands), Counter(c["src"] for c in cands))
    if "--prep" in sys.argv:
        out = [{"en": c["en"], "price": int(min(200, max(100, c["us_price"] or 120)))} for c in cands]
        json.dump(out, open(os.path.join(work, "v3_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("written", len(out)); return
    mic = json.load(open(os.path.join(root, "data", "mic_1500.json"), encoding="utf-8"))
    # manual review of implausible supplier matches: {en: {"usd": cost of one sold unit or null, "verdict": ok|fixed|estimated|reject, "why": ...}}
    cfp = os.path.join(root, "data", "cost_fix_v3.json")
    cost_fix = json.load(open(cfp, encoding="utf-8")) if os.path.exists(cfp) else {}
    # rewritten Arabic name / problem for entries whose text was too thin: {en: {"ar": ..., "problem": ...}}
    tfp = os.path.join(root, "data", "text_fix_v3.json")
    text_fix = json.load(open(tfp, encoding="utf-8")) if os.path.exists(tfp) else {}
    amz = json.load(open(os.path.join(root, "data", "amz_comp.json"), encoding="utf-8"))
    why, P = Counter(), []
    for c in cands:
        ev, az = mic.get(c["en"]), amz.get(c["en"])
        if not ev or not az:
            why["not measured"] += 1; continue
        if az.get("n", 0) < 10:
            why["suspicious Amazon.sa page (re-measure)"] += 1; continue
        # selling price: the Saudi market price (median of matching Amazon.sa listings), else the US price
        sa_med = az.get("med_price")
        ref = sa_med if sa_med and az.get("n_rel", 0) >= 3 else (c["us_price"] or c.get("agent_sell"))
        if not ref:
            why["no price reference"] += 1; continue
        sell = round(min(200, ref * 0.95 if sa_med else ref))
        bundle = 1
        if sell < MIN_SELL:
            # cheap in Saudi: offer a bundle of k units at 10% below k single prices, if that reaches 50 SAR
            single = ref * 0.95 if sa_med else ref
            k = int(-(-MIN_SELL // (single * 0.9))) if single > 0 else 99
            if not (sa_med and max(2, k) <= 2):
                why["market price under 100"] += 1; continue
            bundle = max(2, k)
            sell = round(min(200, single * bundle * 0.9))
        # purchase price: supplier median (pack-adjusted), never below the researcher's estimate
        n = pack_count(c["en"], c["ar"])
        has_mic = ev.get("mic_usd") and ev.get("n_priced", 0) >= 3
        mic_usd = ev["mic_usd"] * (n if has_mic and n > 1 and not any(listing_is_pack(t.get("title") or "", n) for t in ev.get("top", [])) else 1) if has_mic else None
        usd = max(x for x in (mic_usd, c["agent_usd"]) if x) if (mic_usd or c["agent_usd"]) else None
        fx = cost_fix.get(c["en"])
        if fx:
            if fx.get("verdict") == "reject" or not fx.get("usd"):
                why["supplier match rejected on review"] += 1; continue
            if fx["verdict"] != "ok":
                usd, mic_usd = max(fx["usd"], usd or 0), (None if fx["verdict"] == "estimated" else fx["usd"])
        elif usd and sell / (usd * (bundle if bundle > 1 else 1) * FX) > REVIEW_MULT:
            why["implausible cost, not reviewed"] += 1; continue
        if usd and bundle > 1:
            usd *= bundle
        if not usd:
            why["no supplier price"] += 1; continue
        mult = sell / (usd * FX)
        if mult < 4:
            why["under 4x"] += 1; continue
        if mult > MAX_MULT:                # too good to be true: mismatched listing or overpriced imported stock
            why["multiple above %dx (unreliable)" % MAX_MULT] += 1; continue
        comp = az["comp"]
        weak_inc = az.get("weak_incumbent")
        if comp <= 4:
            typ = "us_gap" if az.get("n_rel", 0) <= 5 and (c["us_ratings"] or 0) >= 1000 else "weak_comp"
        elif comp <= 7 and (weak_inc or c["improve"]):
            typ = "improve"
        elif comp <= 6:
            typ = "mid_comp"
        else:
            why["competition too strong"] += 1; continue
        letter = CATS[c["cat"]]
        cc = {"en": c["en"].lower(), "cat": letter, "kg": c["kg"], "size": "S" if c["size"] == "صغير" else "M"}
        pct, fbn = commission_rate(cc, sell), fbn_fee(cc, sell)
        landed = (usd * FX * 1.08 + c["kg"] * 8) * 1.05
        net = sell / 1.15
        pn = net - landed - max(1, pct * sell) - fbn - sell * 0.11
        daily, dsrc = daily_estimate(c, az)
        top = az.get("top") or {}
        tf = text_fix.get(c["en"]) or {}
        if tf.get("ar"):
            c = dict(c, ar=tf["ar"])
        if tf.get("problem"):
            c = dict(c, problem=tf["problem"])
        img = c["us_img"] or (ev.get("img") if ev.get("img_score", 0) >= 0.5 else "")
        P.append(dict(
            ar=c["ar"] + (f" (طقم {bundle} قطع)" if bundle > 1 else ""), en=c["en"], bundle=bundle if bundle > 1 else None, cat=c["cat"], type=typ, problem=c["problem"], price=sell, usd=round(usd, 2), cost_src="mic" if mic_usd else "est",
            mic_usd=ev.get("mic_usd"), pack=n if n > 1 else None, mic_range=ev.get("mic_range", ""), mic_moq=ev.get("mic_moq"), mic_n=ev.get("n_priced", 0), mic_top=ev.get("top", []),
            usd_agent=c["agent_usd"], buy_range="", kg=c["kg"], size=c["size"], comp=comp,
            top_comp=(f"{top.get('title','')[:70]} — {top.get('price') or '?'} ريال، {top.get('ratings',0):,} تقييم{'، مخزون محلي' if top.get('local') else '، مستورد'}" if top else "لا يوجد منافس مطابق على أمازون السعودية"),
            subs=("بدائل أرخص: " + "؛ ".join(f"{s['title'][:45]} {s['price']} ريال ({s['ratings']} تقييم)" for s in az.get("cheap_top", []))) if az.get("cheap_top") else "لا توجد بدائل أرخص راسخة",
            comp_ev=f"أمازون السعودية: {az.get('n_rel',0)} عرض مطابق ({az.get('n_local',0)} بمخزون محلي)، {az.get('n_strong',0)} بائع قوي (+100 تقييم) منهم {az.get('n_strong_local',0)} محلي، {az.get('n_big',0)} كبير (+1000)، {az.get('n_cheap',0)} بديل أرخص. متوسط السعر {sa_med or '—'} ريال." + (f" مبيعات ظاهرة ≈{az['bought']}/شهر." if az.get('bought') else ""),
            comp_url="https://www.amazon.sa/s?k=" + c["en"].replace(" ", "+"),
            demand_ev=(f"أمريكا: #{c['us_rank']} في الأكثر مبيعًا ({c['us_path']})، {c['us_ratings']:,} تقييم، السعر {c['us_price']} ريال." if c["us_rank"] else "من بحث الوكلاء.") + (f" «{c['us_title'][:90]}»" if c["us_title"] else ""),
            us_units=None, us_ratings=c["us_ratings"], us_rank=c["us_rank"], demand_url=(f"https://www.amazon.com/dp/{c['asin']}" if c["asin"] else ""),
            daily=round(daily, 1), daily_src=dsrc, improve=c["improve"] or (f"المنافسون الأقوياء تقييمهم أقل من 4 نجوم ({top.get('stars')}) — راجع تعليقاتهم السلبية وحسّن العيوب المتكررة." if weak_inc else ""),
            review_url=c["review_url"] or (f"https://www.amazon.sa/dp/{top['asin']}" if top.get("asin") else ""),
            supplier_url=ev.get("supplier_url", ""), img=img, img_title="", cert="لا", season="طوال السنة",
            conf="verified" if (mic_usd and az.get("n_rel", 0) >= 3) else "partial",
            pct=pct, fbn=fbn, amz_pct=AMZ.get(letter, 0.15), amz_fee=fbn + 1.0, mult=round(mult, 2), _margin=pn / net, sa_med=sa_med, sa_bought=az.get("bought", 0)))
    print("excluded:", dict(why))
    print("qualified:", len(P), Counter(p["type"] for p in P))
    for p in P:
        m = max(0, min(1, (p["_margin"] + 0.05) / 0.45)); cs = (10 - p["comp"]) / 9; d = min(1, p["daily"] / 5)
        dem = min(1, math.log10(max(1, (p["us_ratings"] or 0))) / 4.5) if p["us_ratings"] else 0.3
        p["score"] = round(100 * (0.30 * cs + 0.25 * m + 0.20 * d + 0.15 * dem + 0.10 * min(1, (p["mult"] - 4) / 4)), 1)
    P.sort(key=lambda p: -p["score"])
    if "--dump" in sys.argv:          # whole qualified pool, for the cost / text review
        json.dump(P, open(os.path.join(work, "v3_qualified.json"), "w", encoding="utf-8"), ensure_ascii=False); print("dumped", len(P)); return
    top = P[:N]
    # qualified but not selected: build_v2 fills its gaps from these (they also meet its 50-200 SAR rules)
    json.dump([dict(p, _margin=None) for p in P[N:]], open(os.path.join(work, "v3_spares.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for i, p in enumerate(top):
        p["id"], p["rank"] = 5001 + i, i + 1
        del p["_margin"]
    print("selected", len(top), Counter(p["type"] for p in top), Counter(p["cat"] for p in top).most_common(5))
    notice = ("كل منتج هنا مقاس: المنافسة من بحث أمازون السعودية الفعلي (عدد البائعين وتقييماتهم والمخزون المحلي والبدائل الأرخص)، "
              "وسعر البيع من متوسط سعر السوق السعودي، وسعر الشراء من قوائم موردين على Made-in-China، والطلب من قوائم الأكثر مبيعًا في أمازون أمريكا. "
              "نون يحظر الفحص الآلي فلم يُقس فيه. المبيعات اليومية تقدير مبني على هذه الأرقام.")
    A = dict(fx=FX, agent=0.08, ship=8.0, customs=0.05, vat=0.15, ads=0.08, ret=0.03, target=0.30, ok=0.20, qty=100, prep=2.0, samples=250, launch=600, certcost=1500, salesk=1.0)
    data = dict(assumptions=A, notice=notice, products=top)
    json.dump(data, open(os.path.join(root, "data", "products_v3.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("wrote data/products_v3.json; run model/build_main.py to refresh the dashboard")


if __name__ == "__main__":
    main()
