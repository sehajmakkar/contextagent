# Loop eval (loops_holdout): 2026-10-25 · `gemini-3.8-flash`

16 labelled screens (10 expected new loops, 1 expected closes, 7 negatives). 16 new API call(s) this run; the rest came from the cache.

## New loops (confidence ≥ 0.6)
Precision **100%** (10/10) · Recall **100%** (10/10) · F1 **1.00** · due date right 8/8
Negatives left clean (no false loop or close): 7/7

## Closes (inferred done, confidence ≥ 0.8)
Correct 1/1 · **unsafe closes 0** (closing a loop that isn't done hides it from you)

## Threshold sweep (new loops)
| min confidence | precision | recall | F1 |
|---|---|---|---|
| 0.5 | 100% | 100% | 1.00 |
| 0.6 | 100% | 100% | 1.00 |
| 0.7 | 100% | 100% | 1.00 |
| 0.8 | 100% | 100% | 1.00 |
| 0.9 | 100% | 100% | 1.00 |

## Errors
- none
