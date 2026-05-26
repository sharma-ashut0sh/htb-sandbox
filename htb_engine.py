import os
import json
import requests
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE      = "https://labs.hackthebox.com/api/v4"
EXP_BASE  = "https://labs.hackthebox.com/api/experience/v1"
ACAD_BASE = "https://academy.hackthebox.com/api/v1"

# Hardcoded public user UUID from the experience endpoint you already have
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
            "rank":   d.get("levelTitle", "Unknown"),
            "level":  d.get("level", 0),
            "xp":     d.get("totalExperiencePoints", 0),
            "xp_next_level": d.get("nextLevelExperiencePoints", 0),
            "streak": d.get("streakData", {}).get("counter", 0),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 2 – Basic Profile (user_id + owns)
# ─────────────────────────────────────────────
def fetch_profile_basic(token):
    """
    GET /api/v4/user/info  — returns the authenticated user's own profile.
    Falls back gracefully so the rest of the pipeline still runs.
    """
    url = f"{BASE}/user/info"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        info = d.get("info", d)
        return {
            "user_id":      info.get("id"),
            "username":     info.get("name", "Unknown"),
            "avatar":       info.get("avatar", ""),
            "user_owns":    info.get("user_owns", 0),
            "system_owns":  info.get("system_owns", 0),
            "points":       info.get("points", 0),
            "user_bloods":  info.get("user_bloods", 0),
            "system_bloods": info.get("system_bloods", 0),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 3 – Machine progress breakdown
# ─────────────────────────────────────────────
def fetch_machines(token, user_id):
    """
    GET /api/v4/user/profile/chart/machines/attack/{user_id}
    Returns owns split by OS and difficulty.
    """
    if not user_id:
        return {"error": "No user_id available"}
    url = f"{BASE}/user/profile/chart/machines/attack/{user_id}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        # Response shape: { "profile": { "system": {...}, "user": {...} } }
        profile = d.get("profile", d)
        return {
            "by_difficulty": profile.get("system", {}),
            "user_owns_by_difficulty": profile.get("user", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_machine_os_breakdown(token, user_id):
    """
    GET /api/v4/user/profile/progress/machines/os/{user_id}
    Returns machine owns split by OS.
    """
    if not user_id:
        return {"error": "No user_id available"}
    url = f"{BASE}/user/profile/progress/machines/os/{user_id}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        profile = d.get("profile", d)
        # Typically: { "linux": N, "windows": N, "freebsd": N, "openbsd": N, "android": N, "other": N }
        return profile
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 4 – Challenge progress by category
# ─────────────────────────────────────────────
def fetch_challenges(token, user_id):
    """
    GET /api/v4/user/profile/progress/challenges/{user_id}
    Returns { "profile": { "challenges": [ { "name": "Crypto", "solved": N, "total": N }, ... ] } }
    """
    if not user_id:
        return {"error": "No user_id available"}
    url = f"{BASE}/user/profile/progress/challenges/{user_id}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        profile = d.get("profile", d)
        return profile.get("challenges", [])
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 5 – Recent activity feed
# ─────────────────────────────────────────────
def fetch_activity(token, user_id):
    """
    GET /api/v4/user/profile/activity/{user_id}
    Returns recent solves / events.
    """
    if not user_id:
        return {"error": "No user_id available"}
    url = f"{BASE}/user/profile/activity/{user_id}"
    try:
        r = requests.get(url, headers=_headers(token), timeout=15)
        r.raise_for_status()
        d = r.json()
        profile = d.get("profile", d)
        activity = profile.get("activity", [])
        # Trim to last 20 for dashboard display
        return activity[:20]
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# MODULE 6 – HTB Academy progress
# ─────────────────────────────────────────────
def fetch_academy(token):
    """
    Academy uses a separate subdomain & token.
    HTB_ACADEMY_TOKEN should be set as a separate secret.
    Endpoint: GET /api/v1/user/dashboard  (academy.hackthebox.com)
    """
    acad_token = os.getenv("HTB_ACADEMY_TOKEN", "").strip()
    if not acad_token:
        # Fall back: try the same token on the academy endpoint
        acad_token = token.strip()

    url = f"{ACAD_BASE}/user/dashboard"
    try:
        r = requests.get(url, headers=_headers(acad_token), timeout=15)
        r.raise_for_status()
        d = r.json()
        return {
            "modules_completed": d.get("modules_completed", d.get("completedModules", 0)),
            "modules_total":     d.get("modules_total",     d.get("totalModules", 0)),
            "current_paths":     d.get("current_paths",     d.get("activePaths", [])),
            "cubes":             d.get("cubes",              0),
        }
    except Exception as e:
        # Academy API endpoint discovery is still pending — return placeholder
        return {
            "error": str(e),
            "note": "Academy endpoint not yet confirmed. Set HTB_ACADEMY_TOKEN secret if separate."
        }


# ─────────────────────────────────────────────
# ASSEMBLE & OUTPUT
# ─────────────────────────────────────────────
def main():
    token = os.getenv("HTB_LABS_TOKEN", "")
    if not token:
        print("CRITICAL: HTB_LABS_TOKEN secret is missing.")
        return

    print("[1/6] Fetching experience data...")
    exp = fetch_experience(token)

    print("[2/6] Fetching basic profile (user_id)...")
    profile = fetch_profile_basic(token)

    user_id = profile.get("user_id") if "error" not in profile else None
    print(f"      user_id resolved: {user_id}")

    print("[3/6] Fetching machine breakdown...")
    machines_diff = fetch_machines(token, user_id)
    machines_os   = fetch_machine_os_breakdown(token, user_id)

    print("[4/6] Fetching challenge progress...")
    challenges = fetch_challenges(token, user_id)

    print("[5/6] Fetching recent activity...")
    activity = fetch_activity(token, user_id)

    print("[6/6] Fetching HTB Academy progress...")
    academy = fetch_academy(token)

    # ── Compose the JSON payload ──────────────────────────────────────────
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    now_fmt = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    payload = {
        "generated_at": now_iso,
        "experience":   exp,
        "profile":      profile,
        "machines": {
            "by_difficulty": machines_diff,
            "by_os":         machines_os,
        },
        "challenges":   challenges,
        "activity":     activity,
        "academy":      academy,
    }

    # ── Write data.json ───────────────────────────────────────────────────
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("  ✓ data.json written")

    # ── Write index.md (fallback human-readable view) ─────────────────────
    rank   = exp.get("rank", "Unknown") if "error" not in exp else "N/A"
    level  = exp.get("level", 0)        if "error" not in exp else 0
    xp     = exp.get("xp", 0)           if "error" not in exp else 0
    streak = exp.get("streak", 0)       if "error" not in exp else 0

    u_owns = profile.get("user_owns", 0)    if "error" not in profile else 0
    r_owns = profile.get("system_owns", 0)  if "error" not in profile else 0
    points = profile.get("points", 0)       if "error" not in profile else 0

    chall_total = sum(c.get("solved", 0) for c in challenges) if isinstance(challenges, list) else 0

    acad_done  = academy.get("modules_completed", "?")
    acad_total = academy.get("modules_total", "?")

    md = f"""---
layout: htb_dashboard
title: HTB Progress
---

# HackTheBox Progress Dashboard
*Last updated: {now_fmt}*

## Rank & XP

| Metric | Value |
| :--- | :--- |
| **Rank** | `{rank}` (Level {level}) |
| **Total XP** | {xp:,} |
| **Active Streak** | {streak} days |
| **Points** | {points} |

## Machines

| Metric | Value |
| :--- | :--- |
| **User Owns** | {u_owns} |
| **Root/System Owns** | {r_owns} |

## Challenges

| Metric | Value |
| :--- | :--- |
| **Total Solved** | {chall_total} |

## HTB Academy

| Metric | Value |
| :--- | :--- |
| **Modules Completed** | {acad_done} / {acad_total} |
"""

    with open("index.md", "w", encoding="utf-8") as f:
        f.write(md)
    print("  ✓ index.md written")
    print("Build complete.")


if __name__ == "__main__":
    main()
