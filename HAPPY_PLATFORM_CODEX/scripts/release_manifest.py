"""Record immutable release identities from clean checked-out Git sources.

Run after required checks. Output outside the checkout: a commit cannot contain
its own SHA. CI publishes this manifest as an artifact of the exact successful run.
This file records identity and evidence, never deployment or programme approval.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={repository.as_posix()}",
            "-C",
            str(repository),
            *arguments,
        ],
        text=True,
    ).rstrip("\r\n")


def identity(repository: Path) -> str:
    if git(repository, "status", "--porcelain=v1", "--untracked-files=normal"):
        raise ValueError("Release source checkout must be clean.")
    sha = git(repository, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Release identity must be a full Git SHA.")
    return sha


def migration_head() -> str:
    revisions: set[str] = set()
    parents: set[str] = set()
    for source in (ROOT / "database/migrations/versions").glob("[0-9]*.py"):
        metadata = {}
        for node in ast.parse(source.read_text()).body:
            if isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            else:
                continue
            if (
                isinstance(target, ast.Name)
                and target.id in {"revision", "down_revision"}
                and value is not None
            ):
                metadata[target.id] = ast.literal_eval(value)
        revisions.add(metadata["revision"])
        previous = metadata["down_revision"]
        if isinstance(previous, str):
            parents.add(previous)
        elif previous:
            parents.update(previous)
    heads = revisions - parents
    if len(heads) != 1:
        raise ValueError("Release migrations must have exactly one head.")
    return heads.pop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unijay", required=True, type=Path)
    parser.add_argument("--expected-unijay-sha", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    happy = identity(REPOSITORY)
    unijay = identity(args.unijay.resolve())
    if unijay != args.expected_unijay_sha:
        raise ValueError("Collector checkout differs from the reviewed release SHA.")
    definition = (REPOSITORY / args.deployment).resolve()
    if not definition.is_relative_to(REPOSITORY) or not definition.is_file():
        raise ValueError("Deployment definition must be a tracked repository file.")
    relative = definition.relative_to(REPOSITORY).as_posix()
    git(REPOSITORY, "ls-files", "--error-unmatch", relative)
    run_id = os.environ.get("GITHUB_RUN_ID")
    result = {
        "happy_sha": happy,
        "unijay_sha": unijay,
        "migration_head": migration_head(),
        "release_version": (ROOT / "VERSION").read_text().strip(),
        "parser": {
            "happy_sha": happy,
            "tree_sha": git(REPOSITORY, "rev-parse", "HEAD:CV-Parser-main/cv_system_output"),
        },
        "deployment_definition": relative,
        "deployment_sha256": hashlib.sha256(definition.read_bytes()).hexdigest(),
        "source_checkouts_clean": True,
        "ci_run": f"https://github.com/OffgengStudios/HAPPY-ONE/actions/runs/{run_id}"
        if run_id
        else None,
        "deployment_approved": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Release identities recorded for {happy} and {unijay}.")


if __name__ == "__main__":
    main()
