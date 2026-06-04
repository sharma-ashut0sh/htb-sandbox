import os
import json
import requests
from datetime import datetime
from collections import defaultdict

BASE         = "https://labs.hackthebox.com/api/v4"
EXP_BASE     = "https://labs.hackthebox.com/api/experience/v1"
EXPERIENCE_UUID = "9d7ea1a6-d26f-4522-b039-146c00b8b27b"


def _headers(token):
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def safe_get(token, url, label):
    """GET a URL, print full raw response for debugging, return parsed JSON or {}."""
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        print(f"\n  [{label}] HTTP {r.status_code}  url={url}")
        if r.status_code == 200:
            d = r.json()
            # Print first 600 chars of raw response so we can see the shape
            raw = json.dumps(d)
            print(f"  [{label}] RAW (first 600 chars): {raw[:600]}")
            return d
        else:
            print(f"  [{label}] ERROR BODY: {r.text[:300]}")
            return {}
    except Exception as e:
        print(f"  [{label}] EXCEPTION: {e}")
        return {}


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
    """Gets user_id. Also dump everything it returns."""
    d = safe_get(token, f"{BASE}/user/info", "user/info")
    info = d.get("info", d)
    return {
        "user_id":  info.get("id"),
        "username": info.get("name", "Unknown"),
    }


def fetch_profile_basic(token, user_id):
    """Public profile — should have user_owns, system_owns etc."""
    if not user_id:
        print("  [profile/basic] SKIPPED — no user_id")
        return {}
    d = safe_get(token, f"{BASE}/user/profile/basic/{user_id}", "profile/basic")
    p = d.get("profile", d)
    return {
        "user_owns":     p.get("user_owns", 0),
        "system_owns":   p.get("system_owns", 0),
        "points":        p.get("points", 0),
        "user_bloods":   p.get("user_bloods", 0),
        "system_bloods": p.get("system_bloods", 0),
    }


def fetch_activity(token, user_id):
    """Full activity feed — DUMP RAW so we can see real field names."""
    if not user_id:
        print("  [activity] SKIPPED — no user_id")
        return []
    d = safe_get(token, f"{BASE}/user/profile/activity/{user_id}", "activity")
    p = d.get("profile", d)
    activity = p.get("activity", [])
    print(f"\n  [activity] total items returned: {len(activity)}")
    if activity:
        print(f"  [activity] FIRST ITEM FULL: {json.dumps(activity[0], indent=2)}")
        print(f"  [activity] SECOND ITEM FULL: {json.dumps(activity[1], indent=2) if len(activity)>1 else 'N/A'}")
        # Print all unique 'type' values seen
        types = set(str(item.get('type','')) for item in activity)
        obj_types = set(str(item.get('object_type','')) for item in activity)
        print(f"  [activity] ALL 'type' values seen:        {types}")
        print(f"  [activity] ALL 'object_type' values seen: {obj_types}")
        # Print all top-level keys from first item
        print(f"  [activity] KEYS in first item: {list(activity[0].keys())}")
    return activity


def fetch_challenges(token, user_id):
    """Challenge progress by category."""
    if not user_id:
        return []
    d = safe_get(token, f"{BASE}/user/profile/progress/challenges/{user_id}", "challenges")
    p = d.get("profile", d)
    challenges = p.get("challenges", [])
    print(f"\n  [challenges] items: {len(challenges)}")
    if challenges:
        print(f"  [challenges] first item: {json.dumps(challenges[0])}")
    return challenges


def fetch_machines_difficulty(token, user_id):
    if not user_id:
        return {}
    d = safe_get(token, f"{BASE}/user/profile/chart/machines/attack/{user_id}", "machines/difficulty")
    p = d.get("profile", d)
    return p


def fetch_machines_os(token, user_id):
    if not user_id:
        return {}
    d = safe_get(token, f"{BASE}/user/profile/progress/machines/os/{user_id}", "machines/os")
    p = d.get("profile", d)
    return p


