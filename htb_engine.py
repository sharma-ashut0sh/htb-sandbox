import os
import json
import requests
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE         = "https://labs.hackthebox.com/api/v4"
EXP_BASE     = "https://labs.hackthebox.com/api/experience/v1"
EXPERIENCE_UUID = "9d7ea1a6-d26f-4522-b039-146c00b8b27b"
TEAM_ID      = 7247


def _h(token):
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }


def safe_get(token, url, label):
    try:
        r = requests.get(url, headers=_h(token), timeout=15)
        print(f"  [{label}] HTTP {r.status_code}")
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  [{label}] body: {r.text[:200]}")
    except Exception as e:
        print(f"  [{label}] exception: {e}")
    return {}


# ─────────────────────────────────────────────
# FETCHERS
# ─────────────────────────────────────────────

def fetch_experience(token):
    d = safe_get(token, f"{EXP_BASE}/account/{EXPERIENCE_UUID}", "experience")
    return {
        "rank":          d.get("levelTitle", "Unknown"),
        "level":         d.get("level", 0),
        "xp":            d.get("totalExperiencePoints", 0),
        "xp_next_level": d.get("nextLevelExperiencePoints", 0),
        "streak":        d.get("streakData", {}).get("counter", 0),
    }


def fetch_user_info(token):
    d = safe_get(token, f"{BASE}/user/info", "user/info")
    info = d.get("info", d)
    return {
        "user_id":  info.get("id"),
        "username": info.get("name", "Unknown"),
    }


def fetch_profile(token, user_id):
    """
    /user/profile/basic/{id} — confirmed response shape:
    { "profile": { "system_owns": 30, "user_owns": 31, "points": 314,
                   "team": { "id":7247, "name":"VXON", "ranking":50,
                             "member_count":18, "logo_thumb_url":"..." },
                   ... } }
    """
    d = safe_get(token, f"{BASE}/user/profile/basic/{user_id}", "profile/basic")
    p = d.get("profile", {})
    team_raw = p.get("team") or {}
    return {
        "user_owns":   p.get("user_owns", 0),
        "system_owns": p.get("system_owns", 0),
        "points":      p.get("points", 0),
        "user_bloods": p.get("user_bloods", 0),
        "system_bloods": p.get("system_bloods", 0),
        # embed team basics from profile — no extra API call needed
        "team": {
            "id":           team_raw.get("id", TEAM_ID),
            "name":         team_raw.get("name", ""),
            "ranking":      team_raw.get("ranking", 0),
            "member_count": team_raw.get("member_count", 0),
            "logo":         team_raw.get("logo_thumb_url", ""),
        } if team_raw else {}
    }


def fetch_activity(token, user_id):
    """
    Confirmed field names: type ∈ {root, user, challenge, fortress}
    object_type ∈ {machine, challenge, fortress}
    """
    d = safe_get(token, f"{BASE}/user/profile/activity/{user_id}", "activity")
    p = d.get("profile", d)
    return p.get("activity", [])


def fetch_challenges(token, user_id):
    """
    Confirmed shape:
    { "profile": {
        "challenge_owns": { "solved": 20, "total": 831 },
        "challenge_categories": [
          { "name": "Reversing", "owned_flags": 3, "total_flags": 100,
            "completion_percentage": 3 }, ...
        ]
    }}
    """
    d = safe_get(token, f"{BASE}/user/profile/progress/challenges/{user_id}", "challenges")
    p = d.get("profile", {})
    categories = p.get("challenge_categories", [])
    total_solved = p.get("challenge_owns", {}).get("solved", 0)
    return {
        "total_solved": total_solved,
        "categories": [
            {
                "name":       c.get("name", ""),
                "solved":     c.get("owned_flags", 0),
                "total":      c.get("total_flags", 0),
                "completion": c.get("completion_percentage", 0),
            }
            for c in categories if c.get("owned_flags", 0) > 0
        ]
    }


def fetch_attack_paths(token, user_id):
    """
    Confirmed shape:
    { "profile": {
        "machine_owns": { "solved": 30, "total": 532 },
        "machine_attack_paths": {
          "Reconnaissance": { "solved": 9, "total": 251 }, ...
        }
    }}
    """
    d = safe_get(token, f"{BASE}/user/profile/chart/machines/attack/{user_id}", "attack_paths")
    p = d.get("profile", {})
    paths_raw = p.get("machine_attack_paths", {})
    # Sort by solved desc, take top 8
    paths = sorted(
        [{"name": k, "solved": v.get("solved", 0), "total": v.get("total", 0)}
         for k, v in paths_raw.items() if v.get("solved", 0) > 0],
        key=lambda x: x["solved"], reverse=True
    )[:8]
    return {
        "total_solved": p.get("machine_owns", {}).get("solved", 0),
        "paths": paths
    }


