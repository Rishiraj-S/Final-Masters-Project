"""Download the still-missing team logos (ban lifted). Slow + circuit-breaks on 429.

Builds the set from missing_matches.json (>=0.72) minus amateur false-positives,
plus hand overrides for mis-hits. Saves slug.svg into assets/logos/team.
Writes downloaded_missing.json = {data_team_name: slug} for the mapping step.
"""
import json, os, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEAM_DIR = os.path.join(ROOT, "assets", "logos", "team")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://football-logos.cc/",
           "Accept": "image/svg+xml,*/*"}
DELAY = 3.0

mm = json.load(open(os.path.join(HERE, "missing_matches.json"), encoding="utf-8"))
index = json.load(open(os.path.join(HERE, "index.json"), encoding="utf-8"))
idx = {(e["country"], e["slug"]): e for e in index}

# correct country+slug for mis-hits and real low-confidence teams
OVERRIDES = {
    'PAOK Thessaloniki FC': ('greece', 'paok'),
    'Stade Rennais FC': ('france', 'rennes'),
    'Brighton & Hove Albion FC': ('england', 'brighton'),
    'OGC Nice Côte d\'Azur': ('france', 'nice'),
    'PAE APS Atromitos Athens': ('greece', 'atromitos'),
    'Panaitolikos GFS Agrinio': ('greece', 'panetolikos'),
    'Racing Club de Lens': ('france', 'rc-lens'),
    'RasenBallsport Leipzig': ('germany', 'rb-leipzig'),
    'Stade Brestois 29': ('france', 'brest'),
}
# confident-but-wrong (amateur, not really on site) — do not download
SKIP = {'Atlético Palma del Río'}

# assemble final {name: (country, slug, svg_url)}
jobs = {}
for name, rec in mm.items():
    if name in SKIP:
        continue
    if name in OVERRIDES:
        co, sl = OVERRIDES[name]
        e = idx.get((co, sl))
        if not e:
            print(f"  !! override slug not in index: {name} -> {co}/{sl}")
            continue
        jobs[name] = e
    elif rec and rec["score"] >= 0.72:
        jobs[name] = idx[(rec["country"], rec["slug"])]
# add overrides that weren't in mm keys (all are, but be safe)
for name, (co, sl) in OVERRIDES.items():
    if name not in jobs and (co, sl) in idx:
        jobs[name] = idx[(co, sl)]

print(f"to download: {len(jobs)} teams")


def valid(p):
    return os.path.exists(p) and os.path.getsize(p) > 80 and open(p, "rb").read(40).lstrip().startswith(b"<")


downloaded = {}
fresh = fail = cached = 0
banned = False
for name in sorted(jobs):
    e = jobs[name]
    fn = f"{e['slug']}.svg"
    dest = os.path.join(TEAM_DIR, fn)
    if valid(dest):
        downloaded[name] = e["slug"]; cached += 1; continue
    try:
        req = urllib.request.Request(e["svg_url"], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except urllib.error.HTTPError as ex:
        if ex.code == 429:
            print(f"RATE LIMITED at {fn} — stopping"); banned = True; break
        print(f"  FAIL {name} -> {e['svg_url']} (HTTP {ex.code})"); fail += 1; continue
    except Exception as ex:
        print(f"  FAIL {name} ({ex})"); fail += 1; continue
    if not data.lstrip().startswith(b"<") or len(data) < 80:
        print(f"  FAIL {name} not-svg ({len(data)}b)"); fail += 1; continue
    open(dest, "wb").write(data)
    downloaded[name] = e["slug"]; fresh += 1
    print(f"  ok {name} -> {fn}")
    time.sleep(DELAY)

json.dump(downloaded, open(os.path.join(HERE, "downloaded_missing.json"), "w"),
          ensure_ascii=False, indent=2)
print(f"\n[summary] fresh={fresh} cached={cached} fail={fail} "
      f"mapped={len(downloaded)} banned={banned}")
if banned or (len(downloaded) < len(jobs) - fail):
    raise SystemExit(2)
