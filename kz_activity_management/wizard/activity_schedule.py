from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import SQL

from ..models.common import SchedulingValues, internal, is_internal


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    scheduled_activity_ids = fields.Json(default=list, readonly=True)
    scheduled_at = fields.Datetime(readonly=True)
    management_can_complete = fields.Boolean(compute='_compute_management_can_complete')

    priority = fields.Selection(
        [
            ('0', 'Normal'),
            ('1', 'Low'),
            ('2', 'Medium'),
            ('3', 'High'),
        ],
        string='Priority',
        default='0',
    )

    tag_ids = fields.Many2many(
        'activity.tag',
        'mail_activity_schedule_tag_rel',
        'schedule_id',
        'tag_id',
        string='Tags',
    )

    estimated_hours = fields.Float(string='Estimated Hours')

    assignment_type = fields.Selection(
        [
            ('individual', 'A separate task for each person'),
            ('shared', 'One shared task'),
        ],
        string='Assignment Type',
        default='individual',
        required=True,
    )

    assigned_user_ids = fields.Many2many(
        'res.users',
        'mail_activity_schedule_user_rel',
        'schedule_id',
        'user_id',
        string='Additional People',
        help='Independent tasks in Individual mode; participants in one task in Shared mode.',
    )

    supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor',
    )

    alarm_datetime = fields.Datetime(string='Reminder', help='A popup and pending work-bell reminder at this time.')

    is_recurring = fields.Boolean(string='Recurring Activity')
    recurrence_interval = fields.Integer(
        string='Repeat Every',
        default=1,
    )
    recurrence_unit = fields.Selection(
        [
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
            ('years', 'Years'),
        ],
        string='Repeat Unit',
        default='weeks',
    )
    recurrence_end_date = fields.Date(string='Repeat Until')

    @api.depends('activity_user_id', 'supervisor_id', 'assigned_user_ids', 'assignment_type')
    @api.depends_context('uid')
    def _compute_management_can_complete(self):
        Activity = self.env['mail.activity']
        for wizard in self:
            wizard.management_can_complete = (
                not Activity._is_management_user()
                or self.env.user.has_group('kz_activity_management.group_activity_manager')
                or wizard.activity_user_id == self.env.user
                or (wizard.assignment_type == 'shared' and self.env.user in wizard.assigned_user_ids)
                or (self.env.user.has_group('kz_activity_management.group_activity_supervisor')
                    and (wizard.supervisor_id or wizard.activity_user_id.sudo().supervisor_id) == self.env.user))

    @api.model_create_multi
    def create(self, vals_list):
        if not is_internal(self) and any(v.get('scheduled_at') or v.get('scheduled_activity_ids') for v in vals_list):
            raise AccessError(self.env._('Scheduling results are maintained by the system.'))
        return super().create(vals_list)

    def write(self, vals):
        if not is_internal(self) and {'scheduled_at', 'scheduled_activity_ids'} & vals.keys():
            raise AccessError(self.env._('Scheduling results are maintained by the system.'))
        return super().write(vals)

    @api.constrains('is_recurring', 'recurrence_interval', 'recurrence_unit', 'recurrence_end_date', 'date_deadline', 'estimated_hours', 'assignment_type', 'assigned_user_ids')
    def _check_management_values(self):
        for wizard in self:
            if wizard.estimated_hours < 0:
                raise ValidationError(self.env._('Estimated hours cannot be negative.'))
            if wizard.assignment_type == 'shared' and not (wizard.assigned_user_ids - wizard.activity_user_id):
                raise ValidationError(self.env._('Select at least one additional person for a shared task.'))
            if wizard.is_recurring:
                if wizard.recurrence_interval < 1 or not wizard.recurrence_unit:
                    raise ValidationError(self.env._('Select a repeat unit and an interval of at least 1.'))
                if wizard.recurrence_end_date and wizard.recurrence_end_date < wizard.date_deadline:
                    raise ValidationError(self.env._('Repeat Until cannot be before the current deadline.'))

    def _management_values(self):
        self.ensure_one()
        values = {
            'priority': self.priority, 'tag_ids': [fields.Command.set(self.tag_ids.ids)],
            'estimated_hours': self.estimated_hours, 'assignment_type': self.assignment_type,
            'assigned_user_ids': [fields.Command.set(self.assigned_user_ids.ids)],
            'alarm_datetime': self.alarm_datetime, 'is_recurring': self.is_recurring,
            'recurrence_interval': self.recurrence_interval, 'recurrence_unit': self.recurrence_unit,
            'recurrence_end_date': self.recurrence_end_date,
        }
        if self.supervisor_id:
            values['supervisor_id'] = self.supervisor_id.id
        return values

    def _action_schedule_activities(self):
        self.ensure_one()
        if not self.env['mail.activity']._is_management_user():
            return super()._action_schedule_activities()
        self.check_access('write')
        self.flush_recordset()
        self.env.cr.execute(SQL('SELECT id FROM mail_activity_schedule WHERE id = %s FOR UPDATE', self.id))
        self.invalidate_recordset()
        if self.scheduled_at:
            return self.env['mail.activity'].with_context(active_test=False).browse(self.scheduled_activity_ids or []).exists()
        # Populate at creation, not by a later write to a task the creator may no
        # longer own. The payload cannot be forged by a JSON/RPC context.
        scheduler = self.with_context(_activity_schedule_values=SchedulingValues(self._management_values()))
        activities = super(MailActivitySchedule, scheduler)._action_schedule_activities()
        internal(self).write({'scheduled_at': fields.Datetime.now(),
                              'scheduled_activity_ids': activities.ids})
        return activities

    def _action_schedule_activity(self):
        """Compatibility alias for integrations using the previous method name."""
        return self._action_schedule_activities()
