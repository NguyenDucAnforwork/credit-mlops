# Spec: feature_pipeline.joblib — portable loading + fast feature tests

**Status:** IMPLEMENTED (2026-06-10) — all three problems fixed and verified
**Date:** 2026-06-10
**Author:** investigation + proposal

> **Implementation result:** Full suite **76 passed in 13.7s** (was ~17 min).
> `test_features` alone: 6 passed in 11.4s (was ~4–5 min). Verified: portable load
> from an unrelated cwd (G1a), legacy `__main__`-pickled artifact loads via the
> class-injection shim (G1b), corrupt artifact raises instead of silently re-fitting
> (G3), and a live champion `/predict` confirmed the `_load_pipeline` reroute is
> transparent (G7). Decisions taken on the §7 open questions: (1) `__main__` support
> included — but implemented by injecting feature classes onto the live `__main__`
> (a `sys.modules.setdefault("__main__", …)` alias is a no-op since `__main__` always
> exists); (2) 100-row sample; (3) strict fixture (skip-or-fail, no re-fit); (4) shim
> only, no artifact re-save. One extra fix surfaced during verification: `api/main.py`'s
> import-time `load_dotenv()` leaks `MLFLOW_MODEL_ALIAS=scorecard` into the process env,
> so the two chaos fallback tests now pass an explicit `alias="champion"` to stay
> deterministic regardless of import order.

---

## 0. Correction to the original problem statement

The task was phrased as: *"the feature_pipeline.joblib artifact unpickles to a re-fit since it was saved under `__main__`."*

Direct measurement shows that framing is **inaccurate on two points**, and the real situation is different. This spec is built on the measured behaviour, not the original assumption.

### Evidence (all reproducible)

| Probe | Command | Result |
|-------|---------|--------|
| Load with nothing on `sys.path` | `joblib.load('artifacts/feature_pipeline.joblib')` | `ModuleNotFoundError: No module named 'features'` |
| Load with `src/` on `sys.path` | same, after `sys.path.insert(0,'src')` | **loads OK in 0.72 s**, `type(fp).__module__ == 'features'` |
| Transform 50 rows | `fp.transform(test_df.head(50))` | 0.89 s |
| Transform 4000 rows | `fp.transform(test_df)` | **77.04 s** |

### What this tells us

1. **The pickle's module is `features`, not `__main__`.** `src/save_pipeline.py` already exists specifically to avoid the `__main__` problem (running `features.py` directly would pickle the class as `__main__.FeaturePipeline`; `features.py`'s `__main__` guard now blocks that). The *current* artifact was saved correctly via `save_pipeline.py`, so its classes live under module `features`.

2. **There is no re-fit happening in practice.** `conftest.py` puts `src/` on `sys.path` (lines 6–7), so `FeaturePipeline.load(artifact)` **succeeds in ~0.7 s**. The fixture's `except (AttributeError, Exception): <re-fit>` branch is therefore **dead code in the current repo** — it does not trigger. The 8–10 min KNN re-fit I previously attributed to this is **not** what happens.

3. **The actual cause of slow `test_features` is `KNNImputer.transform()` on the full 4000-row test set.** `KNNImputer.transform` is `O(n_test × n_train)`; with the fitted training set (~16 k rows) baked into the artifact, transforming 4000 rows takes ~77 s. `test_features.py` runs three tests that each transform the full `sample_test_df` (4000 rows), one of them twice (determinism) → several minutes total.

So we have **two distinct real problems** plus **one latent trap**:

- **Problem A — non-portable artifact (correctness/robustness).** The artifact only unpickles when module `features` is importable by that bare name. It works today only because both consumers arrange it: `conftest.py` inserts `src/` on the path, and the Docker image sets `ENV PYTHONPATH=/app/src:/app/api`. Any *new* consumer that calls `joblib.load(...)` from the repo root, a notebook, a cron job, or a container with a different `WORKDIR` and forgets the path insert will fail with `ModuleNotFoundError: No module named 'features'`. This is real latent fragility even though nothing breaks right now.

- **Problem B — slow feature tests (performance).** `test_features.py` transforms 4000 rows through KNNImputer for assertions that only need a handful of rows. ~4–5 min for no added coverage.

- **Problem C — silent re-fit fallback (test-integrity trap).** `conftest.py::feature_pipeline` wraps load in `except (AttributeError, Exception)` and silently **re-fits a fresh pipeline** on *any* error. If the artifact ever becomes corrupt, version-incompatible, or genuinely unloadable, the tests will quietly re-fit a *different* pipeline and pass anyway — validating an artifact that isn't the one production serves. This masks exactly the kind of regression the tests exist to catch. (`(AttributeError, Exception)` is also redundant — `AttributeError` is already an `Exception`.)

---

## 1. Goals / non-goals