def fetch_team_full(token, team_id):
    """
    Confirmed working on labs.hackthebox.com/api/v4:
      GET /team/info/{id}                  — flat JSON: name, points, discord etc
      GET /team/members/{id}               — array of members with owns/points/role
      GET /team/graph/{id}?duration=1M     — {"status":true,"data":{"points":[...],"rank":[...]}}
      GET /team/chart/machines/attack/{id} — {"machine_owns":{...},"machine_attack_paths":{...}}
      GET /rankings/teams?page=1           — leaderboard with root_owns/user_owns/challenge_owns
    """
    result = {}

    # ── 1. Team info (name, points, social links) ─────────────────────────
    d = safe_get(token, f"{BASE}/team/info/{team_id}", "team/info")
    if d and isinstance(d, dict) and "name" in d:
        result.update({
            "id":      team_id,
            "name":    d.get("name", ""),
            "points":  d.get("points", 0),
            "discord": d.get("discord", ""),
            "country": d.get("country_name", ""),
            "avatar":  d.get("avatar_url", ""),
        })
        print(f"  [team/info] name={result['name']}  pts={result['points']}")

    # ── 2. Members list ───────────────────────────────────────────────────
    # Confirmed shape: flat array [{id, name, points, root_owns, user_owns, role, rank_text, ...}]
    m = safe_get(token, f"{BASE}/team/members/{team_id}", "team/members")
    if isinstance(m, list):
        members = sorted([
            {
                "name":       mb.get("name", "?"),
                "rank":       mb.get("rank_text", ""),
                "points":     mb.get("points", 0),
                "root_owns":  mb.get("root_owns", 0),
                "user_owns":  mb.get("user_owns", 0),
                "country":    mb.get("country_code", ""),
                "is_captain": mb.get("role", "") == "captain",
            }
            for mb in m if isinstance(mb, dict)
        ], key=lambda x: x["points"], reverse=True)
        result["members"]      = members
        result["member_count"] = len(members)
        print(f"  [team/members] count={len(members)}")

    # ── 3. Rank graph (last 1 month) ──────────────────────────────────────
    # Confirmed shape: {"status":true,"data":{"points":[...],"rank":[...],"respect":[...]}}
    g = safe_get(token, f"{BASE}/team/graph/{team_id}?duration=1M", "team/graph")
    if g and g.get("status"):
        data = g.get("data", {})
        result["graph"] = {
            "points": data.get("points", []),
            "rank":   data.get("rank", []),
        }
        print(f"  [team/graph] pts_series={len(result['graph']['points'])}  rank_series={len(result['graph']['rank'])}")

    # ── 4. Team attack paths ──────────────────────────────────────────────
    # Confirmed shape: {"machine_owns":{"solved":191,"total":532},"machine_attack_paths":{...}}
    a = safe_get(token, f"{BASE}/team/chart/machines/attack/{team_id}", "team/attack")
    if a and "machine_attack_paths" in a:
        paths_raw = a["machine_attack_paths"]
        result["attack_paths"] = sorted(
            [{"name": k, "solved": v.get("solved", 0), "total": v.get("total", 0)}
             for k, v in paths_raw.items() if v.get("solved", 0) > 0],
            key=lambda x: x["solved"], reverse=True
        )[:8]
        result["team_machine_owns"] = a.get("machine_owns", {})
        print(f"  [team/attack] paths={len(result['attack_paths'])}  total_solved={result['team_machine_owns'].get('solved')}")

    # ── 5. Global ranking (root/user/challenge owns) ──────────────────────
    # Confirmed shape: {"data":[{"rank":1,"points":...,"root_owns":...,"id":...,"name":...},...]}
    r = safe_get(token, f"{BASE}/rankings/teams?page=1", "rankings/teams")
    if r and "data" in r:
        for entry in r["data"]:
            if entry.get("id") == team_id:
                result["ranking"]        = entry.get("rank", 0)
                result["root_owns"]      = entry.get("root_owns", 0)
                result["user_owns"]      = entry.get("user_owns", 0)
                result["challenge_owns"] = entry.get("challenge_owns", 0)
                print(f"  [rankings] rank={result['ranking']}  root={result['root_owns']}  user={result['user_owns']}  chall={result['challenge_owns']}")
                break
        else:
            print(f"  [rankings] team {team_id} not on page 1 — trying page scan")
            # Team might be past page 1 — use profile-provided ranking as fallback

    return result