def derive_from_activity(activity):
    """
    Parse activity with awareness that the 'type' field might have
    different values. Print what we find and try multiple field name patterns.
    """
    machine_user  = set()
    machine_root  = set()
    challenge_solves = 0
    diff_counts = defaultdict(int)
    os_counts   = defaultdict(int)

    for item in activity:
        # Try both 'type' and 'object_type' — HTB API is inconsistent
        t = (
            item.get("type") or
            item.get("object_type") or
            ""
        ).lower().strip()

        name = (
            item.get("name") or
            item.get("machine_name") or
            item.get("challenge_name") or
            item.get("object_name") or
            ""
        )
        diff = (item.get("difficulty") or item.get("difficultyText") or "").capitalize()
        os_  = (item.get("os") or item.get("machine_os") or "").lower()

        # HTB v4 activity types can be: "user", "root", "challenge",
        # OR integers: 1=user, 2=root, 3=challenge
        # OR strings like "machine_user", "machine_root"
        t_str = str(t)

        if t_str in ("user", "1", "machine_user", "user_own"):
            machine_user.add(name)
        elif t_str in ("root", "2", "machine_root", "root_own", "system_own"):
            machine_root.add(name)
            if diff:
                diff_counts[diff] += 1
            if os_:
                os_counts[os_] += 1
        elif t_str in ("challenge", "3", "chall", "challenge_own"):
            challenge_solves += 1

    return {
        "user_owns":          len(machine_user),
        "system_owns":        len(machine_root),
        "challenge_solves":   challenge_solves,
        "diff_from_activity": dict(diff_counts),
        "os_from_activity":   dict(os_counts),
        "unique_machines":    sorted(machine_root | machine_user),
    }


def main():
    token = os.getenv("HTB_LABS_TOKEN", "")
    if not token:
        print("CRITICAL: HTB_LABS_TOKEN missing")
        return

    print("=" * 60)
    print("[1] Experience")
    exp = fetch_experience(token)

    print("\n" + "=" * 60)
    print("[2] User info (get user_id)")
    info = fetch_user_info(token)
    user_id = info.get("user_id")
    print(f"  user_id = {user_id}")

    print("\n" + "=" * 60)
    print("[3] Public profile stats")
    stats = fetch_profile_basic(token, user_id)
    print(f"  user_owns={stats.get('user_owns')}  system_owns={stats.get('system_owns')}  points={stats.get('points')}")

    print("\n" + "=" * 60)
    print("[4] Activity feed")
    activity = fetch_activity(token, user_id)

    print("\n" + "=" * 60)
    print("[5] Challenges")
    challenges = fetch_challenges(token, user_id)

    print("\n" + "=" * 60)
    print("[6] Machines difficulty")
    machines_diff = fetch_machines_difficulty(token, user_id)

    print("\n" + "=" * 60)
    print("[7] Machines OS")
    machines_os = fetch_machines_os(token, user_id)

    print("\n" + "=" * 60)
    print("[8] Deriving stats from activity...")
    derived = derive_from_activity(activity)
    print(f"  DERIVED: {json.dumps(derived, indent=2)}")

    print("\n" + "=" * 60)
    print("[TEAM] Fetching team stats...")
    team = fetch_team(token)

    # ── Final values ─────────────────────────────────────────────────────
    final_user_owns   = stats.get("user_owns")   or derived["user_owns"]
    final_system_owns = stats.get("system_owns") or derived["system_owns"]

    # For difficulty: try several known response shapes
    diff_data = {}
    if isinstance(machines_diff, dict):
        # try "system" key (root owns per difficulty)
        diff_data = machines_diff.get("system") or machines_diff.get("data") or {}
        # flatten if nested
        if not any(isinstance(v, (int, float)) for v in diff_data.values()):
            diff_data = {}
    if not diff_data:
        diff_data = derived["diff_from_activity"]

    os_data = {}
    if isinstance(machines_os, dict):
        os_data = {k: v for k, v in machines_os.items() if isinstance(v, (int, float)) and v > 0}
    if not os_data:
        os_data = derived["os_from_activity"]

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "generated_at": now_iso,
        "experience": exp,
        "profile": {
            "user_id":       user_id,
            "username":      info.get("username", "Unknown"),
            "user_owns":     final_user_owns,
            "system_owns":   final_system_owns,
            "points":        stats.get("points", 0),
            "user_bloods":   stats.get("user_bloods", 0),
            "system_bloods": stats.get("system_bloods", 0),
        },
        "machines": {
            "by_difficulty": diff_data,
            "by_os":         os_data,
        },
        "challenges":  challenges,
        "activity":    activity[:20],
        "derived":     derived,
        "team":        team,
    }

    print("\n" + "=" * 60)
    print("FINAL PAYLOAD SUMMARY:")
    print(f"  user_owns   = {final_user_owns}")
    print(f"  system_owns = {final_system_owns}")
    print(f"  challenges  = {len(challenges)} categories")
    print(f"  activity    = {len(activity[:20])} items")
    print(f"  diff_data   = {diff_data}")
    print(f"  os_data     = {os_data}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\n✓ data.json written")


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────
# TEAM DATA
# ─────────────────────────────────────────────
TEAM_ID = 7247

