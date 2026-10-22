from odoo import api,fields, models, tools
from odoo.tools import SQL

class NegativeStockReport(models.Model):
    """Read-only report of negative on-hand stock per product & location"""
    _name = 'negative.stock.report'
    _description = 'Negative Stock Report'
    _auto = False
    _order = 'quantity,id'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', readonly=True)
    product_categ_id = fields.Many2one('product.category',string='Product Category',readonly=True)
    location_id = fields.Many2one('stock.location',readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse',readonly=True)
    company_id = fields.Many2one('res.company',readonly=True)
    quantity = fields.Float(string='On Hand Qty', readonly=True)
    last_move_id = fields.Many2one('stock.move',string='Last Stock Move',readonly=True)
    last_move_reference = fields.Char(string='Last Move Reference',readonly=True)
    last_move_date = fields.Datetime( readonly=True)
    last_move_user_id = fields.Many2one('res.users',string='User',readonly=True)

    currency_id = fields.Many2one('res.currency',related='company_id.currency_id')
    value = fields.Monetary(string='Negative Value',compute='_compute_value',search='_search_value',currency_field='currency_id')
    move_line_ids = fields.Many2many('stock.move.line',string='Last Stock Moves',compute='_compute_move_line_ids')

    @api.depends('quantity','product_id','company_id')
    def _compute_value(self):
        for rec in self:
            cost = rec.product_id.with_company(rec.company_id).standard_price
            rec.value =rec.quantity * cost

    def _search_value(self, operator, value):
        records = self.search([]).filtered_domain([('value', operator, value)])
        return [('id', 'in', records.ids)]

    def _compute_move_line_ids(self):
        MoveLine = self.env['stock.move.line']
        for rec in self:
            rec.move_line_ids = MoveLine.search([
                ('product_id', '=', rec.product_id.id),
                ('state', '=', 'done'),
                '|',
                ('location_id', '=', rec.location_id.id),
                ('location_dest_id', '=', rec.location_id.id),
            ], order='date desc, id desc')

    def action_open_physical_inventory(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Physical Inventory',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('location_id', '=', self.location_id.id),
            ],
            'context': {
                'default_product_id': self.product_id.id,
                'default_location_id': self.location_id.id,
                'inventory_mode': True,
            },
        }

    def action_open_purchase_orders(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'New Purchase Order',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_order_line': [(0, 0, {
                    'product_id': self.product_id.id,
                })],
            },
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("CREATE OR REPLACE VIEW %s AS (%s)", SQL.identifier(self._table), self._query()))

    def _query(self):
        return SQL("""
            SELECT q.id AS id,
                   q.product_id,
                   pt.categ_id AS product_categ_id,
                   q.location_id,
                   l.warehouse_id,
                   COALESCE(q.company_id, l.company_id) AS company_id,
                   q.quantity,
                   lm.move_id AS last_move_id,
                   lm.date AS last_move_date,
                   lm.reference AS last_move_reference,
                   lm.create_uid AS last_move_user_id
              FROM stock_quant q
              JOIN stock_location l ON l.id = q.location_id
              JOIN product_product pp ON pp.id = q.product_id
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              LEFT JOIN LATERAL (
                    SELECT sm.id AS move_id,
                           sml.date,
                           sm.reference,
                           sml.create_uid
                      FROM stock_move_line sml
                      LEFT JOIN stock_move sm ON sm.id = sml.move_id
                     WHERE sml.product_id = q.product_id
                       AND sml.state = 'done'
                       AND q.location_id IN (
                           sml.location_id,
                           sml.location_dest_id
                       )
                  ORDER BY sml.date DESC, sml.id DESC
                     LIMIT 1
              ) lm ON TRUE
             WHERE q.quantity < 0
               AND l.usage = 'internal'
        """)