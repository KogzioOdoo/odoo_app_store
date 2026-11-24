from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from ..models.common import internal, is_internal


class ActivityMassWizard(models.TransientModel):
    _name = 'activity.mass.wizard'
    _description = 'Schedule Mass Activity Wizard'

    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type', required=True)
    summary = fields.Char()
    note = fields.Html()
    date_deadline = fields.Date(string='Due Date', required=True, default=fields.Date.context_today)
    priority = fields.Selection(selection='_selection_priority', default='0')
    user_ids = fields.Many2many('res.users', string='Assign To', required=True, default=lambda self: self.env.user)
    scheduled_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal(self) and any(v.get('scheduled_at') for v in vals_list):
            raise AccessError(self.env._('Scheduling status is maintained automatically.'))
        return super().create(vals_list)

    @api.model
    def _selection_priority(self):
        return self.env['mail.activity']._fields['priority']._description_selection(self.env)

    def write(self, values):
        if 'scheduled_at' in values and not is_internal(self):
            raise AccessError(self.env._('Scheduling status is maintained automatically.'))
        return super().write(values)

    def action_schedule(self):
        self.ensure_one()
        self.env['mail.activity']._require_management_user()
        self.check_access('write')
        self.flush_recordset()
        self.env.cr.execute(SQL('SELECT id FROM activity_mass_wizard WHERE id = %s FOR UPDATE', self.id))
        self.invalidate_recordset()
        if self.scheduled_at:
            return {'type': 'ir.actions.act_window_close'}
        model = self.env.context.get('active_model')
        ids = self.env.context.get('active_ids', [])
        if not model or model not in self.env or not isinstance(ids, (list, tuple)) or not ids:
            raise UserError(self.env._('Select at least one valid source record first.'))
        if not self.user_ids:
            raise UserError(self.env._('Select at least one person.'))
        records = self.env[model].browse(ids).exists()
        if len(records) != len(set(ids)):
            raise UserError(self.env._('Some selected records no longer exist. Refresh the list and try again.'))
        if not hasattr(records, 'activity_schedule'):
            raise UserError(self.env._('This document type does not support activities.'))
        records.check_access('read')
        for user in self.user_ids:
            records.activity_schedule(activity_type_id=self.activity_type_id.id,
                                      summary=self.summary or '', note=self.note or '',
                                      date_deadline=self.date_deadline, user_id=user.id,
                                      priority=self.priority or '0')
        internal(self).write({'scheduled_at': fields.Datetime.now()})
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': self.env._('Activities Scheduled'),
            'message': self.env._('%(count)s activities created for %(people)s people.',
                                   count=len(records) * len(self.user_ids), people=len(self.user_ids)),
            'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}
