---
name: add-benchmark
description: Add a new benchmark to sgl-eval by vendoring its NeMo-Skills dataset module and registering it in `_TABLE`. Use when the user asks to "add <benchmark>" / "support <benchmark>" / "register <benchmark>" inside the sgl-eval repo.
---

# Adding a benchmark

Don't skip step 1. If NS doesn't have the benchmark, this becomes a
heavier `add-metrics-type` task instead, not this skill.

## 1. Verify upstream coverage

```bash
SHA=$(python -c "import yaml; print(yaml.safe_load(open('sgl_eval/_vendored/nemo_skills/SOURCES.yaml'))['synced_from_sha'])")
gh api "repos/NVIDIA/NeMo-Skills/contents/nemo_skills/dataset/<name>?ref=$SHA" \
  --jq '.[] | .name'
gh api "repos/NVIDIA/NeMo-Skills/contents/nemo_skills/dataset/<name>/__init__.py?ref=$SHA" \
  --jq '.content' | base64 -d
```

Confirm:
- The directory exists.
- `METRICS_TYPE` is one of `math`, `multichoice` (the wired-up types).
  Otherwise stop and ask the user; this skill cannot proceed.
- `GENERATION_ARGS` contains a `++prompt_config=...` (the prompt yaml
  basename will be auto-derived).

## 2. Add source files to `SOURCES.yaml`

Always append the dataset `__init__.py`:

```yaml
- src: nemo_skills/dataset/<name>/__init__.py
  dst: dataset/<name>/__init__.py
```

Then **exactly one** data-source entry, depending on what the upstream
benchmark ships:

- **If upstream has `dataset/<name>/prepare.py`** (benchmark downloads
  from HuggingFace / a URL at prepare time):

  ```yaml
  - src: nemo_skills/dataset/<name>/prepare.py
    dst: dataset/<name>/prepare.py
  ```

- **Else if upstream has `dataset/<name>/test.txt`** (questions bundled
  as jsonl-in-txt):

  ```yaml
  - src: nemo_skills/dataset/<name>/test.txt
    dst: dataset/<name>/test.txt
    binary: true
  ```

- Else stop -- this skill only covers the two loaders sgl-eval wires.

If the prompt yaml referenced by `GENERATION_ARGS` is one we already
vendor (`math.yaml`, `mcq-4choices.yaml`, `mcq-4choices-boxed.yaml`),
no further yaml entry is needed. Otherwise, also add the prompt:

```yaml
- src: nemo_skills/prompt/config/<path>.yaml
  dst: prompts/<basename>.yaml
```

## 3. Run sync

```bash
python scripts/sync_vendored.py
```

## 4. Register in `_registry.py:_TABLE`

Append a row. Only set fields that are non-default for this benchmark;
`metrics_type` + prompt yaml basename are auto-derived from the upstream
`__init__.py:GENERATION_ARGS`, so do not hardcode them.

Two minimal shapes -- pick the one matching step 2:

**Bundled** (vendored `test.txt`):

```python
{
    "name": "<name>",
    "loader": "bundled",
    "thinking": True,                # True for reasoning, False for knowledge
    "default_n_repeats": 16,         # 1 single-shot, 8/16 stochastic
    "description": "<one-liner>",
},
```

**Prepare** (vendored `prepare.py`):

```python
{
    "name": "<name>",
    "loader": "prepare",
    "save_args": ("test",),          # see invariant below
    "save_kwargs": {"random_seed": 42},  # only if upstream save_data takes non-default kwargs
    "thinking": False,
    "default_n_repeats": 1,
    "description": "<one-liner>",
},
```

> **`save_args[0]` invariant.** `_loader.py` uses
> `output_basename = f"{save_args[0]}.jsonl"` to find the file
> `save_data` wrote. So `save_args[0]` must equal the basename (sans
> `.jsonl`) of upstream's output. e.g. `gpqa.save_data("diamond")`
> writes `diamond.jsonl` -> `save_args=("diamond",)`. If upstream's
> signature differs, the loader can't be reused as-is.

## 5. Verify

```bash
pytest                                    # vendor audit + NS tests still pass
sgl-eval list -v                          # new benchmark appears with correct defaults
```

For a smoke test against a real server (only if user has one running):

```bash
sgl-eval run <name> --base-url http://localhost:30000/v1 --num-examples 3
```

## 6. Commit

One commit per benchmark. Title: `add <name> benchmark`.

The commit should contain:
- `SOURCES.yaml` change (manifest entries)
- new files under `sgl_eval/_vendored/nemo_skills/dataset/<name>/`
- the `_TABLE` row in `_registry.py`

Nothing else. If the sync also produced unrelated changes (e.g., the
upstream commit has been bumped meanwhile), separate that into its own
`vendor-update` commit first.
