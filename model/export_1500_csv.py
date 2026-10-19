# -*- coding: utf-8 -*-
"""Writes data/opportunities_1500.csv (Excel-friendly, UTF-8 BOM) with the default assumptions."""
import csv, json, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(root, "data", "products_v2.json"), encoding="utf-8"))
A, P = D["assumptions"], D["products"]
TYPES = {"weak_comp": "منافسة ضعيفة", "us_gap": "رائج في أمريكا وغائب في السعودية", "improve": "فرصة تحسين", "mid_comp": "منافسة متوسطة"}
SRC = {"mic": "Made-in-China موثّق", "est_mic_lower": "تقدير (قوائم المورد أرخص)", "est": "تقدير"}
rows = []
for p in P:
    f = p["usd"] * A["fx"] * (1 + A["agent"]); sh = p["kg"] * A["ship"]; landed = (f + sh) * (1 + A["customs"])
    net = p["price"] / (1 + A["vat"]); var = p["price"] * (A["ads"] + A["ret"])
    pn = net - landed - max(1, p["pct"] * p["price"]) - p["fbn"] - var
    pa = net - landed - max(1, p["amz_pct"] * p["price"]) - p["amz_fee"] - var
    cert = 0 if p["cert"] == "لا" else A["certcost"]
    budget = landed * A["qty"] + A["prep"] * A["qty"] + A["samples"] + A["launch"] + cert
    rows.append({"الترتيب": p["rank"], "التقييم /100": p["score"], "المنتج": p["ar"], "كلمة البحث": p["en"], "الفئة": p["cat"], "النوع": TYPES[p["type"]],
                 "المشكلة التي يحلها": p["problem"], "سعر الشراء $": p["usd"], "سعر الشراء ر.س": round(p["usd"] * A["fx"], 2), "مصدر سعر الشراء": SRC[p["cost_src"]],
                 "سعر البيع ر.س": p["price"], "المضاعف": p["mult"], "ربح نون/قطعة": round(pn, 2), "هامش نون": round(pn / net, 3),
                 "ربح أمازون/قطعة": round(pa, 2), "هامش أمازون": round(pa / net, 3), "المنافسة /10": p["comp"], "أكبر منافس": p["top_comp"], "البدائل المشابهة": p["subs"],
                 "التحسين المقترح من التعليقات": p["improve"], "بيع يومي متوقع": p["daily"], "ميزانية تجربة 100 قطعة ر.س": round(budget),
                 "أيام بيع 100 قطعة": round(A["qty"] / p["daily"]), "ربح شهري متوقع ر.س": round((pn + pa) / 2 * p["daily"] * 30),
                 "الوزن كجم": p["kg"], "الحجم": p["size"], "الشهادات": p["cert"], "الموسم": p["season"], "طلب أمريكي/شهر": p["us_units"] or "",
                 "رابط المورد": p["supplier_url"], "رابط الصورة": p["img"], "رابط المنافس": p["comp_url"], "مصدر الطلب": p["demand_url"], "مصدر التعليقات": p["review_url"],
                 "ثقة البيانات": {"verified": "موثّق", "partial": "جزئي", "estimate": "تقدير"}[p["conf"]]})
with open(os.path.join(root, "data", "opportunities_v2.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("rows", len(rows))
