# -*- coding: utf-8 -*-
"""Builds the single dashboard index.html from model/template.html:
  v1 = data/products.json     (the original 890, mostly estimated)
  v2 = data/products_v2.json  (711 measured, 50-200 SAR)
  v3 = data/products_v3.json  (2000 measured, 100-200 SAR)
Images: data/images.json maps an original product id -> {"img": url, "score": s}; weak title matches are dropped.
Run from the repo root:  python model/build_main.py"""
import json, os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load = lambda n: json.load(open(os.path.join(root, "data", n), encoding="utf-8"))


def from_measured(p, tag):
    """Map a measured product onto the original dashboard schema, keeping the measured evidence for the drawer."""
    c = p["comp"]
    return dict(
        id=p["id"], list=tag, ar=p["ar"], en=p["en"], cat=p["cat"], price=p["price"], usd=p["usd"], kg=p["kg"], size=p["size"],
        season=p.get("season") or "طوال السنة", cert=p.get("cert") or "لا", pct=p["pct"], fbn=p["fbn"],
        comp="منخفضة" if c <= 3 else "متوسطة" if c <= 6 else "عالية", comp10=c,
        ps="sa", cs="mic" if p.get("cost_src") == "mic" else "est", n=p.get("mic_n") or 0,
        note=f"النطاق {p['mic_range']}" if p.get("mic_range") else "", us_units=p.get("us_units"), img=p.get("img"),
        problem=p.get("problem") or "", improve=p.get("improve") or "", top_comp=p.get("top_comp") or "", subs=p.get("subs") or "",
        comp_ev=p.get("comp_ev") or "", daily=p.get("daily"), review_url=p.get("review_url") or "", supplier_url=p.get("supplier_url") or "",
        comp_url=p.get("comp_url") or "", bundle=p.get("bundle"), mult=p.get("mult"),
    )


v1 = load("products.json")
img_path = os.path.join(root, "data", "images.json")
imgs = json.load(open(img_path, encoding="utf-8")) if os.path.exists(img_path) else {}
P = []
for p in v1["products"]:
    e = imgs.get(str(p["id"])) or {}
    u = e.get("img") if e.get("score", 1) >= 0.55 else None
    q = dict(p, list="v1")
    if u:
        q["img"] = u
    P.append(q)
for tag, name in (("v2", "products_v2.json"), ("v3", "products_v3.json")):
    P += [from_measured(p, tag) for p in load(name)["products"]]
ids = [p["id"] for p in P]
assert len(ids) == len(set(ids)), "duplicate product ids across lists"

notice = ("هذه الصفحة تجمع كل القوائم (3,601 منتج). القائمتان المقاستان (711 و2000): المنافسة من بحث أمازون السعودية الفعلي، وسعر البيع من متوسط السوق السعودي، "
          "وسعر الشراء من قوائم موردين على Made-in-China، وتفاصيل القياس داخل كل منتج. القائمة الأولى (890): أغلب أسعارها ومنافستها تقديرية، فراجعها قبل الاعتماد عليها. "
          "نون يحظر الفحص الآلي فلم يُقس فيه. اختر القائمة من الأزرار أعلى النتائج.")
data = dict(assumptions=v1["assumptions"], notice=notice, products=P)
tpl = open(os.path.join(root, "model", "template.html"), encoding="utf-8").read()
html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
for out in ("index.html",):
    open(os.path.join(root, out), "w", encoding="utf-8").write(html)
print("products:", len(P), {k: sum(1 for p in P if p["list"] == k) for k in ("v1", "v2", "v3")})
