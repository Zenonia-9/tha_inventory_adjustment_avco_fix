from datetime import date, datetime
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.tha_purchase_bill_uom_valuation_fix.models.product import ProductProduct as PreviousReplay


@tagged("post_install", "-at_install")
class TestAdjustmentAvco(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.unit = self.env.ref("uom.product_uom_unit")
        self.category = self.env["product.category"].create({
            "name": "Physical AVCO regression", "property_cost_method": "average",
        })
        self.product = self.env["product.product"].create({
            "name": "Physical AVCO regression", "is_storable": True,
            "categ_id": self.category.id, "uom_id": self.unit.id,
        })
        self.inside = self.env["stock.location"].create({
            "name": "AVCO regression stock", "usage": "internal", "company_id": self.company.id,
        })
        self.inventory = self.env["stock.location"].create({
            "name": "AVCO regression counts", "usage": "inventory", "company_id": self.company.id,
        })

    def _seed(self, value=10):
        self.env["product.value"].create({
            "product_id": self.product.id, "company_id": self.company.id,
            "date": "2026-08-01 00:00:00", "value": value,
        })

    def _move(self, qty, when, source=None, dest=None, physical=True, uom=None):
        with freeze_time(when):
            move = self.env["stock.move"].create({
                "product_id": self.product.id, "product_uom": (uom or self.unit).id,
                "product_uom_qty": qty, "company_id": self.company.id,
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

    def test_positive_negative_and_zero_stored_value(self):
        self._seed()
        first = self._move(10, "2026-09-01 09:00:00")
        second = self._move(3, "2026-09-02 09:00:00", self.inside, self.inventory)
        self.assertAlmostEqual(first.value, 100)
        self.assertAlmostEqual(second.value, 30)
        first.value = 0  # Historical count imported without a recorded value.
        legacy = PreviousReplay._run_avco(self.product, at_date=datetime(2026, 9, 30, 23, 59))
        self.assertAlmostEqual(legacy[1], 0)
        replay = self.product._tha_replay_adjustment_avco("2026-09-30 23:59:59")
        self.assertAlmostEqual(replay["value"], 70)
        self.assertAlmostEqual(replay["cost"], 10)
        self.assertEqual(replay["quantity"], 7)
        self.assertAlmostEqual(self.product.with_context(
            to_date="2026-09-30 23:59:59", allowed_company_ids=self.company.ids).total_value, 70)
        self.assertAlmostEqual(self.product._run_average_batch(
            at_date=datetime(2026, 9, 30, 23, 59))[1][self.product.id], 70)

    def test_intervening_receipt_and_future_cost(self):
        self._seed()
        self._move(10, "2026-09-01 09:00:00")
        receipt = self._move(10, "2026-09-02 09:00:00",
                             self.env.ref("stock.stock_location_suppliers"), physical=False)
        self.env["product.value"].create({
            "move_id": receipt.id, "date": "2026-09-02 09:00:00", "value": 300,
            "company_id": self.company.id,
        })
        self._move(2, "2026-09-03 09:00:00")
        self.env["product.value"].create({
            "product_id": self.product.id, "company_id": self.company.id,
            "date": "2026-10-01 00:00:00", "value": 999,
        })
        result = self.product._tha_replay_adjustment_avco("2026-09-30 23:59:59")
        self.assertAlmostEqual(result["value"], 440)
        self.assertAlmostEqual(result["adjustments"][-1]["value"], 40)

    def test_missing_and_explicit_zero_cost(self):
        self._seed()
        self._move(2, "2026-09-01 09:00:00")
        # Simulate an imported count with no opening-cost history. Native
        # product creation/completion can create an initial zero cost record.
        self.env["product.value"].search([
            ("product_id", "=", self.product.id), ("move_id", "=", False),
        ]).unlink()
        with self.assertRaises(UserError):
            self.product._tha_replay_adjustment_avco("2026-09-30 23:59:59")
        self._seed(0)
        self.assertEqual(self.product._run_avco(at_date=datetime(2026, 9, 30, 23, 59))[1], 0)

    def test_negative_stock_recovery(self):
        self._seed()
        self._move(10, "2026-09-01 09:00:00")
        self._move(15, "2026-09-02 09:00:00", self.inside, self.inventory)
        self._move(10, "2026-09-03 09:00:00")
        result = self.product._tha_replay_adjustment_avco("2026-09-30 23:59:59")
        self.assertEqual(result["quantity"], 5)
        self.assertAlmostEqual(result["value"], 50)

    def test_manual_override_and_internal_transfer(self):
        self._seed()
        move = self._move(10, "2026-09-01 09:00:00")
        self.env["product.value"].create({
            "move_id": move.id, "date": "2026-09-01 09:00:00", "value": 150,
            "company_id": self.company.id,
        })
        other = self.inside.copy({"name": "AVCO second location"})
        self._move(3, "2026-09-02 09:00:00", self.inside, other, physical=False)
        self.assertAlmostEqual(self.product._run_avco(at_date=datetime(2026, 9, 30, 23, 59))[1], 150)

    def test_backdate_and_same_timestamp_order(self):
        self._seed()
        self._move(10, "2026-09-02 09:00:00")
        self._move(2, "2026-09-01 09:00:00")
        self._move(1, "2026-09-02 09:00:00", self.inside, self.inventory)
        result = self.product._tha_replay_adjustment_avco("2026-09-30 23:59:59")
        self.assertAlmostEqual(result["value"], 110)
        self.assertEqual(result["quantity"], 11)

    def test_closing_day_timezone(self):
        self.company.partner_id.tz = "Asia/Yangon"
        self.assertEqual(self.company._tha_stock_closing_cutoff(date(2026, 9, 30)),
                         datetime(2026, 9, 30, 17, 29, 59, 999999))

    def test_closing_cutoff_includes_local_day_only(self):
        self.company.partner_id.tz = "Asia/Yangon"
        self._seed()
        self._move(10, "2026-09-30 17:29:00", physical=False)
        self._move(3, "2026-09-30 17:31:00", self.inside, self.inventory)
        mapping = {self.product: {"valuation": self.company.account_stock_valuation_id}}
        values = self.company.stock_value(mapping, at_date=date(2026, 9, 30))
        self.assertAlmostEqual(sum(values.values()), 100)

    def test_other_cost_methods_delegate(self):
        for method in ("standard", "fifo"):
            self.category.property_cost_method = method
            with patch.object(PreviousReplay, "_run_avco", return_value=(123, 456)) as parent:
                self.assertEqual(self.product._run_avco(), (123, 456))
                parent.assert_called_once()

    def test_packaging_quantities_and_company_isolation(self):
        self._seed()
        box = self.env["uom.uom"].create({
            "name": "AVCO Box 12", "relative_factor": 12, "relative_uom_id": self.unit.id,
        })
        move = self._move(2, "2026-09-01 09:00:00", uom=box)
        self.assertAlmostEqual(move.value, 240)
        self.assertAlmostEqual(self.product._run_avco(at_date=datetime(2026, 9, 30))[1], 240)
        other = self.env["res.company"].create({"name": "AVCO isolation regression"})
        self.env["product.value"].create({
            "product_id": self.product.id, "company_id": other.id,
            "date": "2026-09-02 00:00:00", "value": 999,
        })
        self.assertAlmostEqual(self.product._run_avco(at_date=datetime(2026, 9, 30))[1], 240)

    def test_closing_preview_and_draft_entry(self):
        self._seed()
        self._move(10, "2026-09-01 09:00:00")
        self._move(3, "2026-09-02 09:00:00", self.inside, self.inventory)
        account = self.env["account.account"].create({
            "name": "AVCO regression stock", "code": "TAV001", "account_type": "asset_current",
            "company_ids": [(6, 0, self.company.ids)],
        })
        expense = self.env["account.account"].create({
            "name": "AVCO regression COGS", "code": "TAV002", "account_type": "expense",
            "company_ids": [(6, 0, self.company.ids)],
        })
        account.account_stock_variation_id = expense
        journal = self.env["account.journal"].create({
            "name": "AVCO regression", "code": "TAV", "type": "general", "company_id": self.company.id,
        })
        self.company.account_stock_journal_id = journal
        opening = self.env["account.move"].create({
            "journal_id": journal.id, "date": "2026-08-31", "line_ids": [
                (0, 0, {"account_id": account.id, "debit": 100}),
                (0, 0, {"account_id": expense.id, "credit": 100}),
            ],
        })
        opening.action_post()
        mapping = {self.product: {"valuation": account, "variation": expense, "expense": expense}}
        cls = type(self.company)
        with patch.object(cls, "_get_accounts_by_product", lambda company, products=None: mapping), \
             patch.object(cls, "_get_location_valuation_vals", lambda *args, **kwargs: []):
            preview = self.env["stock_account.stock.valuation.report"]._get_report_data(date=date(2026, 9, 30))
            self.assertAlmostEqual(preview["ending_stock"]["value"], 70)
            action = self.company.action_close_stock_valuation(at_date=date(2026, 9, 30))
            entry = self.env["account.move"].browse(action["res_id"])
            self.assertEqual(entry.state, "draft")
            self.assertAlmostEqual(sum(entry.line_ids.mapped("balance")), 0)
            self.assertAlmostEqual(entry.line_ids.filtered(lambda l: l.account_id == account).credit, 30)
            self.assertAlmostEqual(entry.line_ids.filtered(lambda l: l.account_id == expense).debit, 30)

    def test_location_reclassification_uses_replayed_count_values(self):
        self._seed()
        first = self._move(10, "2026-09-01 09:00:00")
        self._move(3, "2026-09-02 09:00:00", self.inside, self.inventory)
        first.value = 0
        account_model = self.env["account.account"]
        stock = account_model.create({
            "name": "AVCO location stock", "code": "TAL001", "account_type": "asset_current",
            "company_ids": [(6, 0, self.company.ids)],
        })
        count = account_model.create({
            "name": "AVCO location counts", "code": "TAL002", "account_type": "expense",
            "company_ids": [(6, 0, self.company.ids)],
        })
        self.company.account_stock_valuation_id = stock
        self.inventory.valuation_account_id = count
        lines = self.company._get_location_valuation_vals(
            date(2026, 9, 30), location_domain=[("id", "=", self.inventory.id)])
        self.assertAlmostEqual(sum(l["debit"] for l in lines if l["account_id"] == stock.id), 70)
        self.assertAlmostEqual(sum(l["credit"] for l in lines if l["account_id"] == count.id), 70)
