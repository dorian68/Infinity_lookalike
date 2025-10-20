"""Utility for merging all local Git branches into ``master``.

This script mirrors the "merge all into master" operation that users often
perform in GitHub when consolidating diverged work.  It can fetch remote
branches, optionally create ``master`` if it does not exist, and iterate
through the remaining branches to merge them sequentially.

By default the script runs in **dry-run** mode so you can review the commands
that would be executed.  Pass ``--execute`` once you are confident the merge
order is correct.
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass
class CommandResult:
    command: Sequence[str]
    stdout: str
    stderr: str
    returncode: int

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return "Command: {cmd}\nReturn code: {code}\nSTDOUT:\n{out}\nSTDERR:\n{err}".format(
            cmd=" ".join(self.command),
            code=self.returncode,
            out=self.stdout.strip(),
            err=self.stderr.strip(),
        )


def run_git(cmd: Sequence[str], *, check: bool = True) -> CommandResult:
    """Run a git command and return its captured output."""

    result = subprocess.run(
        ["git", *cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(cmd)} failed with code {result.returncode}: {result.stderr.strip()}"
        )
    return CommandResult(command=["git", *cmd], stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)


def ensure_clean_worktree() -> None:
    status = run_git(["status", "--porcelain"], check=False)
    if status.stdout.strip():
        raise RuntimeError(
            "Your working tree has uncommitted changes. Commit or stash them before merging branches."
        )


def list_branches() -> List[str]:
    result = run_git(["branch", "--format", "%(refname:short)"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def create_master(source: str, *, execute: bool) -> None:
    if execute:
        run_git(["branch", "master", source])
    else:
        print(f"DRY-RUN: git branch master {source}")


def checkout(branch: str, *, execute: bool) -> None:
    if execute:
        run_git(["checkout", branch])
    else:
        print(f"DRY-RUN: git checkout {branch}")


def merge(branch: str, *, allow_ff: bool, execute: bool) -> None:
    args = ["merge"]
    if not allow_ff:
        args.append("--no-ff")
    args.append(branch)
    if execute:
        run_git(args)
    else:
        print("DRY-RUN:", "git", " ".join(args))


def fetch_remotes(*, execute: bool) -> None:
    if execute:
        run_git(["fetch", "--all"])
    else:
        print("DRY-RUN: git fetch --all")


def consolidate_branches(
    *,
    create_master_from: str | None,
    ignore_branches: Iterable[str],
    execute: bool,
    allow_fast_forward: bool,
) -> None:
    ensure_clean_worktree()

    fetch_remotes(execute=execute)

    branches = list_branches()
    ignore = set(ignore_branches)

    if "master" not in branches:
        if not create_master_from:
            raise RuntimeError(
                "No 'master' branch found. Provide --create-master-from <branch> to create it."
            )
        if create_master_from not in branches:
            raise RuntimeError(f"Source branch '{create_master_from}' does not exist.")
        create_master(create_master_from, execute=execute)
        branches = list_branches()

    checkout("master", execute=execute)

    for branch in branches:
        if branch == "master" or branch in ignore:
            continue
        checkout("master", execute=execute)
        print(f"Merging branch '{branch}' into master{' (dry-run)' if not execute else ''}...")
        merge(branch, allow_ff=allow_fast_forward, execute=execute)

    if not execute:
        print("\nDry-run complete. Re-run with --execute to perform the merges.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge all local branches into master.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the merges instead of printing the commands.",
    )
    parser.add_argument(
        "--create-master-from",
        metavar="BRANCH",
        help="Create master from the specified branch if it does not exist.",
    )
    parser.add_argument(
        "--ignore",
        metavar="BRANCH",
        nargs="*",
        default=(),
        help="Branches to skip during the merge process.",
    )
    parser.add_argument(
        "--allow-fast-forward",
        action="store_true",
        help="Allow fast-forward merges (default is --no-ff).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    consolidate_branches(
        create_master_from=args.create_master_from,
        ignore_branches=args.ignore,
        execute=args.execute,
        allow_fast_forward=args.allow_fast_forward,
    )


if __name__ == "__main__":
    main()
