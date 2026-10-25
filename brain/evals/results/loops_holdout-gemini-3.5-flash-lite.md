# Loop eval (loops_holdout): 2026-10-25 · `gemini-3.5-flash-lite`

16 labelled screens (10 expected new loops, 1 expected closes, 7 negatives). 1 new API call(s) this run; the rest came from the cache.

## New loops (confidence ≥ 0.6)
Precision **91%** (10/11) · Recall **100%** (10/10) · F1 **0.95** · due date right 8/8
Negatives left clean (no false loop or close): 6/7

## Closes (inferred done, confidence ≥ 0.8)
Proposed by the analysis call: correct 1/1, unsafe 0
**After the verifier: correct 1/1 · unsafe closes 0** (closing a loop that isn't done hides it from you)

## Threshold sweep (new loops)
| min confidence | precision | recall | F1 |
|---|---|---|---|
| 0.5 | 91% | 100% | 0.95 |
| 0.6 | 91% | 100% | 0.95 |
| 0.7 | 91% | 100% | 0.95 |
| 0.8 | 91% | 100% | 0.95 |
| 0.9 | 91% | 100% | 0.95 |

## Errors
- h-forwarded-01: false loop 'Confirm talk for invitation' (i_owe, 0.90) (FYI forward: the ask was to someone else; at most a soft loop)
