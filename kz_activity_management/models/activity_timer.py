from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL
from psycopg2.errors import UniqueViolation

from .common import internal, is_internal

class ActivityTimer(models.Model):
    _name = 'activity.timer'
    _description = 'Activity Time Tracking'
    _order = 'start_time desc, id desc'

    activity_id = fields.Many2one(
        'mail.activity', required=True, ondelete='cascade', index=True,
        help="The activity associated with this time tracking session.")
    user_id = fields.Many2one(
        'res.users', required=True, default=lambda self: self.env.user, index=True,
        help="The user whose working time is recorded in this session.")
    start_time = fields.Datetime(
        required=True, default=fields.Datetime.now,
        help="The date and time when this timer session started.")
    stop_time = fields.Datetime(
        readonly=True,
        help="The date and time when this timer session stopped.")
    duration = fields.Float(
        string='Duration (Hours)', compute='_compute_duration', store=True,
        help="The total time recorded for this session, expressed in hours.")
    is_running = fields.Boolean(
        string='Running', default=True, index=True,
        help="Indicates whether this timer session is currently running.")
    description = fields.Text(readonly=True, help='Session notes, including any legacy migration recovery.')

    _one_running_session = models.UniqueIndex(
        '(activity_id, user_id) WHERE is_running IS TRUE',
        'A timer is already running for this person and activity.')

    @api.depends('start_time', 'stop_time')
    def _compute_duration(self):
        for timer in self:
            end = timer.stop_time or timer.start_time
            timer.duration = max((end - timer.start_time).total_seconds(), 0) / 3600 if end and timer.start_time else 0.0

    @api.constrains('start_time', 'stop_time', 'is_running')
    def _check_dates(self):
        for timer in self:
            if timer.stop_time and timer.stop_time < timer.start_time:
                raise ValidationError(self.env._('A session cannot stop before it starts.'))
            if timer.is_running and timer.stop_time:
                raise ValidationError(self.env._('A running session cannot already have a stop time.'))

    @api.model_create_multi
    def create(self, vals_list):
        values = [dict(vals) for vals in vals_list]
        for vals in values:
            activity = self.env['mail.activity'].browse(vals.get('activity_id')).exists()
            if not activity:
                raise UserError(self.env._('Select an existing activity.'))
            if not self.env.su:
                activity._require_management_user()
                activity._lock_transition()
                if vals.get('user_id', self.env.uid) != self.env.uid:
                    raise AccessError(self.env._('You can only start your own timer.'))
                if not activity.active:
                    raise UserError(self.env._('Reopen the activity before starting a timer.'))
                if vals.get('stop_time') or vals.get('is_running') is False or vals.get('start_time'):
                    raise AccessError(self.env._('Session dates are recorded automatically.'))
                vals.update(user_id=self.env.uid, is_running=True, start_time=fields.Datetime.now())
            if self.search_count([('activity_id', '=', activity.id), ('user_id', '=', vals.get('user_id', self.env.uid)), ('is_running', '=', True)]):
                raise UserError(self.env._('A timer is already running for this activity.'))
        try:
            with self.env.cr.savepoint():
                return super().create(values)
        except UniqueViolation as error:
            if error.diag.constraint_name != 'activity_timer_one_running_session':
                raise
            raise UserError(self.env._('Your timer is already running for this activity. Refresh to see it.')) from None

    def write(self, vals):
        if not is_internal(self):
            raise AccessError(self.env._('Timer history is maintained automatically. Use Start and Stop.'))
        return super().write(vals)

    def action_stop_timer(self):
        self.check_access('write')
        if not self.env.su and any(timer.user_id.id != self.env.uid for timer in self):
            raise AccessError(self.env._('You can only stop your own sessions. Closing an activity resolves all its sessions.'))
        self.activity_id._lock_transition()
        return internal(self)._stop_sessions()

    def _stop_sessions(self):
        if not is_internal(self):
            raise AccessError(self.env._('Use Stop Timer.'))
        if not self:
            return True
        self.flush_recordset()
        self.env.cr.execute(SQL('SELECT id FROM activity_timer WHERE id IN %s ORDER BY id FOR UPDATE', tuple(self.ids)))
        self.invalidate_recordset()
        running = self.filtered('is_running')
        if running:
            running.write({'stop_time': fields.Datetime.now(), 'is_running': False})
        return True