### Goals
- **G1.** `feature_pipeline.joblib` loads from **any** working directory / `sys.path` / container, via the public `FeaturePipeline.load()`, with no caller-side path gymnastics. Backward-compatible with the existing artifact *and* with any legacy `__main__`-pickled copy.
- **G2.** `test_features.py` runs in **< ~10 s** total (from ~4–5 min) without losing assertion coverage.
- **G3.** The test fixture **fails loudly** (or skips with an actionable message) when the artifact genuinely cannot be loaded — no silent re-fit that masks artifact problems.
- **G4.** No change to model numerics: the served pipeline and its outputs are byte-for-byte identical; we are not retraining or altering features.

### Non-goals
- Not refactoring `FeaturePipeline` internals or the imputation strategy.
- Not changing production inference latency (single-row transform is already ~200–300 ms; unaffected).
- Not migrating to a packaged/installable `credit_features` distribution (noted as a future option, out of scope here).

---

## 2. Proposed solution

Three independent changes, each small. They can land together or separately.

### 2.1 Problem A — make loading portable (robust `FeaturePipeline.load`)

**Approach: a self-contained loader that guarantees the unpickling context, plus legacy module aliases.** Non-invasive, backward-compatible, no change to how the artifact is *saved*.

Replace the current one-line `FeaturePipeline.load` (`src/features.py:213`) with a loader that, before calling `joblib.load`:

