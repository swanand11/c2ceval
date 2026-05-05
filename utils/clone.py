import os
import shutil
import subprocess

CLONE_DIR = "repos"

def clone_repo(repo_url, timeout=30):
    os.makedirs(CLONE_DIR, exist_ok=True)

    repo_name = repo_url.split("/")[-1].replace(".git", "")
    path = os.path.join(CLONE_DIR, repo_name)

    if os.path.exists(path):
        shutil.rmtree(path)

    try:
        if not repo_url.endswith(".git"):
            repo_url = repo_url + ".git"
        
        # Use subprocess with timeout instead of Repo.clone_from for timeout control
        subprocess.run(
            ["git", "clone", repo_url, path],
            timeout=timeout,
            capture_output=True,
            text=True
        )
        return path
    except subprocess.TimeoutExpired:
        print(f"Clone timeout: {repo_url}")
        if os.path.exists(path):
            shutil.rmtree(path)
        return None
    except Exception as e:
        print(f"Clone failed: {repo_url}, {e}")
        if os.path.exists(path):
            shutil.rmtree(path)
        return None