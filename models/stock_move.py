from odoo import _, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    def _tha_is_physical_adjustment(self):
        self.ensure_one()
        # Imported count moves can lack is_inventory. Scrap is a separate flow.
        return not self.scrap_id and (
            (self.location_id.usage == "inventory" and self.location_dest_id.usage == "internal")
            or (self.location_dest_id.usage == "inventory" and self.location_id.usage == "internal")
        )

    def _set_value(self):
        physical = self.filtered(lambda move: move._tha_is_physical_adjustment()
                                 and move.product_id.cost_method == "average"
                                 and not move.product_id.lot_valuated)
        expected = {}
        for move in physical:
            incoming = move._is_in()
            lines = move._get_in_move_lines() if incoming else move._get_out_move_lines()
            qty = sum(lines.mapped("quantity_product_uom"))
            if not qty:
                continue
            product = move.product_id.with_company(move.company_id)
            replay = product._tha_replay_adjustment_avco(at_date=move.date, before_move=move)
            manual = move._get_manual_value(qty, at_date=move.date)
            if not replay["known_cost"] and not manual["quantity"]:
                raise UserError(_("No historical AVCO exists for physical adjustment of %(product)s "
                                  "at %(date)s. Set an opening cost or explicit adjustment valuation.",
                                  product=product.display_name, date=move.date))
            expected[move.id] = manual["value"] if manual["quantity"] else qty * replay["cost"]
        result = super()._set_value()
        for move in physical:
            if move.id in expected:
                move.value = expected[move.id]
        return result
