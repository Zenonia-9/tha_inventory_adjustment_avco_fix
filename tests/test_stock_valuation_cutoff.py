from datetime import date, datetime

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockValuationCutoff(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.unit = self.env.ref("uom.product_uom_unit")
        self.category = self.env["product.category"].create({
            "name": "Stock valuation cutoff regression", "property_cost_method": "average",
        })
        self.product = self.env["product.product"].create({
            "name": "Stock valuation cutoff regression", "is_storable": True,
            "categ_id": self.category.id, "uom_id": self.unit.id,
        })
        self.inside = self.env["stock.location"].create({
            "name": "Cutoff regression stock", "usage": "internal", "company_id": self.company.id,
        })
        self.inventory = self.env["stock.location"].create({
            "name": "Cutoff regression inventory", "usage": "inventory", "company_id": self.company.id,
        })

    def _move(self, qty, when, source=None, dest=None, physical=True):
        with freeze_time(when):
            move = self.env["stock.move"].create({
                "product_id": self.product.id,
                "product_uom": self.unit.id,
                "product_uom_qty": qty,
                "company_id": self.company.id,
                "location_id": (source or self.inventory).id,
                "location_dest_id": (dest or self.inside).id,
                "is_inventory": physical,
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = qty
            move.picked = True
            move._action_done()
        return move

    def _seed_cost(self):
        self.env["product.value"].create({
            "product_id": self.product.id,
            "company_id": self.company.id,
            "date": "2026-08-01 00:00:00",
            "value": 10,
        })

    def test_date_only_cutoff_uses_company_local_end_of_day(self):
        self.company.partner_id.tz = "Asia/Yangon"
        self.assertEqual(
            self.company._tha_stock_closing_cutoff(date(2026, 9, 30)),
            datetime(2026, 9, 30, 17, 29, 59, 999999),
        )

    def test_stock_value_includes_only_moves_through_local_closing_day(self):
        self.company.partner_id.tz = "Asia/Yangon"
        self._seed_cost()
        self._move(10, "2026-09-30 17:29:00", physical=False)
        self._move(3, "2026-09-30 17:31:00", self.inside, self.inventory)
        mapping = {self.product: {"valuation": self.company.account_stock_valuation_id}}

        values = self.company.stock_value(mapping, at_date=date(2026, 9, 30))

        self.assertAlmostEqual(sum(values.values()), 100)
