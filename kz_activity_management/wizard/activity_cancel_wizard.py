from odoo import fields, models

class ActivityCancelWizard(models.TransientModel):
    _name = 'activity.cancel.wizard'
    _description = 'Cancel Activity Wizard'

    activity_id = fields.Many2one('mail.activity', string='Activity', required=True, ondelete='cascade')
    reason = fields.Text(string='Cancel Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.activity_id._action_cancel(self.reason)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': self.env._('Activity Cancelled'), 'message': self.env._('The reason and activity history have been retained.'), 'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}

