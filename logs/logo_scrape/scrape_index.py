"""Fetch football-logos.cc country pages and build a global logo index.

Output: logs/logo_scrape/index.json  -> list of
    {country, slug, name, svg_hash, svg_url}
"""
import json, re, time, urllib.request, os

BASE = "https://football-logos.cc"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": BASE + "/", "Accept": "text/html,*/*"}

COUNTRIES = [
    "belgium", "czech-republic", "denmark", "england", "france", "germany",
    "greece", "spain", "netherlands", "italy", "switzerland", "austria",
    "norway", "kazakhstan", "turkey", "kosovo", "sweden", "cyprus",
    "azerbaijan", "scotland", "portugal",
]

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "country_html")
os.makedirs(CACHE, exist_ok=True)


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return open(dest, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    open(dest, "w", encoding="utf-8").write(html)
    time.sleep(1.0)
    return html


# split page into per-card blocks; each card carries the data-* attrs + an alt name
CARD_RE = re.compile(r'data-logo-downloads(.*?)(?=data-logo-downloads|$)', re.S)
ATTR = lambda name, blk: (re.search(name + r'="([^"]*)"', blk) or [None, None])[1]
ALT_RE = re.compile(r'alt="([^"]*?)\s*logo"', re.I)


def parse(country, html):
    out = []
    for blk in CARD_RE.findall(html):
        cat = ATTR("data-category-id", blk)
        slug = ATTR("data-logo-id", blk)
        svg = ATTR("data-svg-hash", blk)
        if not (cat and slug and svg):
            continue
        m = ALT_RE.search(blk)
        name = m.group(1).strip() if m else slug
        out.append({
            "country": country, "slug": slug, "name": name, "svg_hash": svg,
            "svg_url": f"https://images.football-logos.cc/{cat}/{slug}.{svg}.svg",
        })
    return out


def main():
    index = []
    for c in COUNTRIES:
        html = fetch(f"{BASE}/{c}/", os.path.join(CACHE, f"{c}.html"))
        cards = parse(c, html)
        print(f"{c}: {len(cards)} logos")
        index.extend(cards)
    json.dump(index, open(os.path.join(HERE, "index.json"), "w"),
              ensure_ascii=False, indent=2)
    print("TOTAL index entries:", len(index))


if __name__ == "__main__":
    main()
