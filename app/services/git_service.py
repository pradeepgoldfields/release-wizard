"""Git synchronisation service.

Pulls a pipeline definition from a remote Git repository (reads the YAML file
at ``conduit/<pipeline-name>.yaml``) and imports it into the database,
or pushes the current database state back to Git as a YAML file.

Requires ``gitpython`` (``pip install gitpython``).
Degrades gracefully when gitpython is not installed or the repo URL is not set.
"""

from __future__ import annotations

import logging
import os
import tempfile

log = logging.getLogger(__name__)

_DEFINITION_PATH = "conduit/{name}.yaml"  # path inside the repo


def _git_available() -> bool:
    try:
        import git  # noqa: F401

        return True
    except ImportError:
        return False


def sync_pipeline_from_git(pipeline) -> dict:
    """Clone the pipeline's git_repo, read its YAML definition, and return
    the parsed spec dict ready to be handed to the import endpoint logic.

    Args:
        pipeline: A :class:`app.models.pipeline.Pipeline` instance.

    Returns:
        ``{"spec": <dict>, "sha": <str>}`` on success.

    Raises:
        RuntimeError: If gitpython is missing, git_repo is not set, or the
                      definition file does not exist in the repo.
    """
    if not _git_available():
        raise RuntimeError("gitpython is not installed — run: pip install gitpython")

    import git  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    repo_url = pipeline.git_repo
    branch = pipeline.git_branch or "main"
    if not repo_url:
        raise RuntimeError("Pipeline has no git_repo configured")

    def_path = _DEFINITION_PATH.format(name=pipeline.name)

    with tempfile.TemporaryDirectory() as tmpdir:
        log.info("Cloning %s (branch=%s) …", repo_url, branch)
        repo = git.Repo.clone_from(
            repo_url,
            tmpdir,
            branch=branch,
            depth=1,
            env=_git_env(),
        )
        sha = repo.head.commit.hexsha[:12]
        full_path = os.path.join(tmpdir, def_path)
        if not os.path.exists(full_path):
            raise RuntimeError(f"Definition file not found in repo: {def_path}")
        with open(full_path, encoding="utf-8") as fh:
            spec = yaml.safe_load(fh) or {}
        log.info("Loaded definition from %s @ %s", def_path, sha)
        return {"spec": spec, "sha": sha}


def push_pipeline_to_git(
    pipeline,
    yaml_text: str,
    author_name: str = "Conduit",
    author_email: str = "rw@conduit.local",
) -> str:
    """Serialise the pipeline definition as YAML and push it to Git.

    Args:
        pipeline: A :class:`app.models.pipeline.Pipeline` instance.
        yaml_text: The YAML string to write.
        author_name: Git commit author name.
        author_email: Git commit author e-mail.

    Returns:
        The new commit SHA (short, 12 chars).

    Raises:
        RuntimeError: If gitpython is missing or git_repo is not set.
    """
    if not _git_available():
        raise RuntimeError("gitpython is not installed — run: pip install gitpython")

    import git  # noqa: PLC0415

    repo_url = pipeline.git_repo
    branch = pipeline.git_branch or "main"
    if not repo_url:
        raise RuntimeError("Pipeline has no git_repo configured")

    def_path = _DEFINITION_PATH.format(name=pipeline.name)

    with tempfile.TemporaryDirectory() as tmpdir:
        log.info("Cloning %s (branch=%s) for push …", repo_url, branch)
        repo = git.Repo.clone_from(
            repo_url,
            tmpdir,
            branch=branch,
            depth=1,
            env=_git_env(),
        )
        # Ensure the directory exists
        full_dir = os.path.join(tmpdir, os.path.dirname(def_path))
        os.makedirs(full_dir, exist_ok=True)

        full_path = os.path.join(tmpdir, def_path)
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(yaml_text)

        repo.index.add([def_path])
        commit = repo.index.commit(
            f"chore: update {pipeline.name} pipeline definition [conduit]",
            author=git.Actor(author_name, author_email),
            committer=git.Actor(author_name, author_email),
        )
        origin = repo.remote("origin")
        origin.push(refspec=f"HEAD:{branch}", env=_git_env())
        sha = commit.hexsha[:12]
        log.info("Pushed definition to %s @ %s", def_path, sha)
        return sha


def _git_env() -> dict:
    """Return env vars for git operations (SSH key / token from environment)."""
    env = {}
    token = os.getenv("GIT_TOKEN")
    if token:
        # For HTTPS repos: inject credentials via GIT_ASKPASS helper pattern
        env["GIT_ASKPASS"] = "echo"
        env["GIT_USERNAME"] = "x-token"
        env["GIT_PASSWORD"] = token
    ssh_key = os.getenv("GIT_SSH_KEY_PATH")
    if ssh_key:
        env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key} -o StrictHostKeyChecking=no"
    return env or None
