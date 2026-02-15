# Task 5 — Shell Git Client Adapter

## Objective

Implement the Git client adapter responsible for repository synchronization in the core flow:
- clone when the repo does not exist locally
- pull when the repo already exists locally

This is the infrastructure implementation of `GitClientPort`.

## What was implemented (high level)

File changed:
- `src/git_workspace_tool/adapters/git_client/shell_git_client.py`

Key behavior:
1. `clone(clone_url, local_path)`
   - returns early if the target path already exists
   - ensures parent directory exists
   - executes `git clone <clone_url> <local_path>`

2. `pull(local_path)`
   - validates that `local_path` exists
   - validates that `.git` exists under `local_path`
   - executes `git pull` in that directory

3. Shared command execution helper
   - runs git commands through `subprocess.run`
   - captures stdout/stderr
   - applies timeout protection
   - raises clear `RuntimeError` messages for:
     - git not found
     - command timeout
     - non-zero exit with captured output

## How we verified it

Validation done in a local integration run (no external network):
1. Create a temporary bare git repository as remote.
2. Create a source repository with an initial commit and push.
3. Run scanner once using the shell git adapter:
   - expected: local clone is created.
4. Push a second commit to the remote.
5. Run scanner again:
   - expected: local clone is updated via pull.
6. Assert file contents changed from first commit to second commit.

Observed result:
- Clone + pull behavior passed end-to-end.

## Why this is acceptable

- Matches Task 5 acceptance criteria from the implementation plan.
- Keeps git operations isolated in one adapter (`GitClientPort` implementation).
- Fails fast with actionable messages, which helps operational troubleshooting.
- Preserves core boundary: orchestration code does not execute shell commands directly.
