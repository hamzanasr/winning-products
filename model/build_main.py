# -*- coding: utf-8 -*-
"""Builds the main page index.html with every list in one dashboard:
  v1 = data/products.json     (the original 890, mostly estimated)
  v2 = data/products_v2.json  (711 measured, 50-200 SAR)
  v3 = data/products_v3.json  (2000 measured, 100-200 SAR)
Run from the repo root:  python model/build_main.py"""
import json, math, os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load = lambda n: json.load(open(os.path.join(root, "data", n), encoding="utf-8"))

COMP = {"منخفضة": (3, "منخفضة"), "متوسطة": (5, "متوسطة"), "عالية": (8, "عالية")}


def from_v1(p):
    """Map an original-list product onto the measured-list schema. Its competition was judged by hand or not at all."""
    comp, lbl = COMP.get(p.get("comp"), (6, "لم تُفحص"))
    us = p.get("us_units") or 0
    daily = max(0.5, min(3.0, 0.6 + 0.9 * math.log10(us / 300))) if us > 300 else 1.0
    mic = p.get("cs") == "mic"
    return dict(
        id=p["id"], list="v1", ar=p["ar"], en=p["en"], cat=p["cat"], type="original", problem="",
        price=p["price"], usd=p["usd"], cost_src="mic" if mic else "est", mic_usd=p["usd"] if mic else None, pack=None,
        mic_range=p.get("rng") or "", mic_moq=None, mic_n=1 if mic else 0, mic_top=[], usd_agent=p["usd"], buy_range=p.get("rng") or "",
        kg=p["kg"], size=p["size"], comp=comp, comp_lbl=lbl + " (تقدير)",
        top_comp=p.get("sa_evidence") or "لم تُقس المنافسة على أمازون السعودية لهذا المنتج",
        subs="", comp_ev=("سعر البيع " + ("مأخوذ من نون" if p.get("ps") == "real" else "تقديري")) + (f" · {p['note']}" if p.get("note") else ""),
        comp_url="", demand_ev=" · ".join(x for x in [p.get("demand"), p.get("note2"), p.get("us_source")] if x), us_units=us or None,
        us_ratings=None, us_rank=None, demand_url="", daily=round(daily, 1), daily_src="us_demand" if us else "default",
        improve="", review_url="", supplier_url="", img=p.get("img"), img_title="", cert=p["cert"], season=p["season"],
        conf="partial" if p.get("ps") == "real" or mic else "estimate", pct=p["pct"], fbn=p["fbn"], amz_pct=0.15, amz_fee=p["fbn"] + 1.0,
        rank=None,
    )


v1, v2, v3 = load("products.json"), load("products_v2.json"), load("products_v3.json")
P = [from_v1(p) for p in v1["products"]]
for tag, d in (("v2", v2), ("v3", v3)):
    for p in d["products"]:
        P.append(dict(p, list=tag))
ids = [p["id"] for p in P]
assert len(ids) == len(set(ids)), "duplicate product ids across lists"

notice = ("هذه الصفحة تجمع كل القوائم. القائمتان المقاستان (711 و2000): المنافسة من بحث أمازون السعودية الفعلي، وسعر البيع من متوسط السوق السعودي، "
          "وسعر الشراء من قوائم موردين على Made-in-China. القائمة الأولى (890): أغلب أسعارها ومنافستها تقديرية، فراجعها قبل الاعتماد عليها. "
          "نون يحظر الفحص الآلي فلم يُقس فيه. المبيعات اليومية تقدير متحفظ لبائع جديد. اختر القائمة من القائمة المنسدلة.")
data = dict(assumptions=v3["assumptions"], notice=notice, products=P)
tpl = open(os.path.join(root, "model", "template_main.html"), encoding="utf-8").read()
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(tpl.replace("__DATA__", payload))
print("index.html:", len(P), {k: sum(1 for p in P if p["list"] == k) for k in ("v1", "v2", "v3")})
