# THA Inventory Adjustment AVCO Fix

Physical inventory differences for company AVCO products use the average cost
immediately before each completed adjustment's effective datetime, in base units.
The same chronological replay supplies product valuation and stock closing.
Both `_run_avco` and the newer Odoo 19 `_run_average_batch` entry points use
that service. The latter is called directly by the running Odoo build's
`total_value` computation and bypasses the older custom `_run_avco` override.

The prior AVCO override retained zero-valued incoming counts at zero and could
reprice other incoming counts using a later cost. This addon replaces that replay
for non-lot AVCO products, preserving explicit move valuations (including zero).
Completed move dates and IDs determine ordering; explicit cost resets precede
moves at the same datetime. Costs and resets are isolated by company.

A positive count without earlier cost evidence raises an actionable error.
An explicit zero cost is valid. Negative-stock recovery follows native Odoo's
proportional recovery rule. Internal transfers do not change company value.
Standard cost, FIFO, lot valuation and non-realtime replay use the parent methods.

New physical moves receive corrected stored values. Historical valuation is
replayed without rewriting old moves, manual cost history or posted journals.
Backdating therefore changes computed downstream valuation without a migration.

Closing remains inventory value minus posted stock-account balance, less other
closing adjustments. A reduction debits the configured variation/expense account
and credits Stock; an increase does the reverse. No accounting entries are posted
by installation. Date-only stock closing cutoffs include the whole company-local
day (company partner timezone, UTC if unset); GL dates remain accounting dates.
Location reclassification also uses replayed physical-count values and that
cutoff, including historical counts whose stored move value was zero. Archived
products remain eligible for stock-account closing. Inventory-location crossings
are recognized for imported counts even without `is_inventory`; scrap is excluded.

Depends on `tha_purchase_bill_uom_valuation_fix` so purchase bill unit conversion
remains active. Install/upgrade locally with Odoo's normal module workflow.