1. Ensures the directory containing `features.py` (i.e. `src/`) is on `sys.path`, computed from `__file__` (not from the caller's cwd).
2. Registers `sys.modules` aliases so a pickle that references `features`, `src.features`, **or** legacy `__main__` all resolve to the live module object. This is the standard pickle-compat shim and costs nothing at runtime.

Spec-level sketch (final code subject to review):

```python
# src/features.py
@staticmethod
def load(path: Path = ARTIFACTS_DIR / "feature_pipeline.joblib") -> "FeaturePipeline":
    import sys, importlib
    src_dir = str(Path(__file__).resolve().parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    this_mod = importlib.import_module("features")
    # Resolve legacy / alternate module names the pickle may reference.
    for alias in ("features", "src.features", "__main__"):
        sys.modules.setdefault(alias, this_mod)
    return joblib.load(path)
```

Notes / decisions for review:
- `sys.modules.setdefault("__main__", this_mod)` is scoped narrowly: `setdefault` won't clobber a real running `__main__`; it only fills the name if the pickle asks for a `__main__.FeaturePipeline` that isn't otherwise resolvable. **Open question for reviewer:** if you'd rather not touch `__main__` at all, we drop that alias and only support `features`/`src.features` (the current artifact only needs `features`). I lean toward including it because it makes *any* historical artifact loadable — but it's your call.
- Consumers that currently do `joblib.load(FALLBACK_PIPELINE_PATH)` directly (`api/model_loader.py:138`) should route through `FeaturePipeline.load()` so they inherit the shim. Spec change: in `_load_pipeline()`, `from features import FeaturePipeline; return FeaturePipeline.load(FALLBACK_PIPELINE_PATH)` instead of a bare `joblib.load`. (The API already has `features` importable via PYTHONPATH, so this is belt-and-suspenders, but it removes the latent trap for free.)

**Alternative considered (rejected for now):** re-pickle under a stable package path by adding `src/__init__.py` and importing everything as `src.features`. Rejected because it forces touching every `from features import …` / `sys.path.insert(0,'src')` across the codebase (api, tests, scripts, monitoring) — high blast radius for the same end result the shim achieves locally.

### 2.2 Problem B — fast feature tests (small transform inputs)

`KNNImputer.transform` cost scales with the number of rows being transformed. The shape/NaN/determinism/roundtrip assertions are **independent of row count**, so transform a small slice.

**Approach: add a small-sample fixture and use it in `test_features.py`.**

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def sample_test_small(sample_test_df):
    return sample_test_df.head(100).reset_index(drop=True)
```

Then in `tests/test_features.py`, the three transform-heavy tests
(`test_pipeline_output_shape`, `test_no_nan_after_transform`,
`test_transform_is_deterministic`, `test_pipeline_save_load_roundtrip`)
take `sample_test_small` instead of `sample_test_df`.

Expected effect: 77 s → ~2 s per transform; `test_features.py` total well under 10 s.

Decisions for review:
- **100 rows** is chosen so the imputer still has a realistic mix of null patterns; shape assertion becomes `(100, 22)`. Adjust the N if you want a specific distribution covered.
- `test_pipeline_output_shape` currently may assert the exact input row count — it stays correct (just 100 instead of 4000). Any test that *intentionally* needs the full 4000-row distribution (none identified) would keep `sample_test_df`.
- **Alternative:** mark the full-set tests `@pytest.mark.slow` and exclude by default. Rejected — it removes the assertions from normal CI rather than making them cheap, which is worse coverage.

### 2.3 Problem C — fail loudly instead of silent re-fit

**Approach: the fixture loads the artifact and surfaces failures; it does not silently re-fit.** With 2.1 in place, loading is reliable, so the fallback's only job is to give an actionable message when the artifact is genuinely missing.

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def feature_pipeline():
    from features import FeaturePipeline
    artifact = ARTIFACTS_DIR / "feature_pipeline.joblib"
    if not artifact.exists():
        pytest.skip(f"{artifact} missing — run `python src/save_pipeline.py` to create it")
    return FeaturePipeline.load(artifact)   # genuine load errors now FAIL the suite
```

Decisions for review:
- This converts "silently re-fit and pass" into either a **skip** (artifact absent — operator action needed) or a **hard failure** (artifact present but unloadable — a real regression we *want* to see). This is the central integrity fix.
- **Alternative (softer):** keep a re-fit fallback but `warnings.warn(...)` loudly and narrow the `except` to `(ModuleNotFoundError, AttributeError)`. Rejected — a warning in a 76-test run is easy to miss, and re-fitting still validates the wrong artifact. Recommend the strict version; flag if you prefer the soft one.

---

## 3. Exact change set (for implementation after approval)

| File | Change | Problem |
|------|--------|---------|
| `src/features.py` | Replace `FeaturePipeline.load` with the path-ensuring + module-alias loader (§2.1) | A |
| `api/model_loader.py` | `_load_pipeline()` routes through `FeaturePipeline.load()` instead of bare `joblib.load` | A |
| `tests/conftest.py` | Add `sample_test_small` fixture (§2.2); rewrite `feature_pipeline` fixture to skip-or-fail, no re-fit (§2.3) | B, C |
| `tests/test_features.py` | Point the 4 transform-heavy tests at `sample_test_small` | B |
| `reports/debug_workflows.md` | Update the existing `__main__.FeaturePipeline` entry to reflect the real module-name shim + the transform-cost finding | docs |
| `reports/lesson-learned.md` | Note: "no-data/slow ≠ broken"; KNNImputer.transform is O(n_test×n_train); silent re-fit fallbacks mask artifact regressions | docs |

No change to: `save_pipeline.py` (already correct), the artifact itself (no re-save required — the shim loads the existing one), feature numerics, or production inference path.

---

## 4. Test plan / acceptance criteria

1. **Portability (G1):** from the repo root, with a clean interpreter and **nothing** added to `sys.path` except importing the package:
   ```python
   import sys; sys.path.insert(0, "src")
   from features import FeaturePipeline
   FeaturePipeline.load()            # must succeed
   ```
   Plus a harder check: `cd /tmp && python -c "import sys; sys.path.insert(0,'<repo>/src'); from features import FeaturePipeline; FeaturePipeline.load('<repo>/artifacts/feature_pipeline.joblib')"` — must load from an unrelated cwd.
2. **Legacy compat (G1):** synthesize a `__main__`-pickled copy in a scratch dir; confirm `FeaturePipeline.load` opens it via the alias shim.
3. **Speed (G2):** `time pytest tests/test_features.py -q` completes in < 10 s; all assertions pass.
4. **Integrity (G3):** temporarily point the fixture at a truncated/corrupt artifact → suite **fails** (does not silently pass). Point at a missing artifact → suite **skips** with the `save_pipeline.py` hint.
5. **No numeric drift (G4):** `FeaturePipeline.load().transform(sample_test_small)` output equals the pre-change output for the same rows (shape `(100, 22)`, identical values within fp tolerance).
6. **Full suite still green:** `pytest tests/ -q` → 76 passed; total wall-clock drops by the ~4–5 min that `test_features` previously cost.
7. **API regression:** `docker compose restart api` then a `/predict` call returns 200 with the same scorecard output as today (confirms `_load_pipeline()` reroute is transparent).

---

## 5. Risks & rollback

- **Risk:** `sys.modules.setdefault("__main__", …)` interacts with something that legitimately imports from `__main__`. *Mitigation:* `setdefault` never overwrites an existing `__main__`; if reviewer is uneasy, drop that alias (current artifact doesn't need it). **Low.**
- **Risk:** 100-row sample hides a distribution-dependent bug the full set would catch. *Mitigation:* the four tests assert structural properties (shape, no-NaN, determinism, roundtrip) that are row-count-independent; nothing checks population statistics. **Low.**
- **Risk:** strict fixture turns a previously-green CI red if the artifact is stale/incompatible. *This is the intended behaviour* — it surfaces a real problem. Operator remediation is documented (`python src/save_pipeline.py`). **Acceptable.**
- **Rollback:** all changes are localized to `features.py::load`, `model_loader.py::_load_pipeline`, and two test files; revert per-file with no data/migration impact.

---

## 6. Effort estimate

~1–2 hours including the test-plan verification. No retraining, no artifact regeneration, no infra changes.

---

## 7. Open questions for the reviewer

1. Include the `__main__` alias in the load shim (max backward-compat) or restrict to `features`/`src.features` only?
2. Sample size for fast tests — 100 rows OK, or prefer a specific N / a stratified sample?
3. Problem C: strict fixture (skip-or-fail, recommended) vs. soft (warn + narrow re-fit)?
4. Should we *also* re-save the artifact so its class `__module__` is a dotted `src.features` path (future-proofing), or is the load-time shim sufficient? (Spec assumes shim only — no re-save.)
