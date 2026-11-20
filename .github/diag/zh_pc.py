"""One-off: does PriceCharting's API answer browser requests from another website (CORS)? Uses only the demo token printed in their documentation."""
import json, urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; PokemonVaultResearch/1.0; +https://github.com/Swithers21/pokemon-vault)"
DEMO = "c0b53bce27c1bdab90b1605249e600dc43dfd1d5"   # the example token in https://www.pricecharting.com/api-documentation

def call(url, method="GET", headers=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Origin": "https://swithers21.github.io"}, **(headers or {})), method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, dict(r.headers), r.read(3000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), (e.read(1500).decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return 0, {}, "ERR %s" % e

for label, url, method, hd in (
    ("product by id, GET", "https://www.pricecharting.com/api/product?t=%s&id=6910" % DEMO, "GET", None),
    ("products search, GET", "https://www.pricecharting.com/api/products?t=%s&q=earthbound" % DEMO, "GET", None),
    ("products search, preflight", "https://www.pricecharting.com/api/products?t=%s&q=earthbound" % DEMO, "OPTIONS", {"Access-Control-Request-Method": "GET"}),
    ("bad token, GET", "https://www.pricecharting.com/api/products?t=0000&q=earthbound", "GET", None),
):
    st, h, body = call(url, method, hd)
    print("\n=== %s: status %s ===" % (label, st))
    print({k: v for k, v in h.items() if k.lower().startswith(("access-control", "content-type", "vary", "server", "cf-", "allow"))})
    print(body[:900])
