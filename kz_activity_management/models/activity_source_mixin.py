from odoo import models

class ActivitySourceMixin(models.AbstractModel):
    _inherit = 'mail.activity.mixin'

    def write(self, values):
        result = super().write(values)
        if {'partner_id', 'company_id'} & values.keys():
            activities = self.env['mail.activity'].sudo().with_context(active_test=False).search([
                ('res_model', '=', self._name), ('res_id', 'in', self.ids)])
            activities._compute_source_details()
        if self._name == 'res.partner' and 'email' in values:
            people = self.env['res.users'].sudo().search([('partner_id', 'in', self.ids)])
            if people:
                self.env['mail.activity'].sudo().search([
                    '|', ('user_id', 'in', people.ids), ('assigned_user_ids', 'in', people.ids)
                ]).write({'notification_error': False})
        return result
