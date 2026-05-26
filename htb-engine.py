import os
import requests
from datetime import datetime

def fetch_htb_labs(token):
    """Module 1: Fetches data from the HTB Labs V4 API."""
    if not token:
        return {"error": "Token not found in environment."}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mikey-CyberEngine/1.0"
    }
    
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
    except Exception as e:
        print(f"Error fetching HTB Labs: {e}")
        return {"error": "API Request Failed"}

def generate_markdown(labs_data):
    """Generates the final markdown page by combining all modules."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md = f"# CyberActivity Engine\n"
    md += f"*Last system update: {now}*\n\n"
    
    md += "##  Hack The Box: Active Labs\n"
    if "error" in labs_data:
        md += f"> **Status:** System Offline ({labs_data['error']})\n"
    else:
        md += "| Metric | Value |\n"
        md += "| :--- | :--- |\n"
        md += f"| **Operator** | `{labs_data['username']}` |\n"
        md += f"| **Current Rank** | {labs_data['rank']} |\n"
        md += f"| **System Owns (Root)** | {labs_data['system_owns']} |\n"
        md += f"| **User Owns** | {labs_data['user_owns']} |\n"
        md += f"| **Respect** | {labs_data['respect']} |\n"
        
    md += "\n## 🎓 HTB Academy Progress\n"
    md += "*Module pending API endpoint discovery.*\n"
    
    md += "\n## 💻 GitHub Engineering\n"
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
