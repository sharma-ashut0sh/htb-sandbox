"""
Run this once via GitHub Actions to discover the correct team endpoints.
Prints HTTP status for every candidate — 200/401/403 = route exists, 404 = dead.
"""
import os, requests, json

token = os.getenv("HTB_LABS_TOKEN", "")
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}

TEAM_ID = 7247
candidates = []
for base in ["https://www.hackthebox.com/api/v4",
             "https://app.hackthebox.com/api/v4",
             "https://labs.hackthebox.com/api/v4"]:
    for path in [
        f"/team/info/{TEAM_ID}",
        f"/team/profile/{TEAM_ID}",
        f"/team/stats/{TEAM_ID}",
        f"/teams/{TEAM_ID}",
        f"/team/{TEAM_ID}",
        f"/team/chart/machines/attack/{TEAM_ID}",
        f"/team/graph/{TEAM_ID}?duration=1M",
        f"/team/members/{TEAM_ID}",
        f"/team/activity/{TEAM_ID}",
        f"/rankings/teams?page=1",
    ]:
        candidates.append(base + path)

print("=" * 70)
for url in candidates:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        note = {200: "✅ 200 OK", 401: "🔑 401 AUTH", 403: "🔑 403 AUTH", 404: "❌ 404 DEAD"}.get(r.status_code, f"?? {r.status_code}")
        print(f"{note}  {url}")
        if r.status_code == 200:
            print(f"       BODY: {r.text[:400]}")
    except Exception as e:
        print(f"ERR  {url}  {e}")
print("=" * 70)
