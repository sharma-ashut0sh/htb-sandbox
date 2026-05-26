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


# ─────────────────────────────────────────────
# MODULE 1 – Experience / Rank / XP / Streak
# ─────────────────────────────────────────────
def fetch_experience(token):
    url = f"{EXP_BASE}/account/{EXPERIENCE_UUID}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        return {
            "rank":          d.get("levelTitle", "Unknown"),
            "level":         d.get("level", 0),
            "xp":            d.get("totalExperiencePoints", 0),
            "xp_next_level": d.get("nextLevelExperiencePoints", 0),
            "streak":        d.get("streakData", {}).get("counter", 0),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 2 – Basic profile (get user_id)
# ─────────────────────────────────────────────
def fetch_profile_basic(token):
    url = f"{BASE}/user/info"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        info = d.get("info", d)
        return {
            "user_id":  info.get("id"),
            "username": info.get("name", "Unknown"),
            "avatar":   info.get("avatar", ""),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 3 – Public profile (owns from public endpoint)
# ─────────────────────────────────────────────
def fetch_profile_stats(token, user_id):
    """
    GET /api/v4/user/profile/basic/{user_id}
    This is the PUBLIC profile — contains user_owns, system_owns, points, bloods.
    More reliable than /user/info for own stats.
    """
    if not user_id:
        return {"error": "No user_id"}
    url = f"{BASE}/user/profile/basic/{user_id}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        p = d.get("profile", d)
        return {
            "user_owns":     p.get("user_owns", 0),
            "system_owns":   p.get("system_owns", 0),
            "points":        p.get("points", 0),
            "user_bloods":   p.get("user_bloods", 0),
            "system_bloods": p.get("system_bloods", 0),
            "rank":          p.get("rank", {}).get("name", ""),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 4 – Machine breakdown by difficulty & OS
# ─────────────────────────────────────────────
def fetch_machines(token, user_id):
    if not user_id:
        return {"by_difficulty": {}, "by_os": {}}

    diff_data = {}
    os_data   = {}

    # difficulty/attack chart
    try:
        r = requests.get(
            f"{BASE}/user/profile/chart/machines/attack/{user_id}",
            headers=_headers(token), timeout=15
        )
        r.raise_for_status()
        d = r.json()
        p = d.get("profile", d)
        diff_data = p.get("system", {})
    except Exception as e:
        print(f"  [machines/difficulty] {e}")

    # OS breakdown
    try:
        r = requests.get(
            f"{BASE}/user/profile/progress/machines/os/{user_id}",
            headers=_headers(token), timeout=15
        )
        r.raise_for_status()
        d = r.json()
        p = d.get("profile", d)
        os_data = p
    except Exception as e:
        print(f"  [machines/os] {e}")

    return {"by_difficulty": diff_data, "by_os": os_data}


# ─────────────────────────────────────────────
# MODULE 5 – Challenges by category
# ─────────────────────────────────────────────
def fetch_challenges(token, user_id):
    if not user_id:
        return []
    try:
        r = requests.get(
            f"{BASE}/user/profile/progress/challenges/{user_id}",
            headers=_headers(token), timeout=15
        )
        r.raise_for_status()
        d = r.json()
        p = d.get("profile", d)
        return p.get("challenges", [])
    except Exception as e:
        print(f"  [challenges] {e}")
        return []


# ─────────────────────────────────────────────
# MODULE 6 – Full activity feed (no 20-item cap)
# ─────────────────────────────────────────────
def fetch_activity(token, user_id):
    if not user_id:
        return []
    try:
        r = requests.get(
            f"{BASE}/user/profile/activity/{user_id}",
            headers=_headers(token), timeout=15
        )
        r.raise_for_status()
        d = r.json()
        p = d.get("profile", d)
        return p.get("activity", [])
    except Exception as e:
        print(f"  [activity] {e}")
        return []


# ─────────────────────────────────────────────
# DERIVE STATS FROM ACTIVITY
# Used as fallback when profile endpoints return 0
# ─────────────────────────────────────────────
def derive_stats_from_activity(activity):
    """
    Parse the full activity list to count:
    - machine user owns, machine root owns (by machine name, deduplicated)
    - challenge solves
    - machine difficulty breakdown (from type field if available)
    - OS breakdown (best effort from name — not always reliable)
    """
    machine_user  = set()
    machine_root  = set()
    challenge_solves = 0

    diff_counts = defaultdict(int)
    os_counts   = defaultdict(int)

    LINUX_HINTS   = []  # we can't reliably detect OS from name alone
    WINDOWS_HINTS = []

    for item in activity:
        t    = (item.get("type") or "").lower()
        name = item.get("name") or item.get("object_type") or ""
        diff = (item.get("difficulty") or "").capitalize()
        os_  = (item.get("os") or "").lower()

        if t == "user":
            machine_user.add(name)
        elif t == "root":
            machine_root.add(name)
            if diff:
                diff_counts[diff] += 1
            if os_:
                os_counts[os_] += 1
        elif t in ("challenge", "chall"):
            challenge_solves += 1

    return {
        "user_owns":   len(machine_user),
        "system_owns": len(machine_root),
        "challenge_solves": challenge_solves,
        "diff_from_activity": dict(diff_counts),
        "os_from_activity":   dict(os_counts),
        "unique_machines": list(machine_root | machine_user),
    }


# ─────────────────────────────────────────────
# ASSEMBLE & OUTPUT
# ─────────────────────────────────────────────
def main():
    token = os.getenv("HTB_LABS_TOKEN", "")
    if not token:
        print("CRITICAL: HTB_LABS_TOKEN secret is missing.")
        return

    print("[1/6] Fetching experience (rank/XP/streak)...")
    exp = fetch_experience(token)
    print(f"      rank={exp.get('rank')}  xp={exp.get('xp')}  streak={exp.get('streak')}")

    print("[2/6] Fetching basic profile (user_id)...")
    profile = fetch_profile_basic(token)
    user_id = profile.get("user_id") if "error" not in profile else None
    print(f"      user_id={user_id}  username={profile.get('username')}")

    print("[3/6] Fetching public profile stats (owns/points)...")
    stats = fetch_profile_stats(token, user_id)
    print(f"      user_owns={stats.get('user_owns')}  system_owns={stats.get('system_owns')}  points={stats.get('points')}")

    print("[4/6] Fetching machine breakdown (difficulty + OS)...")
    machines = fetch_machines(token, user_id)

    print("[5/6] Fetching challenge progress...")
    challenges = fetch_challenges(token, user_id)

    print("[6/6] Fetching full activity feed...")
    activity = fetch_activity(token, user_id)
    print(f"      activity items: {len(activity)}")

    # ── Derive fallback stats from activity ──────────────────────────────
    derived = derive_stats_from_activity(activity)
    print(f"      derived: user_owns={derived['user_owns']}  root_owns={derived['system_owns']}  challenges={derived['challenge_solves']}")

    # ── Use profile stats if non-zero, else fall back to derived ─────────
    final_user_owns   = stats.get("user_owns")   or derived["user_owns"]
    final_system_owns = stats.get("system_owns") or derived["system_owns"]
    final_points      = stats.get("points", 0)

    # ── Use activity-derived machine breakdown if API returned empty ──────
    final_diff = machines["by_difficulty"] if any(v for v in machines["by_difficulty"].values() if isinstance(v, (int,float)) and v > 0) else derived["diff_from_activity"]
    final_os   = machines["by_os"]         if any(v for v in machines["by_os"].values()         if isinstance(v, (int,float)) and v > 0) else derived["os_from_activity"]

    # ── Compose payload ───────────────────────────────────────────────────
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "generated_at": now_iso,
        "experience":   exp,
        "profile": {
            "user_id":     user_id,
            "username":    profile.get("username", "Unknown"),
            "user_owns":   final_user_owns,
            "system_owns": final_system_owns,
            "points":      final_points,
            "user_bloods":   stats.get("user_bloods", 0),
            "system_bloods": stats.get("system_bloods", 0),
        },
        "machines": {
            "by_difficulty": final_diff,
            "by_os":         final_os,
        },
        "challenges":  challenges,
        "activity":    activity[:20],   # keep last 20 for display
        "derived":     derived,         # raw derived counts for debugging
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("  ✓ data.json written")
    print("Build complete.")


if __name__ == "__main__":
    main()
