from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _run_average_batch(self, at_date=None, lot=None, force_recompute=False):
        # Recent Odoo 19 builds call this directly from total_value, bypassing
        # _run_avco. Both entry points must use the same adjustment replay.
        if lot:
            return super()._run_average_batch(at_date=at_date, lot=lot, force_recompute=force_recompute)
        eligible = self.filtered(lambda p: p.cost_method == "average" and not p.lot_valuated)
        others = self - eligible
        prices, values = ({}, {})
        if others:
            prices, values = super(ProductProduct, others)._run_average_batch(
                at_date=at_date, lot=lot, force_recompute=force_recompute)
        for product in eligible:
            result = product._tha_replay_adjustment_avco(at_date=at_date)
            prices[product.id] = result["cost"]
            values[product.id] = result["value"]
        return prices, values

    def _run_avco(self, at_date=None, lot=None, method="realtime"):
        self.ensure_one()
        if self.cost_method != "average" or self.lot_valuated or lot or method != "realtime":
            return super()._run_avco(at_date=at_date, lot=lot, method=method)
        result = self._tha_replay_adjustment_avco(at_date=at_date)
        return result["cost"], result["value"]

    def _tha_replay_adjustment_avco(self, at_date=None, before_move=None):
        """Read-only company replay; never substitute today's cost for a count."""
        self.ensure_one()
        cutoff = fields.Datetime.to_datetime(at_date) if at_date else fields.Datetime.now()
        company = self.env.company
        domain = [
            ("product_id", "=", self.id), ("company_id", "=", company.id),
            ("state", "=", "done"), ("date", "<=", cutoff),
            "|", "|", ("is_in", "=", True), ("is_out", "=", True),
            ("is_dropship", "=", True),
        ]
        if before_move:
            domain += ["|", ("date", "<", before_move.date),
                       "&", ("date", "=", before_move.date), ("id", "<", before_move.id)]
        moves = self.env["stock.move"].search(domain, order="date, id")
        resets = self.env["product.value"].search([
            ("product_id", "=", self.id), ("company_id", "=", company.id),
            ("move_id", "=", False), ("lot_id", "=", False),
            ("date", "<=", cutoff),
        ], order="date, id")
        quantity = total = cost = 0.0
        known_cost = False
        reset_index = 0
        adjustments = []
        for move in moves:
            # A cost reset at the same time precedes stock moves at that time.
            while reset_index < len(resets) and resets[reset_index].date <= move.date:
                cost = resets[reset_index].value
                total = quantity * cost
                known_cost = True
                reset_index += 1
            incoming = move.is_in or move.is_dropship
            lines = move._get_in_move_lines() if incoming else move._get_out_move_lines()
            qty = sum((move.move_line_ids if move.is_dropship else lines).mapped("quantity_product_uom"))
            if not qty:
                continue
            physical = move._tha_is_physical_adjustment()
            manual = move._get_manual_value(qty, at_date=cutoff)
            has_manual = bool(manual["quantity"])
            before_cost = cost
            if physical:
                if not known_cost and not has_manual:
                    raise UserError(_(
                        "Cannot value physical adjustment %(move)s for %(product)s at %(date)s: "
                        "no earlier AVCO or explicit cost history exists. Review the opening "
                        "stock cost or provide an explicit adjustment valuation.",
                        move=move.reference or move.id, product=self.display_name, date=move.date,
                    ))
                amount = manual["value"] if has_manual else qty * cost
                adjustments.append({
                    "move_id": move.id, "date": move.date, "quantity": qty if incoming else -qty,
                    "cost_before": before_cost, "value": amount if incoming else -amount,
                    "recorded_value": move.value, "manual": has_manual,
                })
            elif incoming:
                amount = move._get_value(at_date=cutoff) if at_date or move.is_dropship else move.value
            else:
                amount = manual["value"] if has_manual else qty * cost
            if incoming:
                if quantity < 0 and quantity + qty >= 0:
                    total = (quantity + qty) / qty * amount
                else:
                    total += amount
                quantity += qty
                cost = total / quantity if quantity else cost
                known_cost = True
                if move.is_dropship:
                    total -= qty * cost
                    quantity -= qty
            else:
                total -= amount
                quantity -= qty
                # Explicit outgoing corrections affect remaining inventory AVCO.
                if has_manual and quantity > 0:
                    cost = total / quantity
        while reset_index < len(resets):
            cost = resets[reset_index].value
            total = quantity * cost
            known_cost = True
            reset_index += 1
        return {"cost": cost, "quantity": quantity, "value": total,
                "known_cost": known_cost, "adjustments": adjustments}