def fetch_team(token):
    BASE = "https://labs.hackthebox.com/api/v4"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    def unwrap(d):
        if not d: return {}
        if "profile" in d and isinstance(d["profile"], dict): return d["profile"]
        if "team"    in d and isinstance(d["team"], dict):    return d["team"]
        if "data"    in d:
            data = d["data"]
            if isinstance(data, dict): return data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("id") == TEAM_ID:
                        return item
                return data[0] if data else {}
        if "name" in d or "points" in d: return d
        return d

    def get_members(profile):
        for key in ("members", "users", "teammates"):
            val = profile.get(key)
            if val and isinstance(val, list):
                return val
        return []

    # ── Try profile endpoint ───────────────────────────────────────────────
    profile = {}
    for url in [
        f"{BASE}/team/profile/{TEAM_ID}",
        f"https://www.hackthebox.com/api/v4/team/profile/{TEAM_ID}",
    ]:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            print(f"  [team] {r.status_code} {url}")
            if r.status_code == 200:
                raw = r.json()
                print(f"  [team] raw keys: {list(raw.keys())}")
                print(f"  [team] raw (600c): {json.dumps(raw)[:600]}")
                profile = unwrap(raw)
                break
            else:
                print(f"  [team] body: {r.text[:200]}")
        except Exception as e:
            print(f"  [team] exception: {e}")

    if not profile:
        print("  [team] PROFILE EMPTY — trying rankings endpoint to find team")
        # Scan global rankings for our team
        try:
            r = requests.get(
                f"{BASE}/rankings/teams?page=1&per_page=100",
                headers=headers, timeout=15
            )
            print(f"  [rankings] {r.status_code}")
            if r.status_code == 200:
                raw = r.json()
                data = raw.get("data", raw.get("rankings", []))
                if isinstance(data, list):
                    for item in data:
                        if item.get("id") == TEAM_ID:
                            profile = item
                            print(f"  [rankings] found team: {json.dumps(item)[:300]}")
                            break
        except Exception as e:
            print(f"  [rankings] exception: {e}")

    if not profile:
        return {"error": "team endpoint returned no usable data", "id": TEAM_ID}

    # ── Extract members ────────────────────────────────────────────────────
    raw_members = get_members(profile)
    members = []
    for m in raw_members:
        members.append({
            "name":       m.get("name") or m.get("username") or "?",
            "rank":       m.get("rank") or m.get("level") or "",
            "points":     m.get("points", 0),
            "root_owns":  m.get("root_owns") or m.get("system_owns", 0),
            "is_captain": bool(m.get("is_captain") or m.get("captain")),
        })
    # Sort by points desc
    members.sort(key=lambda x: x["points"], reverse=True)

    team = {
        "id":             TEAM_ID,
        "name":           profile.get("name", ""),
        "points":         profile.get("points", 0),
        "root_owns":      profile.get("root_owns", 0),
        "user_owns":      profile.get("user_owns", 0),
        "challenge_owns": profile.get("challenge_owns", 0),
        "ranking":        profile.get("ranking") or profile.get("rank") or 0,
        "member_count":   profile.get("member_count") or profile.get("members_count") or len(members),
        "members":        members,
    }
    print(f"  [team] FINAL: name={team['name']} rank={team['ranking']} pts={team['points']} members={len(members)}")
    return team