# ─────────────────────────────────────────────
# DERIVE FROM ACTIVITY
# ─────────────────────────────────────────────
def derive_from_activity(activity):
    """
    Confirmed types: root, user, challenge, fortress
    """
    machine_user = set()
    machine_root = set()
    challenge_solves = 0
    points_by_month = defaultdict(int)

    for item in activity:
        t    = (item.get("type") or "").lower()
        name = item.get("name", "")
        pts  = item.get("points", 0) or 0
        date = item.get("date", "")

        if t == "user":
            machine_user.add(name)
        elif t == "root":
            machine_root.add(name)
        elif t == "challenge":
            challenge_solves += 1

        # Monthly XP bucketing
        if date and pts:
            try:
                month = date[:7]  # "2026-06"
                points_by_month[month] += pts
            except Exception:
                pass

    return {
        "user_owns":        len(machine_user),
        "system_owns":      len(machine_root),
        "challenge_solves": challenge_solves,
        "unique_machines":  sorted(machine_root | machine_user),
        "points_by_month":  dict(sorted(points_by_month.items())),
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    token = os.getenv("HTB_LABS_TOKEN", "")
    if not token:
        print("CRITICAL: HTB_LABS_TOKEN missing")
        return

    print("[1/7] Experience")
    exp = fetch_experience(token)
    print(f"      rank={exp['rank']}  xp={exp['xp']}  streak={exp['streak']}")

    print("\n[2/7] User info")
    info = fetch_user_info(token)
    user_id = info.get("user_id")
    print(f"      user_id={user_id}  username={info.get('username')}")

    print("\n[3/7] Profile + team basics")
    profile = fetch_profile(token, user_id)
    print(f"      user_owns={profile['user_owns']}  system_owns={profile['system_owns']}  points={profile['points']}")
    print(f"      team={profile.get('team')}")

    print("\n[4/7] Activity (full feed)")
    activity = fetch_activity(token, user_id)
    print(f"      items={len(activity)}")

    print("\n[5/7] Challenges by category")
    challenges = fetch_challenges(token, user_id)
    print(f"      total_solved={challenges['total_solved']}  categories={len(challenges['categories'])}")

    print("\n[6/7] Machine attack paths")
    attack_paths = fetch_attack_paths(token, user_id)
    print(f"      total_solved={attack_paths['total_solved']}  paths={len(attack_paths['paths'])}")

    print("\n[7/7] Team full profile")
    team_full = fetch_team_full(token, TEAM_ID)
    # Merge with basics from profile if full fetch failed/empty
    team_basic = profile.get("team", {})
    team = {
        "id":             team_full.get("id")           or team_basic.get("id", TEAM_ID),
        "name":           team_full.get("name")         or team_basic.get("name", "VXON"),
        "points":         team_full.get("points")       or team_basic.get("points", 0),
        "root_owns":      team_full.get("root_owns", 0),
        "user_owns":      team_full.get("user_owns", 0),
        "challenge_owns": team_full.get("challenge_owns", 0),
        "ranking":        team_full.get("ranking")      or team_basic.get("ranking", 0),
        "member_count":   team_full.get("member_count") or team_basic.get("member_count", 0),
        "members":        team_full.get("members", []),
        "logo":           team_basic.get("logo", ""),
    }
    print(f"      name={team['name']}  rank={team['ranking']}  members={team['member_count']}")

    print("\n[derive] Parsing activity...")
    derived = derive_from_activity(activity)
    print(f"      user={derived['user_owns']}  root={derived['system_owns']}  chall={derived['challenge_solves']}")

    # Final owns — profile wins if non-zero, else derived fallback
    final_user   = profile["user_owns"]   or derived["user_owns"]
    final_system = profile["system_owns"] or derived["system_owns"]

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "generated_at": now_iso,
        "experience":   exp,
        "profile": {
            "user_id":       user_id,
            "username":      info.get("username", "Unknown"),
            "user_owns":     final_user,
            "system_owns":   final_system,
            "points":        profile["points"],
            "user_bloods":   profile["user_bloods"],
            "system_bloods": profile["system_bloods"],
        },
        "challenges":    challenges,
        "attack_paths":  attack_paths,
        "activity":      activity[:20],
        "derived":       derived,
        "team":          team,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\n✓ data.json written")


if __name__ == "__main__":
    main()
