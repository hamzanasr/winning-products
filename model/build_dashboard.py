# -*- coding: utf-8 -*-
"""Builds index.html from model/template.html and data/products.json.
Run from the repo root:  python model/build_dashboard.py
Images: data/images.json maps product id -> {"img": url}; they are copied into each product as "img"."""
import json, os, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_path = os.path.join(root, "data", "products.json")
img_path = os.path.join(root, "data", "images.json")

d = json.load(open(data_path, encoding="utf-8"))
imgs = json.load(open(img_path, encoding="utf-8")) if os.path.exists(img_path) else {}
for p in d["products"]:
    e = imgs.get(str(p["id"])) or {}
    u = e.get("img") if e.get("score", 1) >= 0.55 else None   # drop weak title matches, the dashboard shows an icon instead
    if u:
        p["img"] = u
    else:
        p.pop("img", None)

json.dump(d, open(data_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
tpl = open(os.path.join(root, "model", "template.html"), encoding="utf-8").read()
payload = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(os.path.join(root, "index.html"), "w", encoding="utf-8").write(tpl.replace("__DATA__", payload))
print("products:", len(d["products"]), "with image:", sum(1 for p in d["products"] if p.get("img")))
