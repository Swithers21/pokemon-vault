"""One-off: how PriceCharting's long set pages continue past the first 150 cards."""
import re, time, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; PokemonVaultResearch/1.0; +https://github.com/Swithers21/pokemon-vault)"

def get(url, limit=4000000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read(limit).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read(500).decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return 0, "ERR %s" % e

base = "https://www.pricecharting.com/console/pokemon-chinese-csv8c"
st, page = get(base)
ids = re.findall(r'<tr id="product-(\d+)"', page)
print("base status", st, "rows", len(ids), "first", ids[:2], "last", ids[-2:])
end = page.rfind("</tr>")
print("--- after last row ---")
print(re.sub(r"\s+", " ", page[end:end + 2500]))
print("--- words ---")
for w in ("cursor", "next", "more", "pagination", "page"):
    for m in list(re.finditer(w, page, re.I))[:0]:
        pass
for m in re.finditer(r'[^<>]{0,120}(?:cursor|js-next|load-more|loadMore|next-page|nextPage|\?page|&page|offset)[^<>]{0,160}', page, re.I):
    print(re.sub(r"\s+", " ", m.group(0))[:300])
    break
hits = [re.sub(r"\s+", " ", m.group(0))[:260] for m in re.finditer(r'[^<>]{0,100}(?:cursor|nextPage|next_page|load more|loadMore)[^<>]{0,160}', page, re.I)]
print("hit count", len(hits)); print("\n".join(hits[:8]))
for q in ("?cursor=150", "?cursor=151", "?offset=150", "?page=2", "?sort=name&cursor=150"):
    time.sleep(1.3)
    s2, p2 = get(base + q)
    i2 = re.findall(r'<tr id="product-(\d+)"', p2)
    print(q, "status", s2, "rows", len(i2), "first", i2[:2], "same-as-base-first:", bool(i2 and ids and i2[0] == ids[0]))
