from odoo import api, fields, models
from odoo.exceptions import UserError


class ActivityBulkCloseWizard(models.TransientModel):
    _name = 'activity.bulk.close.wizard'
    _description = 'Bulk Activity Completion and Cancellation'

    activity_ids = fields.Many2many('mail.activity', string='Selected Activities', readonly=True)
    operation = fields.Selection([('done', 'Mark as Done'), ('cancel', 'Cancel')], required=True, readonly=True)
    feedback = fields.Text(string='Feedback')
    reason = fields.Text(string='Cancellation Reason')

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        context = self.env.context
        if context.get('active_model') != 'mail.activity':
            raise UserError(self.env._('Select activities from the Activities list.'))
        ids = context.get('active_ids') or []
        if not ids:
            raise UserError(self.env._('Select at least one activity.'))
        activities = self.env['mail.activity'].browse(ids).exists()
        if len(activities) != len(set(ids)):
            raise UserError(self.env._('One or more selected activities no longer exist.'))
        activities.check_access('write')
        if any(not activity.active for activity in activities):
            raise UserError(self.env._('Select only open activities. Closed activities cannot be processed again.'))
        if 'activity_ids' in field_names:
            values['activity_ids'] = [fields.Command.set(activities.ids)]
        if 'operation' in field_names:
            values['operation'] = context.get('default_operation')
        return values

    def action_confirm(self):
        self.ensure_one()
        activities = self.activity_ids.exists()
        if not activities or len(activities) != len(self.activity_ids):
            raise UserError(self.env._('The selected activities are no longer available.'))
        activities.check_access('write')
        if any(not activity.active for activity in activities):
            raise UserError(self.env._('Some activities are already closed. Refresh the list and try again.'))
        if self.operation == 'done':
            for activity in activities.sorted('id'):
                activity.action_feedback(feedback=self.feedback or '')
        elif self.operation == 'cancel':
            reason = (self.reason or '').strip()
            if not reason:
                raise UserError(self.env._('Enter a cancellation reason.'))
            activities.sorted('id')._action_cancel(reason)
        else:
            raise UserError(self.env._('Invalid bulk operation.'))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': self.env._('Activities Updated'),
                           'message': self.env._('%(count)s activities processed.', count=len(activities)),
                           'type': 'success',
                           'next': {'type': 'ir.actions.act_window_close'}}}
