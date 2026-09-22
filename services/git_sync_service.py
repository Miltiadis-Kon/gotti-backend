import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Services mapping to directory names and docker compose service names
REPOS_CONFIG = [
    {
        "name": "gotti-backend",
        "dir_name": "gotti-backend",
        "service_name": "gotti-backend",
        "branch": "main"
    },
    {
        "name": "stock-alchemist",
        "dir_name": "stock-alchemist",
        "service_name": "stock-alchemist",
        "branch": "main"
    },
    {
        "name": "gotti-visualize",
        "dir_name": "gotti-visualize",
        "service_name": "gotti-visualize",
        "branch": "main"
    },
    {
        "name": "gotti-frontend",
        "dir_name": "gotti-frontend",
        "service_name": "gotti-frontend",
        "branch": "main"
    }
]


def run_git_cmd(repo_path: Path, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a git command in the specified repo directory."""
    cmd = ["git", "-C", str(repo_path)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False
    )


def run_docker_compose_reload(compose_dir: Path, service_name: str, timeout: int = 300) -> bool:
    """Rebuild and restart a specific Docker container service."""
    cmd = ["docker", "compose", "up", "-d", "--build", service_name]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(compose_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[ERROR] Failed to run docker compose reload for {service_name}: {e}")
        return False


class GitSyncManager:
    """
    Monitors all 4 repositories in the Gotti ecosystem.
    Fetches remote changes, pulls updates, and triggers container reload.
    """

    def __init__(self, root_repos_dir: Optional[str | Path] = None):
        env_root = os.getenv("REPOS_ROOT_DIR")
        if root_repos_dir:
            self.root_dir = Path(root_repos_dir).resolve()
        elif env_root:
            self.root_dir = Path(env_root).resolve()
        else:
            # Default to parent of gotti-backend or current directory
            current_path = Path(__file__).resolve()
            # If inside gotti-backend/services/
            if "gotti-backend" in current_path.parts:
                parts = list(current_path.parts)
                idx = parts.index("gotti-backend")
                # Construct path up to parent of gotti-backend
                self.root_dir = Path(parts[0]).joinpath(*parts[1:idx])
            else:
                self.root_dir = current_path.parent

    def get_repo_path(self, dir_name: str) -> Path:
        return self.root_dir / dir_name

    def check_repo_status(self, repo_info: Dict[str, str], do_fetch: bool = True) -> Dict[str, Any]:
        """
        Check if a single repository has remote changes pending.
        """
        name = repo_info["name"]
        dir_name = repo_info["dir_name"]
        service_name = repo_info["service_name"]
        target_branch = repo_info.get("branch", "main")
        repo_path = self.get_repo_path(dir_name)

        result: Dict[str, Any] = {
            "name": name,
            "service": service_name,
            "path": str(repo_path),
            "exists": repo_path.exists() and (repo_path / ".git").exists(),
            "branch": target_branch,
            "local_sha": None,
            "remote_sha": None,
            "commits_behind": 0,
            "new_commits": [],
            "status": "unknown",
            "message": "",
            "checked_at": datetime.utcnow().isoformat()
        }

        if not result["exists"]:
            result["status"] = "missing_repo"
            result["message"] = f"Directory {repo_path} or .git not found"
            return result

        try:
            # 1. Get current branch
            branch_proc = run_git_cmd(repo_path, ["branch", "--show-current"])
            current_branch = branch_proc.stdout.strip() or target_branch
            result["branch"] = current_branch

            # 2. Get local HEAD SHA
            local_proc = run_git_cmd(repo_path, ["rev-parse", "HEAD"])
            if local_proc.returncode != 0:
                result["status"] = "error"
                result["message"] = f"Failed to get local HEAD: {local_proc.stderr}"
                return result
            result["local_sha"] = local_proc.stdout.strip()

            # 3. Fetch remote if requested
            if do_fetch:
                fetch_proc = run_git_cmd(repo_path, ["fetch", "origin", current_branch], timeout=45)
                if fetch_proc.returncode != 0:
                    # Non-fatal if offline or no network
                    result["message"] = f"Fetch warning: {fetch_proc.stderr.strip()[:100]}"

            # 4. Get remote branch SHA
            remote_proc = run_git_cmd(repo_path, ["rev-parse", f"origin/{current_branch}"])
            if remote_proc.returncode == 0:
                result["remote_sha"] = remote_proc.stdout.strip()
            else:
                result["remote_sha"] = result["local_sha"]

            # 5. Check how many commits behind
            rev_list_proc = run_git_cmd(repo_path, ["rev-list", f"HEAD..origin/{current_branch}", "--count"])
            if rev_list_proc.returncode == 0:
                count_str = rev_list_proc.stdout.strip()
                result["commits_behind"] = int(count_str) if count_str.isdigit() else 0

            # 6. Get list of new commit messages if any
            if result["commits_behind"] > 0:
                log_proc = run_git_cmd(repo_path, ["log", f"HEAD..origin/{current_branch}", "--oneline", "-n", "10"])
                if log_proc.returncode == 0:
                    result["new_commits"] = [line.strip() for line in log_proc.stdout.strip().split("\n") if line.strip()]
                result["status"] = "updates_available"
                result["message"] = f"{result['commits_behind']} new commit(s) available on remote"
            else:
                result["status"] = "up_to_date"
                result["message"] = "Repository is up to date"

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)

        return result

    def sync_repo(self, repo_info: Dict[str, str], auto_reload: bool = True) -> Dict[str, Any]:
        """
        Check, fetch, pull changes for a repository, and reload Docker container if updated.
        """
        status_info = self.check_repo_status(repo_info, do_fetch=True)
        name = repo_info["name"]
        dir_name = repo_info["dir_name"]
        service_name = repo_info["service_name"]
        repo_path = self.get_repo_path(dir_name)

        status_info["pulled"] = False
        status_info["reloaded"] = False

        if status_info.get("commits_behind", 0) > 0:
            current_branch = status_info.get("branch", "main")
            print(f"[GIT] Updates detected for {name}: {status_info['commits_behind']} commit(s) behind origin/{current_branch}")
            for c in status_info.get("new_commits", []):
                print(f"      + {c}")

            # Pull changes
            pull_proc = run_git_cmd(repo_path, ["pull", "--ff-only", "origin", current_branch], timeout=60)
            if pull_proc.returncode != 0:
                # Try standard pull if ff-only is not cleanly applicable
                pull_proc = run_git_cmd(repo_path, ["pull", "origin", current_branch], timeout=60)

            if pull_proc.returncode == 0:
                status_info["pulled"] = True
                print(f"[GIT] [OK] Pulled latest updates for {name}")

                # Update local SHA after pull
                new_local_proc = run_git_cmd(repo_path, ["rev-parse", "HEAD"])
                if new_local_proc.returncode == 0:
                    status_info["local_sha"] = new_local_proc.stdout.strip()

                # Trigger Docker Reload
                if auto_reload:
                    print(f"[DOCKER] Rebuilding and reloading container for service: {service_name}...")
                    success = run_docker_compose_reload(self.root_dir, service_name)
                    status_info["reloaded"] = success
                    if success:
                        status_info["status"] = "updated_and_reloaded"
                        status_info["message"] = f"Successfully pulled {status_info['commits_behind']} commit(s) and reloaded container"
                        print(f"[DOCKER] [OK] Successfully reloaded {service_name}")
                    else:
                        status_info["status"] = "pulled_reload_failed"
                        status_info["message"] = "Pulled changes but container reload failed"
                        print(f"[DOCKER] [WARN] Container reload failed for {service_name}")
                else:
                    status_info["status"] = "updated_no_reload"
                    status_info["message"] = "Successfully pulled changes (auto-reload skipped)"
            else:
                status_info["status"] = "pull_failed"
                status_info["message"] = f"Git pull failed: {pull_proc.stderr.strip()}"
                print(f"[GIT] [ERROR] Pull failed for {name}: {pull_proc.stderr.strip()}")

        return status_info

    def sync_all(self, auto_reload: bool = True) -> Dict[str, Any]:
        """
        Check and sync all 4 repositories across the ecosystem.
        """
        results = []
        any_updates = False
        reloaded_services = []

        for repo_info in REPOS_CONFIG:
            res = self.sync_repo(repo_info, auto_reload=auto_reload)
            results.append(res)
            if res.get("pulled"):
                any_updates = True
            if res.get("reloaded"):
                reloaded_services.append(res["service"])

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "root_dir": str(self.root_dir),
            "any_updates": any_updates,
            "reloaded_services": reloaded_services,
            "repositories": results
        }

    def check_all_status(self, do_fetch: bool = True) -> Dict[str, Any]:
        """
        Check status for all 4 repositories without pulling.
        """
        results = []
        for repo_info in REPOS_CONFIG:
            results.append(self.check_repo_status(repo_info, do_fetch=do_fetch))

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "root_dir": str(self.root_dir),
            "repositories": results
        }


# Singleton instance
git_sync_service = GitSyncManager()
