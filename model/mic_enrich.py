# -*- coding: utf-8 -*-
"""Supplier evidence from public Made-in-China.com search pages.
For each product keyword: listing titles, links, images, unit prices and MOQ.
Usage: python model/mic_enrich.py <in.json> <out.json>   (in = list of products with "en")
Pages are cached in ../mic_cache so reruns are cheap."""
import json, os, re, sys, time, statistics, hashlib, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "mic_cache")
os.makedirs(CACHE, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
STOP = {"for", "with", "and", "the", "a", "of", "in", "to", "set", "pcs", "piece", "pack", "kit", "new", "hot", "sale", "china", "custom", "wholesale", "factory"}


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def fetch(kw):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", kw).strip("_")
    path = os.path.join(CACHE, hashlib.md5(slug.encode()).hexdigest() + ".html")
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        return open(path, encoding="utf-8", errors="ignore").read()
    url = "https://www.made-in-china.com/products-search/hot-china-products/" + urllib.parse.quote(slug) + ".html"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
            h = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
            open(path, "w", encoding="utf-8").write(h)
            return h
        except Exception:
            time.sleep(3 * (i + 1))
    return ""


def listings(h):
    """Parses both search-page layouts. Images are matched to a listing by the product slug in the image file name."""
    out = []
    heads = list(re.finditer(r'<h2 class="product-name"[^>]*>\s*(<a [^>]*>)', h))
    for i, m in enumerate(heads):
        a = m.group(1)
        href = re.search(r'href="([^"]+)"', a); title = re.search(r'title="([^"]*)"', a)
        if not href:
            continue
        href = href.group(1).split("#")[0]
        title = (title.group(1) if title else "").replace("&amp;", "&").replace("&quot;", '"')
        end = heads[i + 1].start() if i + 1 < len(heads) else m.end() + 6000
        after = h[m.end():min(end, m.end() + 2500)]
        pm = re.search(r'US\s?\$\s*(?:</span>\s*)?<span>([\d.,]+)</span>(?:\s*-\s*<span>([\d.,]+)</span>)?', after)
        mm = (re.search(r'<span>\s*([\d,]+)\s*([A-Za-z]+)\s*</span>\s*(?:</span>\s*)?<span class="moq-text">', after)
              or re.search(r'Min\. Order:</strong>\s*([\d,]+)\s*([A-Za-z]+)', after))
        lo = float(pm.group(1).replace(",", "")) if pm else None
        hi = float(pm.group(2).replace(",", "")) if pm and pm.group(2) else lo
        slug = re.search(r"/China-([^/]+)\.html", href)
        slug = slug.group(1).lower() if slug else ""
        win = h[max(0, m.start() - 6000):min(end + 200, m.end() + 8000)]
        img = ""
        for u in re.findall(r'(?:data-original|src)="(https://image\.made-in-china\.com/[^"]+)"', win):
            f = u.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
            if slug and (f == slug or f[:40] == slug[:40]):
                img = u if not img or "2f1j00" in u else img
        out.append(dict(title=title, url=href, img=img, lo=lo, hi=hi,
                        moq=int(mm.group(1).replace(",", "")) if mm else None, unit=mm.group(2) if mm else ""))
    return out


def short_kw(kw):
    w = [x for x in re.findall(r"[A-Za-z]+", kw) if x.lower() not in STOP and len(x) > 2]
    return " ".join(w[:4])


def evidence(p):
    want = toks(p["en"])
    def scored(kw):
        L = listings(fetch(kw))
        for x in L:
            x["score"] = len(want & toks(x["title"])) / max(1, len(want))
        return L, [x for x in L if x["score"] >= 0.5] or [x for x in L if x["score"] >= 0.34]
    L, good = scored(p["en"])
    if len(good) < 3 and short_kw(p["en"]).lower() != p["en"].lower():
        L2, good2 = scored(short_kw(p["en"]))
        if len(good2) > len(good):
            L, good = L2, good2
    good.sort(key=lambda x: -x["score"])
    priced = [x for x in good[:10] if x["score"] >= 0.5 and x["lo"] and 0.05 <= x["lo"] <= 500 and (x["unit"] or "").lower().startswith(("piece", "set", "pair", "unit", "pc"))]
    mid = None
    if priced:
        mids = sorted((x["lo"] + x["hi"]) / 2 for x in priced)
        med = statistics.median(mids)
        mids = [v for v in mids if med / 4 <= v <= med * 4]
        mid = round(statistics.median(mids), 2)
    best = next((x for x in good if x["img"]), None)
    return dict(n_listings=len(L), n_match=len(good), n_priced=len(priced), mic_usd=mid,
                mic_range=f"{min(x['lo'] for x in priced):.2f}–{max(x['hi'] for x in priced):.2f}" if priced else "",
                mic_moq=int(statistics.median([x["moq"] for x in priced if x["moq"]])) if any(x["moq"] for x in priced) else None,
                img=best["img"] if best else "", img_title=best["title"] if best else "", img_score=round(best["score"], 2) if best else 0,
                supplier_url=best["url"] if best else "", top=[{k: x[k] for k in ("title", "url", "lo", "hi", "moq")} for x in priced[:3]])


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    P = json.load(open(src, encoding="utf-8"))
    done = json.load(open(dst, encoding="utf-8")) if os.path.exists(dst) else {}
    todo = [p for p in P if p["en"] not in done]
    print("todo", len(todo), flush=True)
    with ThreadPoolExecutor(6) as ex:
        for i, (p, ev) in enumerate(zip(todo, ex.map(evidence, todo))):
            done[p["en"]] = ev
            if i % 50 == 0:
                json.dump(done, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
                print(i, flush=True)
    json.dump(done, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print("done", len(done), "with price", sum(1 for v in done.values() if v["mic_usd"]), "with img", sum(1 for v in done.values() if v["img"]))
