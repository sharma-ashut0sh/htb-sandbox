import os
import requests
from datetime import datetime

def fetch_htb_labs(token):
    """Module 1: Fetches data from the live HTB Experience API."""
    if not token:
        return {"error": "CRITICAL: HTB_LABS_TOKEN is missing from GitHub environment secrets."}
    
    clean_token = token.strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # REVERTED: Back to the working endpoint you found
    url = "https://labs.hackthebox.com/api/experience/v1/account/9d7ea1a6-d26f-4522-b039-146c00b8b27b"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        data = response.json()
        
        return {
            "rank": data.get('levelTitle', 'Unknown'),
            "level": data.get('level', 0),
            "xp": data.get('totalExperiencePoints', 0),
            "streak": data.get('streakData', {}).get('counter', 0)
        }
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}: HTB server rejected the request."}
    except Exception as e:
        return {"error": f"Connection Failed: {str(e)}"}

def generate_markdown(labs_data):
    """Generates the final markdown page by combining all modules."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md = f"# CyberActivity Engine\n"
    md += f"*Last system update: {now}*\n\n"
    
    md += "## Hack The Box: Active Labs\n\n"
    
    if "error" in labs_data:
        md += f"> **Status:** System Offline ({labs_data['error']})\n\n"
    else:
        # THE FIX: Proper Markdown table spacing restored
        md += "| Metric | Value |\n"
        md += "| :--- | :--- |\n"
        md += f"| **Current Rank** | `{labs_data['rank']}` (Level {labs_data['level']}) |\n"
        md += f"| **Total XP** | {labs_data['xp']} |\n"
        md += f"| **Active Streak** | {labs_data['streak']} Days |\n\n"
        
    md += "## HTB Academy Progress\n\n"
    md += "*Module pending API endpoint discovery.*\n\n"
    
    md += "## 💻 GitHub Engineering\n\n"
    md += "*Module pending GraphQL integration.*\n"
    
    return md

def main():
    labs_token = os.getenv('HTB_LABS_TOKEN')
    
    print("Executing HTB Labs fetch...")
    labs_data = fetch_htb_labs(labs_token)
    
    print("Compiling Markdown dashboard...")
    md_content = generate_markdown(labs_data)
    
    with open("index.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    print("Build complete.")

if __name__ == "__main__":
    main()
