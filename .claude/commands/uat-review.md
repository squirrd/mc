---
name: uat-review
description: Review UAT test coverage for one or more features, analyze source + git commits since last review, and propose new/improved TCs
argument-hint: "<feature|[f1, f2, f3]> [optional focus description]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Act as a Senior QA Engineer. For each requested feature, analyze the feature's source code and git history since the last UAT review, then propose new or improved UAT test cases following the established TC format. Improve coverage across: happy paths, UX quality, data integrity, edge cases, and — where relevant — both host and agent runtime modes.
</objective>

<context>
@tests/uat/features/
@tests/uat/data/feature_map.json
@tests/uat/data/feature_meta.json
@tests/uat/README.md
</context>

<process>

<step name="parse_args">
Parse the skill arguments to build a feature list and optional focus description.

**Accepted formats:**
- Single short key: `cmt`
- Single full name: `comments`
- Bracket list (any spacing/quoting): `[att, check, cmt, url]`
- Space-separated: `att chk cmt`
- Mixed: `[attachments, cmt] focus on streaming output`

**Resolution algorithm:**
1. Read `tests/uat/data/feature_map.json`.
2. Build an alias index: for every feature key in every binary section, map each entry in `aliases` → canonical short key (e.g., `"attachments"` → `"att"`, `"comments"` → `"cmt"`).
3. Strip any bracket characters (`[`, `]`) and commas from the raw argument string.
4. Walk the tokens left-to-right. For each token:
   - If it resolves in the alias index → add that canonical key to the feature list.
   - Otherwise → treat it and all remaining tokens as the optional focus description.
5. Deduplicate the feature list while preserving order.

If no feature resolves, use AskUserQuestion to ask which feature(s) to review.

Print the resolved list before proceeding: `Reviewing: att, chk, cmt, url`.
</step>

<step name="review_loop">
For **each** resolved feature key, run steps `load_feature_context` through `write_updates` in sequence. Complete all steps for one feature before moving to the next.

Before starting each feature, print a header: `--- Reviewing: <key> (<name>) ---`
</step>

<step name="load_feature_context">
1. Read `tests/uat/data/feature_map.json` and locate the entry for this feature key. Extract:
   - `source_paths`, `prefixes`, `modes`, `mode_notes`
2. Read the existing feature file `tests/uat/features/<key>.md` to understand current TC coverage.
3. Read `tests/uat/data/feature_meta.json` to find the `last_review` date and `last_review_commit` for this feature.
   - If no prior review: use git's first commit date for the feature's source files as the since-date.
</step>

<step name="analyze_git_changes">
Run the git analysis script to find commits that touched this feature since the last review:

```bash
python3 scripts/uat/analyze_git.py --since <last_review_date_or_30_days_ago> --feature <key>
```

Parse the JSON output. Note the commit subjects — these are candidate areas where test coverage may be missing.
</step>

<step name="review_source_code">
Read each source file listed in `source_paths` for this feature:
- Identify all public-facing behaviors: commands, flags, error paths, config interactions, output formats
- Note which behaviors are mode-specific (host-only, agent-only, or both) using `modes` and `mode_notes` from the feature map
- Cross-reference against existing TCs in the feature file
- Identify gaps: behaviors that exist in source but have no TC

If a focus description was provided, pay special attention to code paths related to that description.
</step>

<step name="identify_coverage_gaps">
Apply the 80/20 UAT framework to identify the highest-value missing TCs:

1. **End-to-end workflows** — are the primary user journeys covered as stories?
2. **UX quality** — progress indicators, helpful error messages, sensible defaults
3. **Data integrity** — does the CLI leave config/state in a clean expected state?
4. **Edge case resilience** — at least 2 destructive/negative tests (invalid input, network failure, interrupted process)
5. **Mode coverage** — if the feature supports both `host` and `agent` modes, check that TCs exist for each mode. Behavior differences (noted in `mode_notes`) must be tested separately, not assumed identical.

Categorize gaps by severity: Critical (core workflow untested) / Medium (edge case) / Low (UX polish).

When a gap is mode-specific, label it clearly: `[host-only]`, `[agent-only]`, or `[both modes]`.
</step>

<step name="propose_tcs">
For each gap, draft a new TC in the established format:

```markdown
### TC-PREFIX-NN: Short description

**Pre-requires:** TC-XXXX-NN (reason) — or `none`
**Cross-deps:** TC-XXXX-NN (reason) — or `none`
**Tags:** tag1, tag2, tag3

**Goal:** One sentence.

**Steps:**
1. ...

**Expected:**
- ...

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**
```

**Mode tagging:**
- If the feature supports multiple modes, add a `mode: host` or `mode: agent` tag (in the **Tags** line) on every TC that is mode-specific.
- If a TC is valid in both modes, add `mode: host+agent` and include separate step variants or a note explaining the difference.
- Host-mode TCs run `mc <cmd>` on the local machine. Agent-mode TCs run `mc <cmd>` from inside a case container (`podman exec <container> mc <cmd>` or by opening the container shell).

Number new TCs sequentially after the highest existing number in this feature file.
Keep total new TCs to ≤ 5 per review per feature to maintain manageability. If more gaps exist, note them.

Also flag any existing TCs that should be updated (e.g. missing mode tags on TCs for dual-mode features).
</step>

<step name="present_proposals">
Present to the user:
1. **Summary:** what changed in git, what source paths were reviewed, prior coverage count, modes supported
2. **New TCs proposed:** each TC with rationale (which gap it fills, which commit it relates to, which mode)
3. **Existing TCs to update:** any edits recommended to existing TCs
4. **Gaps not addressed this review** (if > 5 new TCs were identified, list the deprioritized ones)

Ask: "Shall I write these to `tests/uat/features/<key>.md`? You can also tell me to skip or adjust any TC."

If reviewing multiple features, collect all approvals before writing, or ask per-feature — follow the user's preference.
</step>

<step name="write_updates">
If the user approves (for each approved feature):
1. Add new TCs to the feature file (append to the appropriate Story section, or create a new Story)
2. Update the Coverage Map table at the bottom of the feature file
3. Update `tests/uat/data/feature_meta.json` with:
   ```json
   {
     "features": {
       "<key>": {
         "last_review": "<today_YYYY-MM-DD>",
         "last_review_commit": "<latest_git_hash>"
       }
     }
   }
   ```
4. Update `tests/uat/STATUS.md` TC count row for this feature

Report what was written, then move to the next feature in the list.
</step>

</process>
