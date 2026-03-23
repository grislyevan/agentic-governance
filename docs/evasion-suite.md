# Evasion Suite (INIT-31)

The evasion suite checks that detection and governance hold up under deliberate bypass conditions. It has two parts: **schema/regression** tests and a **runtime** suite that runs the evasion scanner with deterministic fixtures and asserts detector outputs.

## Running the evasion suite locally

From the repo root, with collector deps installed:

```bash
pip install -e ".[dev]"
```

### Schema and regression only

Validates scenario structure and R0–R3 degradation profiles. Excludes slow/benchmark by default in main collector run; run explicitly:

```bash
python -m pytest collector/tests/test_evasion_suite.py -v
```

Or by marker (if configured):

```bash
python -m pytest collector/tests/ -m evasion -v
```

### Full runtime suite (scenario fixtures + detector assertions)

Runs each scenario with deterministic mocks, runs the evasion scanner, and asserts expected vectors and boost bounds:

```bash
python -m pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -v
```

### Writing a metrics artifact

The runtime suite writes a JSON metrics file. By default it goes to `evasion_metrics.json` in the current directory. Override with:

```bash
EVASION_METRICS_OUTPUT=/tmp/evasion_metrics.json python -m pytest collector/tests/test_evasion_suite_runtime.py -v
```

The artifact includes `scenario_pass_count`, `scenario_total`, `detected_vectors`, `missed_vectors`, and per-scenario results. CI uploads it as the `evasion-metrics-initial-31` artifact (see [.github/workflows/ci.yml](../.github/workflows/ci.yml)).

## Weekly regression cadence

Run the full evasion suite (schema + runtime) at least weekly, or on every change that touches `collector/scanner/evasion.py`, policy tamper floor, or enforcement. CI runs it on every push/PR; for local or scheduled runs:

```bash
python -m pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -q
```

When you discover a new evasion vector (e.g. a bypass not covered by E1–E8), open an issue using the [New evasion report](../.github/ISSUE_TEMPLATE/new-evasion.md) template so we can add a scenario and detector.

## Adding or changing scenarios

1. **Edit the scenario list** in [collector/tests/evasion_suite_scenarios.py](../collector/tests/evasion_suite_scenarios.py).

2. **Schema fields (required):**
   - `evasion_scenario_id`, `matrix_cell_id`, `tool_id`, `tool_class`
   - `evasion_category`: one of E1–E5 (E6–E8 when added in Sprint E2)
   - `attack_technique_description`, `preconditions`, `action_sequence`
   - `expected_degradation_profile`: R0, R1, R2, or R3
   - `expected_policy_behavior`, `required_evidence_outputs`, `pass_fail_criteria`

3. **Optional runtime assertion fields:**
   - `expected_vectors`: list of scanner vector IDs (e.g. `["E1-global-hook"]`) that must appear when this scenario is simulated.
   - `expected_min_boost` / `expected_max_boost`: inclusive bounds on `evasion_boost` for the run.

4. **Add a runtime fixture** if the scenario needs custom setup. In [collector/tests/test_evasion_suite_runtime.py](../collector/tests/test_evasion_suite_runtime.py), extend `_run_scenario()` to handle your `evasion_scenario_id` (e.g. new mocks or temp dirs), then return the `ScanResult` from `EvasionScanner.scan()`. The parametrized test will assert `expected_vectors` and boost bounds for you.

5. **Keep the suite green.** After adding a scenario, run:

   ```bash
   python -m pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -v
   ```

   If the new scenario has `expected_vectors` or boost bounds, ensure the fixture you added produces those outputs.

## CI

The **Evasion Regression (INIT-31)** job runs on every push/PR to `main`. It runs both the schema suite and the runtime suite and uploads the metrics artifact. You can require this job in branch protection so scenario regressions block merge.

## Scanner vectors (reference)

The evasion scanner in [collector/scanner/evasion.py](../collector/scanner/evasion.py) emits vector IDs such as:

- E1: `E1-global-hook`, `E1-repo-hook`
- E2: `E2-template-hook`
- E3: `E3-force-push`
- E4: `E4-renamed-binary`
- E5: `E5-cursor-git-disabled`, `E5-cursor-telemetry-off`

Use these in `expected_vectors` when defining scenarios. E6–E8 will be added in Sprint E2.
