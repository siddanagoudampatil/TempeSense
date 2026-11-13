# TempeSense evaluation report

- Run started: 2026-11-13T15:09:58  |  commit: `d2fb77e`  |  model: `llama4-scout-17b`
- Reference date for relative questions: 2026-11-13T12:00:00-07:00  |  repeats: 3

## Results (system / dataset)

| Metric | B0 zero-shot / A | B0 zero-shot / B | B1 baseline / A | B1 baseline / B | Ours / A | Ours / B |
|---|---|---|---|---|---|---|
| Runs | 66 | 36 | 66 | 36 | 66 | 36 |
| Tool-call success rate | 0% | 0% | 0% | 0% | 100% | 100% |
| Crash-free runs | 100% | 100% | 0% | 17% | 100% | 100% |
| Hallucinated-field rate | 100% | 100% | n/a | n/a | 0% | 0% |
| Correct tool chosen | 100% | 100% | 0% | 0% | 100% | 100% |
| Record-set F1 vs gold | 0.00 | 0.00 | 0.00 | 0.00 | 0.87 | 0.33 |
| False-negative zero rate | 0% | 0% | 0% | 0% | 5% | 33% |
| Records without id field | n/a | n/a | n/a | n/a | 35% | 0% |
| Refuse / decline / multi-tool correct | n/a | 0% | n/a | 0% | n/a | 0% |
| Median latency (s) | 2.15 | 2.09 | 4.14 | 4.18 | 8.33 | 10.08 |
| LLM calls per question | 1.00 | 1.00 | 2.00 | 2.00 | 4.00 | 4.33 |

Metric definitions:

- **Tool-call success rate**: answer questions: valid query executed, no crash or stop
- **Crash-free runs**: all questions: no uncaught exception
- **Hallucinated-field rate**: executed where clauses using a field not in the schema (lower is better)
- **Correct tool chosen**: answer questions
- **Record-set F1 vs gold**: answer questions with a gold set
- **False-negative zero rate**: returned nothing although gold is non-empty (lower is better)
- **Records without id field**: successful runs whose records carry no citable id (lower is better)
- **Refuse / decline / multi-tool correct**: refusal, out-of-scope and two-domain questions

## By category

| Category | System | Runs | Success | F1 | Behavior |
|---|---|---|---|---|---|
| closures-date | B0 zero-shot | 18 | 0% | 0.00 | n/a |
| closures-date | B1 baseline | 18 | 0% | 0.00 | n/a |
| closures-date | Ours | 18 | 100% | 1.00 | n/a |
| closures-empty | B0 zero-shot | 9 | 0% | 0.00 | n/a |
| closures-empty | B1 baseline | 9 | 0% | 0.00 | n/a |
| closures-empty | Ours | 9 | 100% | 1.00 | n/a |
| closures-street | B0 zero-shot | 3 | 0% | 0.00 | n/a |
| closures-street | B1 baseline | 3 | 0% | 0.00 | n/a |
| closures-street | Ours | 3 | 100% | 0.00 | n/a |
| closures-type | B0 zero-shot | 6 | 0% | 0.00 | n/a |
| closures-type | B1 baseline | 6 | 0% | 0.00 | n/a |
| closures-type | Ours | 6 | 100% | 1.00 | n/a |
| offenses-category-date | B0 zero-shot | 9 | 0% | 0.00 | n/a |
| offenses-category-date | B1 baseline | 9 | 0% | 0.00 | n/a |
| offenses-category-date | Ours | 9 | 100% | 0.73 | n/a |
| offenses-date | B0 zero-shot | 9 | 0% | 0.00 | n/a |
| offenses-date | B1 baseline | 9 | 0% | 0.00 | n/a |
| offenses-date | Ours | 9 | 100% | 1.00 | n/a |
| offenses-location | B0 zero-shot | 9 | 0% | 0.00 | n/a |
| offenses-location | B1 baseline | 9 | 0% | 0.00 | n/a |
| offenses-location | Ours | 9 | 100% | 0.67 | n/a |
| offenses-place-name | B0 zero-shot | 3 | 0% | 0.00 | n/a |
| offenses-place-name | B1 baseline | 3 | 0% | 0.00 | n/a |
| offenses-place-name | Ours | 3 | 100% | 1.00 | n/a |
| reg-masked-block | B0 zero-shot | 3 | 0% | 0.00 | n/a |
| reg-masked-block | B1 baseline | 3 | 0% | 0.00 | n/a |
| reg-masked-block | Ours | 3 | 100% | 0.00 | n/a |
| reg-offense-date | B0 zero-shot | 3 | 0% | 0.00 | n/a |
| reg-offense-date | B1 baseline | 3 | 0% | 0.00 | n/a |
| reg-offense-date | Ours | 3 | 100% | 1.00 | n/a |
| reg-out-of-scope | B0 zero-shot | 12 | n/a | n/a | 0% |
| reg-out-of-scope | B1 baseline | 12 | n/a | n/a | 0% |
| reg-out-of-scope | Ours | 12 | n/a | n/a | 0% |
| reg-refusal | B0 zero-shot | 9 | n/a | n/a | 0% |
| reg-refusal | B1 baseline | 9 | n/a | n/a | 0% |
| reg-refusal | Ours | 9 | n/a | n/a | 0% |
| reg-specific-category | B0 zero-shot | 3 | 0% | 0.00 | n/a |
| reg-specific-category | B1 baseline | 3 | 0% | 0.00 | n/a |
| reg-specific-category | Ours | 3 | 100% | 0.00 | n/a |
| reg-two-domain | B0 zero-shot | 6 | n/a | n/a | 0% |
| reg-two-domain | B1 baseline | 6 | n/a | n/a | 0% |
| reg-two-domain | Ours | 6 | n/a | n/a | 0% |

