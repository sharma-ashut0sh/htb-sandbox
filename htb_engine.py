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
    Try /team/profile/{id} for full members list.
    Fallback: we already have basics from profile endpoint.
    """
    d = safe_get(token, f"{BASE}/team/profile/{team_id}", "team/profile")
    if not d:
        return {}

    # unwrap any nesting
    for key in ("profile", "team", "data"):
        if key in d and isinstance(d[key], dict):
            d = d[key]
            break

    members_raw = d.get("members") or d.get("users") or []
    members = sorted([
        {
            "name":       m.get("name") or m.get("username", "?"),
            "rank":       m.get("rank") or m.get("level", ""),
            "points":     m.get("points", 0),
            "root_owns":  m.get("root_owns") or m.get("system_owns", 0),
            "is_captain": bool(m.get("is_captain") or m.get("captain")),
        }
        for m in members_raw
    ], key=lambda x: x["points"], reverse=True)

    return {
        "id":             team_id,
        "name":           d.get("name", ""),
        "points":         d.get("points", 0),
        "root_owns":      d.get("root_owns", 0),
        "user_owns":      d.get("user_owns", 0),
        "challenge_owns": d.get("challenge_owns", 0),
        "ranking":        d.get("ranking") or d.get("rank", 0),
        "member_count":   d.get("member_count") or len(members),
        "members":        members,
    }


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
