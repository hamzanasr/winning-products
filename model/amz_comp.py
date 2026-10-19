# -*- coding: utf-8 -*-
"""Real Saudi competition from Amazon.sa search results (first page, English UI).
For each product keyword: matching listings, their ratings, stars, prices, sales badges.
Usage: python model/amz_comp.py <in.json> <out.json>   (in = list of {"en", "price"})
Pages are cached in ../amz_cache."""
import json, os, re, sys, time, random, hashlib, statistics, datetime, urllib.request, urllib.parse
TODAY = datetime.date(2026, 10, 19)
from concurrent.futures import ThreadPoolExecutor

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "amz_cache")
os.makedirs(CACHE, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
STOP = {"for", "with", "and", "the", "a", "of", "in", "to", "set", "pcs", "pack", "kit", "new", "pc", "piece", "pieces"}


def toks(s):
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def fetch(kw):
    path = os.path.join(CACHE, hashlib.md5(kw.lower().encode()).hexdigest() + ".html")
    if os.path.exists(path) and os.path.getsize(path) > 30000:
        return open(path, encoding="utf-8", errors="ignore").read()
    if os.environ.get("AMZ_OFFLINE"):
        return None
    url = "https://www.amazon.sa/s?k=" + urllib.parse.quote_plus(kw) + "&language=en_AE"
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html"})
            h = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
            if "s-search-result" in h or "No results for" in h:
                open(path, "w", encoding="utf-8").write(h)
                return h
            time.sleep(8 * (i + 1) + random.random() * 4)   # captcha / throttled
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def num(s):
    s = s.replace(",", "").upper()
    m = 1000 if s.endswith("K") else 1
    try:
        return float(s.rstrip("K+")) * m
    except ValueError:
        return 0


def results(h):
    out = []
    for p in h.split('data-component-type="s-search-result"')[1:]:
        t = re.search(r'<h2[^>]*aria-label="([^"]+)"', p) or re.search(r"<h2[^>]*>.*?<span[^>]*>([^<]+)</span>", p, re.S)
        if not t:
            continue
        pr = re.search(r'class="a-price-whole">([\d,]+)', p)
        rc = re.search(r'aria-label="([\d,]+) ratings?"', p)
        st = re.search(r"(\d(?:\.\d)?) out of 5 stars", p)
        bo = re.search(r"([\d,.]+K?\+?) bought in past month", p)
        asin = re.search(r'data-asin="(\w+)"', p)
        txt = re.sub(r"<[^>]+>", " ", p)
        dl = re.search(r"delivery\s+(Today|Tomorrow|(?:[A-Z][a-z]{2}, )?(\d{1,2}) ([A-Z][a-z]{2}))", txt)
        days = None
        if dl:
            if dl.group(1) in ("Today", "Tomorrow"):
                days = 0 if dl.group(1) == "Today" else 1
            else:
                try:
                    d = datetime.datetime.strptime(f"{dl.group(2)} {dl.group(3)} {TODAY.year}", "%d %b %Y").date()
                    if d < TODAY: d = d.replace(year=TODAY.year + 1)
                    days = (d - TODAY).days
                except ValueError:
                    pass
        out.append(dict(title=t.group(1).replace("&amp;", "&").replace("&quot;", '"'), price=num(pr.group(1)) if pr else None,
                        ratings=int(num(rc.group(1))) if rc else 0, stars=float(st.group(1)) if st else None,
                        bought=int(num(bo.group(1))) if bo else 0, days=days, local=(days is not None and days <= 4), sponsored="Sponsored" in p[:6000], asin=asin.group(1) if asin else ""))
    return out


def analyse(p):
    h = fetch(p["en"])
    if h is None:
        return None
    R = results(h)
    want = toks(p["en"])
    price = p.get("price") or 100
    for r in R:
        r["rel"] = len(want & toks(r["title"])) / max(1, len(want))
    rel = [r for r in R if r["rel"] >= 0.5]
    near = [r for r in R if r["rel"] >= 0.34]          # same job, maybe different design: substitutes
    strong = [r for r in rel if r["ratings"] >= 100]
    big = [r for r in rel if r["ratings"] >= 1000]
    w = lambda L: sum(1 if r["local"] else 0.5 for r in L)
    cheap = [r for r in near if r["price"] and r["price"] < 0.6 * price and r["ratings"] >= 30]
    top = max(rel or near or [{}], key=lambda r: r.get("ratings", 0)) if (rel or near) else None
    prices = [r["price"] for r in rel if r["price"]]
    comp = 1 + min(4, w(strong) * 0.8) + min(3, w(big) * 1.5) + min(2, w(cheap) * 0.5)
    weak_incumbent = bool(strong) and all((r["stars"] or 5) < 4.0 for r in strong)
    return dict(n=len(R), n_rel=len(rel), n_local=sum(1 for r in rel if r['local']), n_strong_local=sum(1 for r in strong if r['local']), n_strong=len(strong), n_big=len(big), n_cheap=len(cheap),
                sum_ratings=sum(r["ratings"] for r in rel), bought=sum(r["bought"] for r in rel),
                comp=int(round(min(10, comp))), weak_incumbent=weak_incumbent,
                med_price=statistics.median(prices) if prices else None, min_price=min(prices) if prices else None,
                top=({k: top[k] for k in ("title", "price", "ratings", "stars", "asin", "local")} if top and top.get("title") else None),
                cheap_top=sorted(({k: r[k] for k in ("title", "price", "ratings")} for r in cheap), key=lambda r: -r["ratings"])[:3])


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    P = json.load(open(src, encoding="utf-8"))
    done = json.load(open(dst, encoding="utf-8")) if os.path.exists(dst) else {}
    todo = [p for p in P if p["en"] not in done]
    print("todo", len(todo), flush=True)
    fails = 0
    with ThreadPoolExecutor(3) as ex:
        for i, (p, r) in enumerate(zip(todo, ex.map(analyse, todo))):
            if r is None:
                fails += 1
            else:
                done[p["en"]] = r
            if i % 50 == 0:
                json.dump(done, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
                print(i, "fails", fails, flush=True)
    json.dump(done, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print("done", len(done), "fails", fails)
