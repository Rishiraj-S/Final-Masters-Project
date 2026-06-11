"""Download matched SVGs and regenerate utils/logos.py mappings.

- Saves team SVGs   -> assets/logos/team/{slug}.svg
- Saves comp  SVGs  -> assets/logos/tournament/{slug}.svg
- Writes generated TEAM_LOGOS / TOURNAMENT_LOGOS into utils/logos.py
- Keeps existing flag mapping + helper functions intact
"""
import json, os, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEAM_DIR = os.path.join(ROOT, "assets", "logos", "team")
TOUR_DIR = os.path.join(ROOT, "assets", "logos", "tournament")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://football-logos.cc/",
           "Accept": "image/svg+xml,image/*,*/*"}

team_matches = json.load(open(os.path.join(HERE, "team_matches.json"), encoding="utf-8"))
comp_matches = json.load(open(os.path.join(HERE, "comp_matches.json"), encoding="utf-8"))

THRESH = 0.6


REQ_DELAY = 4.0          # polite gap between requests
MAX_429 = 40             # retries on rate limit (wait out long bans)
BACKOFF = 60             # seconds to wait per 429
COOLDOWN_EVERY = 30      # after N fresh downloads, pause to dodge burst cap
COOLDOWN_SECS = 75

_fresh = 0               # count of network downloads this run


def valid_svg(path):
    if not os.path.exists(path) or os.path.getsize(path) < 80:
        return False
    head = open(path, "rb").read(64).lstrip()
    return head.startswith(b"<")


OK, CACHED, RATE_LIMIT, FAIL = "OK", "CACHED", "RATE_LIMIT", "FAIL"


def dl(url, dest):
    """Single attempt. No retry-hammering — caller aborts the run on RATE_LIMIT
    so the ban window can expire during silence."""
    if valid_svg(dest):
        return CACHED, "cached"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        return (RATE_LIMIT if e.code == 429 else FAIL), f"HTTP {e.code}"
    except Exception as e:
        return FAIL, f"ERR {e}"
    if not data.lstrip().startswith(b"<") or len(data) < 80:
        return FAIL, f"not-svg ({len(data)}b)"
    open(dest, "wb").write(data)
    return OK, len(data)


def accept(rec):
    return rec and rec.get("svg_url") and (rec.get("score", 0) >= THRESH or rec.get("override"))


# build job list: (kind, dest_dir, fname, url)
jobs = []
for name in sorted(team_matches):
    rec = team_matches[name]
    if accept(rec):
        jobs.append(("team", TEAM_DIR, f"{rec['slug']}.svg", rec["svg_url"]))
for folder, rec in comp_matches.items():
    if not (rec.get("absent") or not accept(rec)):
        jobs.append(("comp", TOUR_DIR, f"{rec['slug']}.svg", rec["svg_url"]))

# dedupe by (dir,fname)
seen, uniq = set(), []
for k, d, f, u in jobs:
    if (d, f) in seen:
        continue
    seen.add((d, f))
    uniq.append((k, d, f, u))

done = fresh = fail = 0
banned = False
for k, d, fname, url in uniq:
    dest = os.path.join(d, fname)
    status, info = dl(url, dest)
    if status == CACHED:
        done += 1
        continue
    if status == RATE_LIMIT:
        print(f"RATE LIMITED at {fname} — aborting; retry later")
        banned = True
        break
    if status == FAIL:
        print(f"  FAIL {k} {fname} -> {url} ({info})")
        fail += 1
        continue
    done += 1
    fresh += 1
    if fresh % COOLDOWN_EVERY == 0:
        print(f"  ...{fresh} fresh this run, cooldown {COOLDOWN_SECS}s")
        time.sleep(COOLDOWN_SECS)
    else:
        time.sleep(REQ_DELAY)

remaining = len(uniq) - done - fail
print(f"\n[summary] total={len(uniq)} done={done} fresh={fresh} "
      f"fail={fail} remaining={remaining} banned={banned}")
if remaining > 0 or banned:
    raise SystemExit(2)   # signal: run again later
print("ALL DONE")
