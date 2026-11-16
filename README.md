# Stock Valuation Date Cutoff Fix

![Odoo 19](https://img.shields.io/badge/Odoo-19.0-875A7B?style=flat-square)
![License](https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square)
![Category](https://img.shields.io/badge/Category-Inventory-4ECDC4?style=flat-square)

Corrects date-only cutoffs in Odoo 19 Stock Valuation closing calculations.

## Highlights

- Convert a date-only closing input to the final microsecond of that day in the company's timezone.
- Use UTC when the company contact has no timezone configured.
- Apply the same cutoff to stock value and location valuation calculations.

## Workflow

For example, a closing date of September 30 is evaluated through 23:59:59.999999 in the company's timezone, so completed moves later on September 30 are included.

## Technical Notes

- `models/res_company.py` normalizes date-only inputs before delegating to Odoo's stock value and location valuation methods.
- Datetime inputs pass through unchanged.
- The addon does not change stock moves, AVCO calculations, product costs, or accounting entries.
- Focused tests cover timezone conversion and inclusion of moves through the local closing day.

## Module Layout

```text
tha_inventory_adjustment_avco_fix/
|-- models/
|-- tests/
|-- .gitignore
|-- README.md
|-- __init__.py
`-- __manifest__.py
```

## Dependencies

- `stock_account` — provides Odoo's Stock Valuation closing methods.

## Installation

1. Place the module in your custom addons path alongside its dependency.
2. Restart Odoo and update the Apps list.
3. Install **THA Stock Valuation Date Cutoff Fix**.

## License

LGPL-3

## Author

Thein Htoo Aung
