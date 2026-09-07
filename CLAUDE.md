@AGENTS.md

<!--
AGENTS.md is the single source of truth, so every coding agent reads the same
instructions. Claude Code does not read AGENTS.md natively; the import above is
what loads it. Keep project content in AGENTS.md — add only Claude-specific
instructions below this line.
-->

## GitHub CLI

`gh` is installed, but **it is often not on `PATH` in this session**. It was
installed after some sessions started, and a session inherits the environment
as it was when it launched — that snapshot never refreshes. `command -v gh` and
`Get-Command gh` both come back empty even though the tool is there.

Call it by its full path:

```bash
"C:/Program Files/GitHub CLI/gh.exe" issue list
```

In PowerShell the path needs the call operator:

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" issue list
```

Do not conclude `gh` is missing, and do not offer to install it — check the
full path first. It is authenticated as `mmper-dev` with `repo`, `workflow`,
`gist` and `read:org` scopes, so issues, milestones and PRs all work.

### Two things that trip up `gh api`

**Query parameters are not flags.** `--state` is a flag on `gh issue list` but
not on `gh api`, where it belongs in the URL. This fails with `unknown flag`:

```bash
gh api repos/OWNER/REPO/milestones --state all   # wrong
```

```bash
gh api "repos/OWNER/REPO/milestones?state=all"   # right
```

**`git push` working does not mean `gh` is authenticated.** Git uses Windows
Credential Manager; `gh` keeps its own token. Either can work while the other
does not. `gh auth login` is interactive and opens a browser, so it is the
user's to run, not something to attempt from a tool call.

## Shell

Both Bash (Git Bash) and PowerShell are available. Bash is usually the better
choice here: chaining, `&` backgrounding, `timeout` and `curl` all behave as
expected, and heredocs make multi-line commit messages straightforward.

A quoted heredoc occasionally fails to parse on long markdown bodies. When that
happens, write the file with the Write tool rather than fighting the shell.

## Scratch files

Use the session scratchpad directory for throwaway scripts — bulk issue
creation, one-off migrations of tracker state — rather than the project tree or
`$TEMP`. Those scripts are working files, not deliverables, and should not end
up in git.
