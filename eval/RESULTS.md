# TempeSense evaluation report

- Run started: 2026-11-13T17:25:42  |  commit: `68030b6`  |  model: `llama4-scout-17b`
- Reference date for relative questions: 2026-11-13T12:00:00-07:00  |  repeats: 3

## Results (system / dataset)

| Metric | Ours / A | Ours / B |
|---|---|---|
| Runs | 66 | 36 |
| Tool-call success rate | 100% | 100% |
| Crash-free runs | 100% | 100% |
| Hallucinated-field rate | 0% | 0% |
| Correct tool chosen | 100% | 100% |
| Record-set F1 vs gold | 0.91 | 1.00 |
| False-negative zero rate | 0% | 0% |
| Records without id field | 35% | 0% |
| Relaxed-query rate | 14% | 0% |
| Refuse / decline / multi-tool correct | n/a | 78% |
| Median latency (s) | 10.03 | 0.00 |
| LLM calls per question | 3.86 | 2.08 |

Metric definitions:

- **Tool-call success rate**: answer questions: valid query executed, no crash or stop
- **Crash-free runs**: all questions: no uncaught exception
- **Hallucinated-field rate**: executed where clauses using a field not in the schema (lower is better)
- **Correct tool chosen**: answer questions
- **Record-set F1 vs gold**: answer questions with a gold set
- **False-negative zero rate**: returned nothing although gold is non-empty (lower is better)
- **Records without id field**: successful runs whose records carry no citable id (lower is better)
- **Relaxed-query rate**: successful runs where the agent broadened its own query after finding nothing (flagged to the user)
- **Refuse / decline / multi-tool correct**: refusal, out-of-scope and two-domain questions

## By category

| Category | System | Runs | Success | F1 | Behavior |
|---|---|---|---|---|---|
| closures-date | Ours | 18 | 100% | 1.00 | n/a |
| closures-empty | Ours | 9 | 100% | 0.67 | n/a |
| closures-street | Ours | 3 | 100% | 1.00 | n/a |
| closures-type | Ours | 6 | 100% | 1.00 | n/a |
| offenses-category-date | Ours | 9 | 100% | 1.00 | n/a |
| offenses-date | Ours | 9 | 100% | 1.00 | n/a |
| offenses-location | Ours | 9 | 100% | 0.67 | n/a |
| offenses-place-name | Ours | 3 | 100% | 1.00 | n/a |
| reg-masked-block | Ours | 3 | 100% | 1.00 | n/a |
| reg-offense-date | Ours | 3 | 100% | 1.00 | n/a |
| reg-out-of-scope | Ours | 12 | n/a | n/a | 100% |
| reg-refusal | Ours | 9 | n/a | n/a | 100% |
| reg-specific-category | Ours | 3 | 100% | 1.00 | n/a |
| reg-two-domain | Ours | 6 | n/a | n/a | 0% |

## Failures

### Ours (12 of 102 runs)

- `O06` [ok] F1 0.00  (x3)
- `C12` [ok] F1 0.00  (x3)
- `R11` [ok] wrong behavior  (x3)
- `R12` [ok] wrong behavior  (x3)
