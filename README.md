# Inventory Adjustment AVCO Fix

![Odoo 19](https://img.shields.io/badge/Odoo-19.0-875A7B?style=flat-square)
![License](https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square)
![Category](https://img.shields.io/badge/Category-Inventory-4ECDC4?style=flat-square)

Historical AVCO valuation for Odoo 19: physical inventory adjustments, stock valuation and Stock-to-COGS closing entries.

## Highlights

- Value physical inventory differences using AVCO immediately before each adjustment's effective datetime.
- Use the same historical calculation for product valuation and stock closing.
- Support backdated counts, completed quantities in base units and company-specific cost history.
- Preserve explicit manual valuations, including an explicit zero value.
- Include archived products when calculating stock-account closing balances.
- Report missing historical cost instead of substituting a later cost.

## Workflow

1. Establish the product's opening cost or earlier receipt valuation.
2. Apply the physical inventory count; Odoo creates a stock move for the quantity difference.
3. The addon values that difference at the preceding AVCO and records the value on new adjustment moves.
4. Open Stock Valuation for the required closing date to calculate historical inventory value.
5. Review the proposed variation and generate the closing entry through the existing Odoo workflow.

A stock reduction debits the configured variation/expense account and credits Stock. An increase debits Stock and credits the configured variation/expense account.

## Technical Notes

- Key models:
  - `models/product.py` — shared chronological replay and integration with `_run_avco` and `_run_average_batch`.
  - `models/stock_move.py` — physical adjustment detection and valuation when stock moves are valued.
  - `models/res_company.py` — closing cutoffs, company stock values, archived products and location reclassification.
- Valuation rules:
  - Completed moves are ordered by effective datetime and move ID; explicit cost resets precede moves at the same datetime.
  - Inventory-location crossings identify imported counts even without `is_inventory`; scrap is excluded.
  - Internal transfers do not change company stock value. Negative-stock recovery follows Odoo's proportional recovery rule.
  - Standard cost, FIFO, lot valuation and non-realtime replay retain their parent behavior.
- Closing:
  - Variation remains inventory value minus the posted Stock GL balance, less other closing adjustments.
  - Date-only cutoffs include the whole day in the company partner's timezone, with UTC as the fallback.
  - Historical valuation is replayed without an installation migration that rewrites old moves, cost history or posted journals.
- Validation:
  - `tests/test_adjustment_avco.py` covers adjustment valuation and closing integration.
  - See [Validation results](VALIDATION.md) for local checks and the BC sample's missing opening-cost limitation.

## Module Layout

```text
tha_inventory_adjustment_avco_fix/
|-- models/
|-- tests/
|-- .gitignore
|-- README.md
|-- VALIDATION.md
|-- __init__.py
`-- __manifest__.py
```

## Dependencies

- `tha_purchase_bill_uom_valuation_fix` — retains purchase bill quantity conversion and establishes the valuation override dependency.

## Installation

1. Place the module in your custom addons path alongside its dependency.
2. Restart Odoo and update the Apps list.
3. Install **THA Inventory Adjustment AVCO Fix**.
4. Review any missing historical cost errors before generating closing entries.

## License

LGPL-3

## Author

Thein Htoo Aung
