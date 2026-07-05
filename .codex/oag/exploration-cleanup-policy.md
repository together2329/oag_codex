# OAG Exploration Cleanup Policy

Architecture exploration is reversible knowledge until scope lock. Before a
candidate can influence locked scope, cleanup must prove that exploration did
not leak provisional variants, worktrees, or undocumented public knobs into
authored product artifacts.

Use:

```bash
python3 .codex/scripts/oag_exploration_cleanup_check.py --ip-dir <ip> --json
```

The cleanup check blocks lock readiness when:

- architecture artifacts exist without exactly one selected, promoted, or
  collapsed candidate;
- unselected candidates remain alive instead of pruned or archived with
  `pruned_reason`;
- retained generate options lack a decision row link, configuration-model
  entry, or matching verification-plan configuration;
- public parameters lack a product rationale;
- provisional decision rows remain after checkpoint review has started;
- authored product paths contain `OAG-BEGIN-PROVISIONAL`,
  `OAG-END-PROVISIONAL`, or references to `knowledge/arch_exploration`;
- `.oag_worktrees/` entries or `oag/dse/*` branches remain.

Cleanup preserves evidence under `knowledge/arch_exploration/`. Prune helpers
remove worktrees and DSE branches only; receipts, sweeps, scoreboards, bench
results, and archived candidate rows remain available for lock review.
