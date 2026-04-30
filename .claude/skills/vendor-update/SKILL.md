---
name: vendor-update
description: Upgrade the vendored NeMo-Skills slice to a newer upstream commit. Use when the user asks to "bump vendored", "sync NeMo-Skills", "update vendored sha", "upgrade NS", or wants to pull a specific upstream fix. Inside the sgl-eval repo.
---

# Update the vendored NeMo-Skills slice

## 1. Pick the new SHA

If the user supplies a SHA / tag, use it. Otherwise:

```bash
gh api repos/NVIDIA/NeMo-Skills/branches/main --jq .commit.sha
```

## 2. Diff what changed in the directories we vendor

```bash
old=$(python -c "import yaml; print(yaml.safe_load(open('sgl_eval/_vendored/nemo_skills/SOURCES.yaml'))['synced_from_sha'])")
new=<new SHA>
gh api "repos/NVIDIA/NeMo-Skills/compare/${old}...${new}" \
  --jq '.files[] | select(
        .filename | startswith("nemo_skills/evaluation/")
                 or startswith("nemo_skills/dataset/")
                 or startswith("nemo_skills/prompt/config/")
                 or startswith("tests/")
       ) | {filename, status, additions, deletions}'
```

Surface anything non-trivial to the user before proceeding. Look
specifically for changes to: `math_grader.py`, `evaluator/math.py`,
`evaluator/mcq.py`, `metrics/base.py`, `metrics/math_metrics.py`,
`prompt/config/generic/math.yaml`, and any vendored test file.

## 3. Update `SOURCES.yaml`

```yaml
synced_from_sha: <new SHA>
synced_at: "<YYYY-MM-DD>"
```

If the upstream `requirements/core.txt` pins of `math_verify` /
`latex2sympy2_extended` / `numpy` changed at the new SHA, update
`pyproject.toml` dependencies to match.

> **Pinned-deps policy.** The pip deps that vendored files import
> (currently `math_verify`, `latex2sympy2_extended`, plus their
> transitive `sympy` / `numpy`) must be installable at versions that
> reproduce upstream's behavior. Track upstream's
> `requirements/core.txt`. If a transitive dep major-bumps and breaks
> vendored tests, add an upper bound in `pyproject.toml` instead of
> patching vendored code.

## 4. Sync

```bash
python scripts/sync_vendored.py
```

## 5. Verify

```bash
pytest
```

The vendored NS tests under `sgl_eval/_vendored/nemo_skills/tests/`
directly exercise the synced code with the current dep versions. Their
pass/fail status IS the drift detector.

If any vendored NS test fails, **do not push and ignore**. Two paths:

a) **Behavior change is intentional upstream**. Read the relevant
   upstream commit; understand the rationale. If we want the new
   behavior, accept it and move on. If we want the old behavior,
   either pick an earlier commit or pin an older version of the
   offending dep (`math_verify` / `latex2sympy2_extended` / `sympy`)
   in `pyproject.toml`.

b) **Spurious failure due to dep version drift**. Check
   `pip show math_verify latex2sympy2_extended sympy`. If a transitive
   dep recently major-bumped, restrict it via `pyproject.toml` upper
   bound and re-run.

If sgl-eval's own tests break, the upstream API likely changed
(renamed function, new required field). Update glue under
`sgl_eval/evals/_*.py` minimally to follow.

## 6. Commit

```bash
git add -A
git commit -m "vendor: bump NeMo-Skills <old short>...<new short>"
```

Keep this commit single-purpose. No bundling unrelated edits.
