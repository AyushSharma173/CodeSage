# backend/app/repo_handler.py
import os
import tempfile
import git
from urllib.parse import urlparse

def clone_repo(repo_url: str) -> str:
    """
    Clones a GitHub repo to a temporary directory and returns the local path.
    """
    try:
        # Parse repo name from URL
        parsed_url = urlparse(repo_url)
        repo_name = os.path.splitext(os.path.basename(parsed_url.path))[0]

        # Clone into a temp directory
        temp_dir = tempfile.mkdtemp(prefix="repo_")
        repo_path = os.path.join(temp_dir, repo_name)
        git.Repo.clone_from(repo_url, repo_path)

        print(f"[+] Cloned repo to {repo_path}")
        return repo_path

    except Exception as e:
        print(f"[!] Error cloning repo: {e}")
        raise
