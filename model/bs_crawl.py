# -*- coding: utf-8 -*-
"""Crawls Amazon Best Sellers trees (amazon.com and amazon.sa) for the allowed departments.
Usage: python model/bs_crawl.py <com|sa> <out.json> [max_nodes]
Output: {asin: {title, price_sar, ratings, stars, rank, node, path, img, site}}"""
import json, os, re, sys, time, random, hashlib, urllib.request
from concurrent.futures import ThreadPoolExecutor

SITE = sys.argv[1]
LIST = os.environ.get("BS_LIST", "bestsellers")   # bestsellers | new-releases
NAVREF = {"bestsellers": "zg_bs_nav_", "new-releases": "zg_bsnr_nav_"}[LIST]
HOST = {"com": "https://www.amazon.com", "sa": "https://www.amazon.sa"}[SITE]
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bs_cache")
os.makedirs(CACHE, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
ROOTS = ["home-garden", "kitchen", "sporting-goods", "automotive", "pet-supplies", "toys-and-games", "office-products", "hi", "lawn-garden",
         "wireless", "electronics", "arts-crafts", "videogames", "fashion/9479199011", "baby-products"]
if SITE == "sa":
    ROOTS = ["home", "automotive", "home-improvement", "electronics", "office-products", "garden", "pet-supplies", "sports-goods", "toys", "videogames", "baby-products"]
SKIP = re.compile(r"Beauty|Health|Grocery|Food|Vitamin|Supplement|Medical|Fragrance|Perfume|Skin|Hair|Makeup|Shav|Oral|Diaper|Feeding|Nursing|"
                  r"Televisions|Laptops|Computers$|Tablets$|Cell Phones$|Drones|Batteries|Power Banks|Headphones$|Cameras$|Clothing|Shoes|Jewelry|Watches$|"
                  r"Knives$|Firearm|Gun|Ammo|Hunting|Tobacco|Vape|Books|Movies|Music|Software|Appliances$|Furniture$|Mattress|Large", re.I)


def fetch(url):
    path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".html")
    if os.path.exists(path) and os.path.getsize(path) > 20000:
        return open(path, encoding="utf-8", errors="ignore").read()
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html"})
            h = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
            if "p13n-sc-uncoverable-faceout" in h or "zg_bs" in h:
                open(path, "w", encoding="utf-8").write(h)
                return h
            time.sleep(6 * (i + 1) + random.random() * 3)
        except Exception:
            time.sleep(4 * (i + 1))
    return ""


def items(h, node, path):
    out = []
    for m in re.finditer(r'id="p13n-asin-index-(\d+)".*?data-asin="(\w+)"', h, re.S):
        rank, asin = int(m.group(1)) + 1, m.group(2)
        seg = h[m.end():m.end() + 6000]
        t = re.search(r'line-clamp-\d[^"]*">([^<]+)<', seg) or re.search(r'<img alt="([^"]+)"', seg)
        r = re.search(r'aria-label="([\d.]+) out of 5 stars, ([\d,]+) ratings"', seg)
        p = re.search(r'p13n-sc-price[^"]*">\s*(?:SAR|\$|USD)\s*([\d,.]+)', seg)
        cur = re.search(r'p13n-sc-price[^"]*">\s*(SAR|\$|USD)', seg)
        img = re.search(r'src="(https://images-na\.ssl-images-amazon\.com/images/I/[^"]+)"', seg) or re.search(r'src="(https://m\.media-amazon\.com/images/I/[^"]+)"', seg)
        price = float(p.group(1).replace(",", "")) if p else None
        if price is not None and cur and cur.group(1) in ("$", "USD"):
            price *= 3.75
        out.append(dict(asin=asin, title=(t.group(1).strip() if t else "").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"'),
                        price_sar=round(price, 1) if price else None, stars=float(r.group(1)) if r else None,
                        ratings=int(r.group(2).replace(",", "")) if r else 0, rank=rank, node=node, path=path,
                        img=img.group(1) if img else "", site=SITE))
    return out


def children(h):
    out = []
    for u, name in re.findall(r'href="(/(?:[^"]*?/)?(?:zgbs|gp/bestsellers|gp/new-releases)/[^"]+?)/ref=' + NAVREF + r'[^"]*"[^>]*>([^<]{2,80})<', h):
        name = name.replace("&amp;", "&").strip()
        if not SKIP.search(name):
            out.append((u, name))
    return out


def crawl(max_nodes):
    seen, queue, data = set(), [], {}
    for r in ROOTS:
        queue.append((("/-/en" if SITE == "sa" else "") + "/gp/" + LIST + "/" + r + ("?language=en_AE" if SITE == "sa" else ""), r, 0))
    done = 0
    with ThreadPoolExecutor(3) as ex:
        while queue and done < max_nodes:
            batch, queue = queue[:12], queue[12:]
            batch = [b for b in batch if b[0] not in seen]
            for b in batch:
                seen.add(b[0])
            pages = list(ex.map(lambda b: (b, fetch(HOST + b[0]), fetch(HOST + b[0] + ("&" if "?" in b[0] else "?") + "pg=2")), batch))
            for (u, path, depth), h1, h2 in pages:
                done += 1
                for it in items(h1, u, path) + items(h2, u, path):
                    old = data.get(it["asin"])
                    if not old or it["rank"] < old["rank"]:
                        data[it["asin"]] = it
                if depth < 3:
                    for cu, name in children(h1):
                        if cu not in seen:
                            queue.append((cu, path + " > " + name, depth + 1))
            print("nodes", done, "queue", len(queue), "items", len(data), flush=True)
    return data


if __name__ == "__main__":
    out = sys.argv[2]
    d = crawl(int(sys.argv[3]) if len(sys.argv) > 3 else 900)
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("saved", len(d))
