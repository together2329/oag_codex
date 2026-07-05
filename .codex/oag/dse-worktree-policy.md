# OAG DSE Worktree Isolation Policy

`oag_dse_worktree.py` isolates design-space exploration candidates from product
RTL/TB work.

Tier A is skeleton-only. It creates candidate state under
`<ip>/knowledge/arch_exploration/<run_id>/<candidate>/` and does not create a
git worktree.

Tier B uses an IP-local git worktree when git is available and the IP directory
is a git repository. Worktrees live under `<ip>/.oag_worktrees/<candidate>/`
and use branches named `oag/dse/<mission>/<candidate>`. If git or git-worktree
support is unavailable, creation degrades explicitly in JSON with a warning and
keeps only Tier A-style knowledge state.

The helper accepts only single-segment run, mission, and candidate IDs. It
rejects absolute paths, nested paths, `.`/`..`, unsupported characters, and
resolved paths outside the intended DSE roots.

Copy-back writes only to `knowledge/arch_exploration`. It refuses source trees
containing `rtl/`, `tb/`, `.git/`, `.oag_worktrees/`, symlinks, or traversal
components, and never writes product RTL/TB paths in the main IP tree.

`list` reports stale hazard data for orchestration consumers, including missing
worktree paths, dirty worktrees, and git-status failures.
