from datetime import date, datetime, time, timedelta
from collections import defaultdict

import pytz

from odoo import _, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_accounts_by_product(self, products=None):
        if products is None:
            products = self.env["product.product"].with_company(self).with_context(active_test=False).search([
                ("is_storable", "=", True), ("company_id", "in", [False, self.id]),
            ])
        return super()._get_accounts_by_product(products)

    def _tha_stock_closing_cutoff(self, at_date):
        self.ensure_one()
        if isinstance(at_date, str) and len(at_date) == 10:
            at_date = date.fromisoformat(at_date)
        if isinstance(at_date, date) and not isinstance(at_date, datetime):
            zone = pytz.timezone(self.partner_id.tz or "UTC")
            next_midnight = zone.localize(datetime.combine(at_date + timedelta(days=1), time.min))
            return next_midnight.astimezone(pytz.UTC).replace(tzinfo=None) - timedelta(microseconds=1)
        return at_date

    def stock_value(self, accounts_by_product=None, at_date=None):
        self.ensure_one()
        company = self.with_company(self).with_context(allowed_company_ids=self.ids)
        accounts_by_product = accounts_by_product or company._get_accounts_by_product()
        cutoff = self._tha_stock_closing_cutoff(at_date)
        result = defaultdict(float)
        for product, accounts in accounts_by_product.items():
            scoped = product.with_company(self).with_context(
                allowed_company_ids=self.ids, to_date=cutoff, warehouse_id=False,
                warehouse=False, location=False, lot_id=False, owner_id=False, package_id=False,
            )
            result[accounts["valuation"]] += scoped.total_value
        return result

    def _get_location_valuation_vals(self, at_date=None, location_domain=False):
        """Keep native reclassification, using the same count values/cutoff."""
        self.ensure_one()
        locations = self.env["stock.location"].search(list(location_domain or []) + [
            ("valuation_account_id", "!=", False), ("company_id", "in", [False, self.id]),
        ])
        if not locations:
            return []
        cutoff = self._tha_stock_closing_cutoff(at_date)
        domain = [("company_id", "=", self.id), ("state", "=", "done"),
                  ("product_id.is_storable", "=", True),
                  "|", ("location_id", "in", locations.ids),
                  ("location_dest_id", "in", locations.ids)]
        if cutoff:
            domain.append(("date", "<=", cutoff))
        balances = defaultdict(float)
        corrected = {}
        for move in self.env["stock.move"].search(domain):
            amount = move.value
            product = move.product_id.with_company(self).with_context(allowed_company_ids=self.ids)
            if move._tha_is_physical_adjustment() and product.cost_method == "average" and not product.lot_valuated:
                if product.id not in corrected:
                    replay = product._tha_replay_adjustment_avco(at_date=cutoff)
                    corrected[product.id] = {line["move_id"]: line["value"] * (1 if line["quantity"] > 0 else -1)
                                             for line in replay["adjustments"]}
                amount = corrected[product.id].get(move.id, amount)
            if move.is_out and move.location_dest_id in locations:
                balances[move.location_dest_id.valuation_account_id] += amount
            if move.is_in and move.location_id in locations:
                balances[move.location_id.valuation_account_id] -= amount
        aml_domain = [("company_id", "=", self.id), ("parent_state", "=", "posted"),
                      ("account_id", "in", locations.valuation_account_id.ids)]
        if at_date:
            aml_domain.append(("date", "<=", fields.Date.to_date(at_date)))
        for account, balance in self.env["account.move.line"]._read_group(
                aml_domain, ["account_id"], ["balance:sum"]):
            balances[account] -= balance
        result = []
        for account, balance in balances.items():
            if not self.currency_id.is_zero(balance):
                result += self._prepare_inventory_aml_vals(
                    account, self.account_stock_valuation_id, balance,
                    _("Closing: Location Reclassification - [%(account)s]", account=account.display_name))
        return result
