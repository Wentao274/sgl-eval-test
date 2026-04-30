---
name: review-vendor-coverage
description: Audit whether all score-deciding logic in sgl-eval is vendored from NeMo-Skills, or whether some has crept into SE code. Use when the user asks "are we vendoring enough", "review vendor coverage", "audit vendoring", "is our vendoring complete", or before a release.
---

# Review vendor coverage

The principle (per `CLAUDE.md`): **anything that decides a score is
vendored verbatim from NeMo-Skills**. SE code is allowed only for
transport, glue, default config, and CLI / output formatting.

This skill audits whether SE code has leaked scoring logic. It does NOT
auto-fix; vendoring more is a design call the user makes after seeing
the report.

## 1. Enumerate SE files

```bash
find sgl_eval scripts tests -name "*.py" \
  | grep -v _vendored | grep -v __pycache__ | sort
```

## 2. Classify each into one of four buckets

For each file (and each function within larger files), ask:
**"Does this code decide a score?"**

| Bucket | Description | Examples | Action |
|---|---|---|---|
| **Transport** | Wraps an external service or a Python primitive. No scoring decisions. | sampler, runner, cli, types, registry, metrics formatter | OK as SE. |
| **Glue** | Bridges between vendored API and our runtime model. Necessary because of architectural difference (sync vs async, in-memory vs file, single vs batch). | `_predictions.py`, `_loader.py`, `_eval_single_sync`, `_score_via_eval_mcq` | OK as SE. Document the upstream API it bridges. |
| **Default config** | Per-benchmark sampling / repeat / thinking defaults. Model-dependent, not a scoring decision. | `_TABLE` rows in `_registry.py` | OK as SE. Confirm tracks NS-aligned defaults. |
| **Score-deciding** | Code that parses generation, compares answers, computes pass@k, renders prompts beyond `str.format`. | (should be empty in SE!) | RED FLAG. See step 4. |

## 3. Specific spots to scrutinize (grey areas)

Known borderline pieces -- not violations, but watch for drift:

| Location | What it does | Why grey |
|---|---|---|
| `evals/_prompts.py:render_prompt` | `yaml.safe_load + str.format` on vendored yaml | Re-implements upstream's prompt subsystem (~500 lines). Equivalent today because templates only use `{problem}` / `{examples}`. Drift if upstream adds richer templating. |
| `evals/_math.py:aggregate_with_math_metrics` (padding) | `while len < n_repeats: append dup` | NS doesn't pad; we pad to keep `MathMetrics` happy under partial sample failure. Affects score only when sampler fails partway. |
| `evals/_math.py:_flatten_math_metrics` and `_multichoice.py:_flatten` | Picks fields out of `MathMetrics.get_metrics()` nested dict | Display selection, not computation. Safe if upstream keeps the same field names. |
| `_TABLE` `thinking` / `n_repeats` | Per-benchmark sgl-eval defaults | Not a violation; runtime config. CLI override always wins. |

If a new grey area surfaces during the audit, add a row.

## 4. If you find score-deciding code in SE

Don't auto-edit. Report to the user:

1. **What** it computes (the scoring decision in plain words).
2. **Where** in NS upstream the equivalent lives (or "not in NS").
3. **What it would take to vendor it**: file path(s), import rewrites,
   any drop_imports/drop_functions needed.

Then ask the user whether to:
- vendor (run `vendor-update` workflow with extended `SOURCES.yaml`),
- keep as SE (document the deviation, e.g., in CLAUDE.md grey-area list),
- or remove the logic entirely.

## 5. Output format

Write a short report (under 300 words):

```
SE files: <count> total
  transport       : <n> (<list>)
  glue            : <n> (<list>)
  default config  : <n> (<list>)
  score-deciding  : <n> (RED if > 0)

Grey areas reviewed:
  - <location>: <still acceptable / has drifted because X>

New findings:
  - <none> | <list>

Recommendation: <one sentence>
```
