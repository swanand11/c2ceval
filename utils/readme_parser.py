import os
import re

def extract_team_info(repo_path):
    readme_path = os.path.join(repo_path, "README.md")

    data = {
        "team_name": "N/A",
        "all_women": "No",
        "all_junior": "No",
        "architecture_text": ""
    }

    if not os.path.exists(readme_path):
        return data

    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract team name
        team_name_match = re.search(r"- \*\*Team Name\*\*:\s*(.*)", content)
        data["team_name"] = team_name_match.group(1).strip() if team_name_match else "N/A"

        # Extract All-Female Team
        women_match = re.search(r"- \*\*All-Female Team\*\*:\s*(.*)", content, re.I)
        data["all_women"] = women_match.group(1).strip() if women_match else "No"

        # Extract Year from All-Junior
        junior_match = re.search(r"- \*\*Year\*\*:\s*(.*)", content, re.I)
        data["all_junior"] = junior_match.group(1).strip() if junior_match else "No"

        # Extract architecture text
        arch = re.search(r"## Architecture(.*)", content, re.S)
        if arch:
            data["architecture_text"] = arch.group(1).strip()[:3000]

        return data

    except:
        return data