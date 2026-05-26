import os
import requests
from datetime import datetime

def fetch_htb_labs(token):
    """Module 1: Fetches data from the core HTB V4 API."""
    if not token:
        return {"error": "CRITICAL: HTB_LABS_TOKEN is missing from GitHub environment secrets."}
    
    clean_token = token.strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # Going back to the correct API endpoint for Machine/User Owns
    url = "https://www.hackthebox.com/api/v4/user/info"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        data = response.json()
        profile = data.get('info', {})
        
        return {
            "username": profile.get('name', 'Unknown'),
            "rank": profile.get('rankText', 'Unknown'),
            "system_owns": profile.get('system_owns', 0),
            "user_owns": profile.get('user_owns', 0),
            "respect": profile.get('respects', 0)
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
    
    # THE FORMATTING FIX: Added double newlines (\n\n) to force proper Markdown rendering.
    md += "## Hack The Box: Active Labs\n\n"
    
    if "error" in labs_data:
        md += f"> **Status:** System Offline ({labs_data['error']})\n\n"
    else:
        md += "| Metric | Value |\n"
        md += "| :--- | :--- |\n"
        md += f"| **Operator** | `{labs_data['username']}` |\n"
        md += f"| **Current Rank** | {labs_data['rank']} |\n"
        md += f"| **System Owns (Root)** | {labs_data['system_owns']} |\n"
        md += f"| **User Owns** | {labs_data['user_owns']} |\n"
        md += f"| **Respect** | {labs_data['respect']} |\n\n"
        
    md += "## HTB Academy Progress\n\n"
    md += "*Module pending API endpoint discovery.*\n\n"
    
    md += "## GitHub Engineering\n\n"
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
    print("✅ Build complete.")

if __name__ == "__main__":
    main()
