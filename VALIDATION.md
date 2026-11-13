# Local validation — 2026-11-13

## Demonstrated defects

The previous custom replay preserves zero-recorded incoming physical counts at
zero. The regression seeds cost 10, adds 10 units, removes 3, then simulates a
zero-recorded imported opening count. Previous replay returns zero ending value;
the new replay returns 7 units, cost 10, value 70. Reading historical product
total_value and calling the batch valuation API also return 70.

The runtime Odoo build (19.0-20260630) computes product total_value through
_run_average_batch, bypassing the existing custom _run_avco override. The new
addon handles both entry points. The checked-out core source differs from that
runtime build; no core files were changed.

## Checks

Odoo transaction tests in THA cover positive/negative counts, missing and explicit
zero costs, intervening receipts, future cost exclusion, backdating, simultaneous
events, negative-stock recovery, completed packaging units, company isolation,
internal transfers, native delegation for other cost methods, timezone cutoffs,
location reclassification, and preview/draft closing parity. Test records and
test journal entries are rolled back by Odoo's test runner.

The closing integration fixture has stock GL 100 and inventory value 70. Preview
reports ending value 70; generated balanced draft debits COGS 30 and credits
Stock 30. No posted journal is changed by addon installation.

Final version 19.0.1.0.10: 12 tests passed, 0 failures and 0 errors in THA.
Python syntax and manifest references checked; no XML data files are needed.

## BC sample and limits

The preliminary audit of local company 135, `ID Company Ltd LOCAL BC0001 20261103`,
product 6215 (`LOCAL-BC0001-20261103`), returned quantity 1,673, AVCO 276 and value
461,748 MMK before imported inventory crossings were included as physical counts.
That preliminary result is superseded. The final read-only audit stops at opening
adjustment move 727, effective 2026-08-31 07:09:52, because there is no preceding
AVCO or explicit cost history. It correctly refuses to borrow a later cost.
No opening-cost history was added or modified to force this sample to pass.

THA contains one product in this local company, not the full live BC movement
history. Therefore no corrected full-category September adjustment or live
Stock Variation amount is claimed. The XLS alone cannot establish AVCO before
each adjustment. No production deployment or historical-record migration was
performed. Remaining accounting reconciliation is outside this change.
