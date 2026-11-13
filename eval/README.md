# TempeSense evaluation harness

Runs the same question set through three systems and scores them against ground truth pulled
live from the ArcGIS layers.

| System | What it is |
|---|---|
| `b0` | Zero-shot LLM: no schema, no validation, no retry (lower bound) |
| `b1` | The stakeholder's original code (commit `baddb80` on `main`), unmodified |
| `ours` | Current branch (MunicipalAgent with guardrails, date resolution, repair loop) |

## Run it (PowerShell, from the repo root)

```powershell
# 1. One-time: check out the stakeholder's original code next to the repo
git worktree add ../baseline-b1 baddb80

# 2. Build gold answers (needs internet, no LLM key)
python -m eval.gold

# 3. Run the systems (needs the LLM key in .env)
python -m eval.run --systems ours,b1,b0 --datasets A,B --repeats 1 --b1-path ../baseline-b1

# 4. Score and write the report
python -m eval.report eval\results\<timestamp>
```

Outputs land in `eval/results/<timestamp>/`: `records.jsonl` (raw), `report.md` (tables),
`scored.csv` (one row per run), `logs/` (agent output per run).
Use `--ids O01,C03` for a quick smoke test and `--repeats 3` for a stable latency/consistency read.

## Datasets
- **A**: data questions with a hand-written gold `where` (offenses and street closures).
- **B**: regression questions for known stakeholder-reported bugs (masked-address handling,
  out-of-scope questions, two-domain questions). Current code is expected to fail several of
  these. That is the "before" measurement.

`questions.json` is a DRAFT. Replace or extend dataset A with the stakeholder's curated list.
The street-closures layer is a stale snapshot (permits from June 8 to July 11, 2026), so questions
C01-C10 set a per-question `"now"` (Wed 2026-06-17) and the agent and B0 are given that clock; B1 has no
clock hook and uses the real date. C02 and C09 are intentional true negatives (nothing should be returned).
Relative dates ("yesterday", "this weekend") otherwise resolve against a fixed clock
(`FIXED_NOW` in `config.py`) so gold and agent agree. Update it to the day you run, and
re-run `eval.gold`, because the gold `where` strings contain explicit UTC dates.

## Contract for new features
A system signals a refusal with `status: "refused"`, an out-of-scope decline with
`status: "out_of_scope"`, and a multi-domain plan with a `tools` list in its result dict.

## Tests
`python -m pytest test_eval_harness.py` (offline, no key needed).