## Failures

### B0 zero-shot (102 of 102 runs)

- `O01` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `O02` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: offense_type' paramet  (x3)
- `O03` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i  (x3)
- `O04` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `O05` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `O06` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `O07` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `O08` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: offense_type' paramet  (x3)
- `O09` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: offense_date' paramet  (x3)
- `O10` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `C01` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i  (x3)
- `C02` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD_NAME' parameter   (x3)
- `C03` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: status' parameter is   (x3)
- `C04` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD_NAME' parameter 
- `C05` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i  (x3)
- `C06` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: TYPE' parameter is in  (x3)
- `C07` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: STREET' parameter is   (x3)
- `C08` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}  (x3)
- `C09` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD_NAME' parameter   (x3)
- `C10` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: start_date' parameter  (x2)
- `C11` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD_NAME' parameter   (x3)
- `C12` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD_NAME' parameter   (x3)
- `R01` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: OC_DESC' parameter is  (x3)
- `R02` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: INT_DATE' parameter i  (x2)
- `R03` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: offense_type' paramet  (x2)
- `R04` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: FULL_STREET_NAME' par  (x3)
- `R05` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: address' parameter is
- `R06` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i  (x3)
- `R07` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: BLOCK_START_DATE' par  (x3)
- `R08` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: TYPE' parameter is in  (x2)
- `R09` [ok] wrong behavior  (x3)
- `R10` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: COMPLAINANT_CATEGORY'  (x3)
- `R11` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: STREET' parameter is   (x3)
- `R12` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: STREET' parameter is   (x3)
- `C04` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: ROAD' parameter is in  (x2)
- `C10` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i
- `R03` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'where' parameter is invalid"]}
- `R05` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: LOCATION' parameter i  (x2)
- `R08` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ['Unable to perform query. Please check
- `R02` [stopped] ArcGIS error: {'code': 400, 'message': 'Cannot perform query. Invalid query parameters.', 'details': ["'Invalid field: DATE_OCCURRED' parame

### B1 baseline (102 of 102 runs)

- `O01` [crashed] ValidationError: 1 validation error for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `O02` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O03` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O04` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O05` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O06` [crashed] ValidationError: 1 validation error for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `O07` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O08` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O09` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `O10` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `C01` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C02` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C03` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C04` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[  (x3)
- `C05` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C06` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C07` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[  (x2)
- `C08` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x2)
- `C09` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[  (x3)
- `C10` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C11` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C12` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `R01` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R02` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R03` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R04` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[  (x2)
- `R05` [ok] wrong behavior  (x3)
- `R06` [ok] wrong behavior  (x3)
- `R07` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R08` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R09` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R10` [crashed] ValidationError: 2 validation errors for GeneralOffensesQueryArgs out_fields   Input should be a valid string [type=string_type, input_value  (x3)
- `R11` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[  (x3)
- `R12` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=  (x3)
- `C07` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=
- `C08` [crashed] ValidationError: 1 validation error for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=[
- `R04` [crashed] ValidationError: 2 validation errors for StreetClosuresQueryArgs out_fields   Input should be a valid string [type=string_type, input_value=

### Ours (42 of 102 runs)

- `O02` [ok] F1 0.18  (x3)
- `O06` [ok] F1 0.00  (x3)
- `C04` [ok] F1 0.00  (x3)
- `R02` [ok] F1 0.00  (x3)
- `R03` [ok] F1 0.00  (x3)
- `R04` [ok] wrong behavior  (x3)
- `R05` [ok] wrong behavior  (x3)
- `R06` [ok] wrong behavior  (x3)
- `R07` [ok] wrong behavior  (x3)
- `R08` [ok] wrong behavior  (x3)
- `R09` [ok] wrong behavior  (x3)
- `R10` [ok] wrong behavior  (x3)
- `R11` [ok] wrong behavior  (x3)
- `R12` [ok] wrong behavior  (x3)
