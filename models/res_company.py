from datetime import date, datetime, time, timedelta

import pytz

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

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
        cutoff = self._tha_stock_closing_cutoff(at_date)
        return super().stock_value(accounts_by_product=accounts_by_product, at_date=cutoff)

    def _get_location_valuation_vals(self, at_date=None, location_domain=False):
        cutoff = self._tha_stock_closing_cutoff(at_date)
        return super()._get_location_valuation_vals(at_date=cutoff, location_domain=location_domain)
