import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import pytz

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL, format_date, format_datetime

from .common import SchedulingValues, internal, is_internal, is_transition

_logger = logging.getLogger(__name__)
STATES = [('planned', 'Planned'), ('today', 'Today'), ('overdue', 'Overdue'),
          ('done', 'Done'), ('cancelled', 'Cancelled')]
RECURRENCE_UNITS = [('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')]

class MailActivity(models.Model):
    _inherit = 'mail.activity'
    _check_company_auto = True

    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Low'), ('2', 'Medium'), ('3', 'High')], default='0', index=True,
        help="Set the importance of this activity to help prioritize work.",)
    tag_ids = fields.Many2many(
        'activity.tag', 'mail_activity_activity_tag_rel', 'activity_id', 'tag_id',
        string='Tags', check_company=True, help="Add tags to organize and easily find activities.",)
    supervisor_id = fields.Many2one(
        'res.users', compute='_compute_supervisor_id', store=True, readonly=False, index=True,
        help="Select the person responsible for supervising this activity and monitoring its progress.",)
    assigned_user_ids = fields.Many2many(
        'res.users', 'mail_activity_assigned_user_rel', 'activity_id', 'user_id',
        string='Additional People', help="Select additional users to include in this activity.",)
    assignment_type = fields.Selection(
        [('individual', 'A separate task for each person'), ('shared', 'One shared task')],
        required=True, default='individual',
        help="Choose whether each person receives a separate activity or multiple people share one activity.",)
    estimated_hours = fields.Float(help="Enter the estimated time required to complete this activity.",)
    legacy_time_spent = fields.Float(
        string='Carried-forward Time Adjustment', readonly=True, copy=False,
        help='Upgrade adjustment preserving the historical total. Completed session hours plus this adjustment equal Time Spent.')
    time_spent = fields.Float(
        string='Time Spent (Hours)', compute='_compute_time_spent', store=True, readonly=True, copy=False,
        help="Total time recorded while working on this activity.",)
    remaining_hours = fields.Float(compute='_compute_remaining_hours', help="Estimated hours remaining after subtracting the recorded time.",)
    timer_ids = fields.One2many(
        'activity.timer', 'activity_id', string='Time Tracking History', copy=False,
        help="View the time tracking sessions recorded for this activity.")
    is_timer_running = fields.Boolean(
        compute='_compute_is_timer_running',
        help="Indicates whether a timer is currently running for this activity.")
    cancel_reason = fields.Text(copy=False, readonly=True, help="Enter the reason for cancelling this activity.",)
    cancelled_date = fields.Datetime(
        string='Cancelled On', readonly=True, copy=False,
        help="Shows the date and time when this activity was cancelled.")
    state = fields.Selection(
        selection_add=[('cancelled', 'Cancelled')], ondelete={'cancelled': 'set null'},
        help="Shows the activity's current state, including cancellation.")
    management_state = fields.Selection(
        STATES, compute='_compute_management_state', search='_search_management_state', string='Status',
        help="Shows whether the activity is planned, due today, overdue, completed, or cancelled.")
    closure_status = fields.Selection(
        [('open', 'Open'), ('done', 'Completed'), ('cancelled', 'Cancelled')],
        compute='_compute_closure_status', store=True, index=True, string='Completion Status',
        help="Shows whether the activity is open, completed, or cancelled.")
    is_recurring = fields.Boolean(
        string='Recurring', help="Enable automatic recurrence for this activity.",)
    recurrence_interval = fields.Integer(string='Repeat Every', default=1, help="Specify how frequently this activity should repeat.",)
    recurrence_unit = fields.Selection(RECURRENCE_UNITS, string='Repeat Unit', default='weeks', help="Choose the recurrence interval, such as days, weeks, or months.",)
    recurrence_end_date = fields.Date(string='Repeat Until', help="Set the last date until which this activity should repeat.",)
    recurrence_created = fields.Boolean(string='Next Occurrence Created', readonly=True, copy=False, help="Indicates whether the next recurring activity has already been created.",)
    recurrence_error = fields.Text(
        string='Recurrence Needs Attention', readonly=True, copy=False,
        help="Shows an issue that prevented the next recurring activity from being created.")
    due_notified = fields.Boolean(string='Due Mail Queued', readonly=True, copy=False, help="Indicates whether the due-date notification email has been added to the outgoing mail queue. This does not confirm delivery.",)
    missed_notified = fields.Boolean(string='Overdue Mail Queued', readonly=True, copy=False, help="Indicates whether the overdue notification email has been added to the outgoing mail queue. This does not confirm delivery.",)
    notification_log = fields.Json(
        default=dict, readonly=True, copy=False, groups='kz_activity_management.group_activity_manager',
        help="Stores internal notification tracking information to prevent duplicate notifications.")
    notification_error = fields.Text(
        string='Notification Needs Attention', readonly=True, copy=False,
        help="Shows an issue encountered while preparing activity notifications.")
    alarm_datetime = fields.Datetime(
        string='Reminder', help='A popup is broadcast at this time. A pending reminder remains in the work bell until acknowledged. Polling may take up to five minutes.')
    alarm_sent = fields.Boolean(
        string='Reminder Broadcast', readonly=True, copy=False,
        help="Indicates whether the reminder notification has been broadcast. This does not mean it has been acknowledged.")
    alarm_acknowledged_user_ids = fields.Many2many(
        'res.users', 'mail_activity_alarm_ack_rel', 'activity_id', 'user_id', readonly=True, copy=False,
        help="Shows the users who have acknowledged this activity reminder.")
    customer_id = fields.Many2one(
        'res.partner', compute='_compute_source_details', store=True, index=True, string='Customer',
        help="Shows the customer associated with the linked business document, when available.")
    company_id = fields.Many2one(
        'res.company', compute='_compute_source_details', store=True, readonly=False,
        index=True, default=lambda self: self.env.company,
        help="Select the company to which this activity belongs.")
    management_details = fields.Json(
        compute='_compute_management_details',
        help="Contains additional information used to display and manage this activity.")
    history_ids = fields.One2many(
        'activity.history', 'activity_id', string='History', readonly=True, copy=False,
        help="View the recorded history of activity actions, including completion, cancellation, and reopening.")

    _LOCKED_FIELDS = {
        'summary', 'activity_type_id', 'priority', 'tag_ids', 'user_id', 'supervisor_id',
        'assignment_type', 'assigned_user_ids', 'date_deadline', 'alarm_datetime', 'estimated_hours',
        'is_recurring', 'recurrence_interval', 'recurrence_unit', 'recurrence_end_date',
        'note', 'res_model_id', 'res_id', 'company_id',
    }
    _AUDIT_FIELDS = {
        'time_spent', 'legacy_time_spent', 'cancel_reason', 'cancelled_date', 'recurrence_created',
        'recurrence_error', 'due_notified', 'missed_notified', 'notification_log', 'notification_error',
        'alarm_sent', 'alarm_acknowledged_user_ids', 'feedback', 'date_done',
        'customer_id', 'closure_status',
        'history_ids',
        'state', 'management_state', 'remaining_hours', 'management_details', 'is_timer_running',
    }

    @api.model
    def _is_management_user(self):
        group = self.env.ref('kz_activity_management.group_activity_employee', raise_if_not_found=False)
        return bool(group) and self.env.user.has_group('kz_activity_management.group_activity_employee')

    @api.model
    def _require_management_user(self):
        if not self.env.su and not self._is_management_user():
            raise AccessError(self.env._('You do not have access to Activity Management.'))

    def _check_access(self, operation):
        # App roles grant activity-only access inside the installed ACL/rule scope.
        # Source access remains separate. Native nonmembers keep native behavior.
        if self.env.su or not self._is_management_user() or operation == 'create':
            return super()._check_access(operation)
        result = models.Model._check_access(self, operation)
        # Group record rules are ORed. Native mail grants creators write access;
        # that grant must not widen this app's explicit own/team management scope.
        permitted = self.sudo().with_context(active_test=False).filtered_domain(self._get_dashboard_role_domain())
        forbidden = self - permitted
        if forbidden:
            if result:
                return result[0] | forbidden, result[1]
            return forbidden, lambda: forbidden._make_access_error(operation)
        return result

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, bypass_access=False, **kwargs):
        if self.env.su or not self._is_management_user():
            return super()._search(domain, offset, limit, order, bypass_access=bypass_access, **kwargs)
        # Generic ORM preserves ALL installed record rules and pagination, unlike
        # the native mail filter whose source exception only covers primary owners.
        domain = Domain.AND([domain, self._get_dashboard_role_domain()])
        return models.Model._search(self, domain, offset, limit, order,
                                    bypass_access=bypass_access, **kwargs)

    @api.depends('res_model_id', 'res_id')
    def _compute_source_details(self):
        sources = defaultdict(list)
        for activity in self:
            model = activity.res_model_id.model
            if model and activity.res_id and model in self.env:
                sources[model].append(activity.res_id)
        records = {model: {r.id: r for r in self.env[model].sudo().browse(ids).exists()}
                   for model, ids in sources.items()}
        for activity in self:
            source = records.get(activity.res_model_id.model, {}).get(activity.res_id)
            partner, company = self.env['res.partner'], self.env['res.company']
            if source:
                if source._name == 'res.partner':
                    partner = source
                elif 'partner_id' in source._fields and source._fields['partner_id'].comodel_name == 'res.partner':
                    partner = source.partner_id
                if 'company_id' in source._fields and source._fields['company_id'].comodel_name == 'res.company':
                    company = source.company_id
            activity.customer_id = partner
            activity.company_id = company or activity.company_id or activity.user_id.sudo().company_id or self.env.company

    def _compute_customer_id(self):
        """Compatibility for existing integrations using the former compute."""
        self._compute_source_details()

    @api.depends('user_id', 'user_id.supervisor_id')
    def _compute_supervisor_id(self):
        for activity in self:
            activity.supervisor_id = activity.user_id.supervisor_id

    @api.depends('active', 'date_deadline', 'user_id.tz', 'cancelled_date')
    def _compute_state(self):
        super()._compute_state()
        for activity in self:
            if not activity.active and activity.cancelled_date:
                activity.state = 'cancelled'

    @api.depends('active', 'cancelled_date')
    def _compute_date_done(self):
        super()._compute_date_done()
        for activity in self:
            if activity.cancelled_date:
                activity.date_done = False

    @api.depends('state')
    def _compute_management_state(self):
        for activity in self:
            activity.management_state = activity.state

    @api.depends('active', 'cancelled_date')
    def _compute_closure_status(self):
        for activity in self:
            activity.closure_status = 'open' if activity.active else ('cancelled' if activity.cancelled_date else 'done')

    @api.model
    def _deadline_domain(self, state):
        # Native deadline state follows the assignee's timezone, including an
        # unassigned/unspecified-timezone UTC fallback.
        rows = self.env['res.users'].sudo().with_context(active_test=False)._read_group([], ['tz'], ['__count'])
        zones = {r[0] or False for r in rows} | {False}
        now = datetime.now(timezone.utc)
        operator = {'today': '=', 'overdue': '<', 'planned': '>'}[state]
        domains = [[('user_tz', '=', zone), ('date_deadline', operator,
                    fields.Date.to_string(now.astimezone(pytz.timezone(zone or 'UTC') if zone in pytz.all_timezones_set else pytz.UTC).date()))] for zone in zones]
        return Domain.AND([[('active', '=', True)], Domain.OR(domains)])

    @api.model
    def _state_domain(self, state):
        if state in ('today', 'overdue', 'planned'):
            return self._deadline_domain(state)
        if state == 'done':
            return Domain([('active', '=', False), ('cancelled_date', '=', False)])
        if state == 'cancelled':
            return Domain([('active', '=', False), ('cancelled_date', '!=', False)])
        return Domain.FALSE

    def _search_management_state(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise ValueError('Unsupported status operator')
        values = value if operator in ('in', 'not in') else [value]
        domain = Domain.OR([self._state_domain(v) for v in values])
        return ~domain if operator in ('!=', 'not in') else domain

    @api.depends('timer_ids.duration', 'timer_ids.is_running', 'legacy_time_spent')
    def _compute_time_spent(self):
        for activity in self:
            sessions = activity.sudo().timer_ids.filtered(lambda t: not t.is_running)
            activity.time_spent = activity.legacy_time_spent + sum(sessions.mapped('duration'))

    @api.depends('estimated_hours', 'time_spent')
    def _compute_remaining_hours(self):
        for activity in self:
            activity.remaining_hours = activity.estimated_hours - activity.time_spent

    @api.depends('timer_ids.is_running', 'timer_ids.user_id')
    @api.depends_context('uid')
    def _compute_is_timer_running(self):
        for activity in self:
            activity.is_timer_running = any(t.user_id.id == self.env.uid and t.is_running for t in activity.timer_ids)

    @api.depends('priority', 'supervisor_id', 'assigned_user_ids', 'tag_ids', 'estimated_hours',
                 'time_spent', 'remaining_hours', 'assignment_type', 'alarm_datetime',
                 'is_recurring', 'recurrence_interval', 'recurrence_unit', 'recurrence_end_date')
    @api.depends_context('uid', 'tz', 'lang')
    def _compute_management_details(self):
        for activity in self:
            if not self.env.su and not self._is_management_user():
                activity.management_details = False
                continue
            def duration(value):
                minutes = round(abs(value) * 60)
                return ('−' if value < 0 else '') + self.env._('%(hours)sh %(minutes)sm', hours=minutes // 60, minutes=minutes % 60)
            priority = dict(activity._fields['priority']._description_selection(self.env))
            assignment = dict(activity._fields['assignment_type']._description_selection(self.env))
            units = dict(activity._fields['recurrence_unit']._description_selection(self.env))
            activity.management_details = {
                'priority': priority.get(activity.priority, ''),
                'supervisor': activity.supervisor_id.sudo().name or '',
                'people': ', '.join(activity.assigned_user_ids.sudo().mapped('name')),
                'tags': ', '.join(activity.tag_ids.sudo().mapped('name')),
                'estimate': duration(activity.estimated_hours), 'spent': duration(activity.time_spent),
                'remaining': duration(activity.remaining_hours), 'assignment': assignment.get(activity.assignment_type, ''),
                'alarm': format_datetime(self.env, activity.alarm_datetime) if activity.alarm_datetime else '',
                'recurrence': self.env._('Every %(interval)s %(unit)s', interval=activity.recurrence_interval,
                                        unit=units.get(activity.recurrence_unit, '')) if activity.is_recurring else '',
                'until': format_date(self.env, activity.recurrence_end_date) if activity.recurrence_end_date else '',
            }

    @api.constrains('estimated_hours')
    def _check_estimated_hours(self):
        if any(a.estimated_hours < 0 for a in self):
            raise ValidationError(self.env._('Estimated hours cannot be negative.'))

    @api.constrains('is_recurring', 'recurrence_interval', 'recurrence_unit', 'recurrence_end_date', 'date_deadline', 'activity_type_id')
    def _check_recurrence_interval(self):
        for activity in self:
            if activity.is_recurring:
                if activity.activity_type_id.chaining_type == 'trigger':
                    raise ValidationError(self.env._('Use either recurring activities or an automatic activity-type chain, not both.'))
                if activity.recurrence_interval < 1 or activity.recurrence_unit not in dict(RECURRENCE_UNITS):
                    raise ValidationError(self.env._('Select a repeat unit and an interval of at least 1.'))
                if activity.recurrence_end_date and activity.recurrence_end_date < activity.date_deadline:
                    raise ValidationError(self.env._('Repeat Until cannot be before the current deadline.'))

    @api.constrains('assignment_type', 'assigned_user_ids')
    def _check_shared_assignment(self):
        for activity in self:
            if activity.assignment_type == 'shared' and not (activity.assigned_user_ids - activity.user_id):
                raise ValidationError(self.env._('Select at least one additional person for a shared task.'))

    def _check_new_participant_assignment(self):
        """Validate deliberate assignments, not recomputation of legacy activities.

        Existing Odoo activities may be assigned to portal users or have a company
        inferred by the new stored computed field during module installation.
        """
        for activity in self:
            people = (activity.user_id | activity.assigned_user_ids).sudo()
            if activity.company_id and any(
                activity.company_id not in user.company_ids for user in people
            ):
                raise ValidationError(self.env._(
                    'Every assigned person must have access to the activity’s company.'
                ))
            if any(user.share and not user.activity_portal_enabled for user in people):
                raise ValidationError(self.env._(
                    'An administrator must enable Portal Activity Access before assigning this portal user.'
                ))

    @api.constrains('company_id', 'res_model_id', 'res_id')
    def _check_source_company(self):
        for activity in self:
            if not is_internal(activity) and activity.company_id and activity.company_id not in self.env.companies:
                raise AccessError(self.env._('Select the activity’s company in the company switcher first.'))
            if activity.res_model_id.model in self.env and activity.res_id:
                source = self.env[activity.res_model_id.model].sudo().browse(activity.res_id).exists()
                if (source and 'company_id' in source._fields
                        and source._fields['company_id'].comodel_name == 'res.company'
                        and source.company_id and activity.company_id != source.company_id):
                    raise ValidationError(self.env._('An activity must use its source document’s company.'))

    @api.model_create_multi
    def create(self, vals_list):
        values = [dict(vals) for vals in vals_list]
        payload = self.env.context.get('_activity_schedule_values')
        if isinstance(payload, SchedulingValues):
            values = [dict(vals, **payload.values) for vals in values]
        if not is_internal(self) and (
            any(any(vals.get(key) for key in self._AUDIT_FIELDS) for vals in values)
            or any(self.env.context.get('default_' + key) for key in self._AUDIT_FIELDS)
        ):
            raise AccessError(self.env._('Time totals and transition history are maintained by the system.'))
        if (not is_internal(self) and self._is_management_user()
                and any(not vals.get('active', self.env.context.get('default_active', True)) for vals in values)):
            raise AccessError(self.env._('Create active work first, then use Done or Cancel to record its outcome.'))
        # Related res_model is precomputed by native Odoo. Resolve the supplied
        # model IDs directly here so source metadata is correct before company
        # validation, even while native precomputation is still in progress.
        model_ids = {vals['res_model_id'] for vals in values if vals.get('res_model_id')}
        model_names = {model.id: model.model for model in self.env['ir.model'].sudo().browse(model_ids).exists()}
        source_ids = defaultdict(set)
        for vals in values:
            model = model_names.get(vals.get('res_model_id'))
            if model and vals.get('res_id') and model in self.env:
                source_ids[model].add(vals['res_id'])
        sources = {model: {r.id: r for r in self.env[model].sudo().browse(ids).exists()}
                   for model, ids in source_ids.items()}
        for vals in values:
            model = model_names.get(vals.get('res_model_id'))
            source = sources.get(model, {}).get(vals.get('res_id'))
            if model and vals.get('res_id') and not source:
                raise UserError(self.env._('The selected source document no longer exists.'))
            partner = self.env['res.partner']
            company = self.env['res.company']
            if source:
                if model == 'res.partner':
                    partner = source
                elif 'partner_id' in source._fields and source._fields['partner_id'].comodel_name == 'res.partner':
                    partner = source.partner_id
                if 'company_id' in source._fields and source._fields['company_id'].comodel_name == 'res.company':
                    company = source.company_id
            vals['customer_id'] = partner.id or False
            vals['company_id'] = company.id or vals.get('company_id') or self.env.company.id
        expanded, originals = [], []
        for vals in values:
            originals.append(len(expanded))
            if vals.get('assignment_type', 'individual') == 'individual' and vals.get('assigned_user_ids'):
                prototype = self.new(vals)
                extra_ids = (prototype.assigned_user_ids - prototype.user_id).ids
                vals = dict(vals, assigned_user_ids=[fields.Command.clear()])
                expanded.append(vals)
                expanded.extend(dict(vals, user_id=user_id) for user_id in extra_ids)
            else:
                expanded.append(vals)
        creator = self.with_context(_activity_schedule_values=None)
        activities = super(MailActivity, creator).create(expanded)
        if not is_internal(self):
            activities._check_new_participant_assignment()
        return activities.browse([activities[index].id for index in originals])

    def _expand_individual_assignments(self):
        for activity in self.filtered(lambda a: a.assignment_type == 'individual' and a.assigned_user_ids):
            people = activity.assigned_user_ids - activity.user_id
            for person in people:
                internal(activity).copy({'user_id': person.id, 'assigned_user_ids': [fields.Command.clear()]})
            internal(activity).write({'assigned_user_ids': [fields.Command.clear()]})

    def _lock_transition(self):
        self.check_access('write')
        if self:
            self.flush_recordset()
            self.env.cr.execute(SQL('SELECT id FROM mail_activity WHERE id IN %s ORDER BY id FOR UPDATE', tuple(self.ids)))
            self.invalidate_recordset()

    def write(self, vals):
        vals = dict(vals)
        trusted = is_internal(self)
        previous_owners = {a.id: a.user_id.id for a in self} if 'user_id' in vals and not is_transition(self) else {}
        if not trusted:
            if {'res_model_id', 'res_model', 'res_id'} & vals.keys():
                raise UserError(self.env._('The source document is fixed when scheduled. Schedule a follow-up to link a different document.'))
            if self._AUDIT_FIELDS.intersection(vals):
                raise AccessError(self.env._('Use the relevant activity action to change time totals or history.'))
            if self._LOCKED_FIELDS.intersection(vals) and self.filtered(lambda a: not a.active):
                raise UserError(self.env._('Reopen the activity before changing it.'))
            if vals.get('active') and self.filtered(lambda a: not a.active):
                raise UserError(self.env._('Use Reopen to reactivate a closed activity.'))
            if 'active' in vals or {'assignment_type', 'assigned_user_ids'} & vals.keys():
                self._lock_transition()
            if vals.get('active') is False:
                self._stop_all_timers()
        if {'date_deadline', 'user_id', 'assigned_user_ids'} & vals.keys():
            vals.update(due_notified=False, missed_notified=False, notification_error=False)
        if {'alarm_datetime', 'user_id', 'assigned_user_ids'} & vals.keys():
            vals.update(alarm_sent=False, alarm_acknowledged_user_ids=[fields.Command.clear()])
        if {'is_recurring', 'recurrence_interval', 'recurrence_unit', 'recurrence_end_date'} & vals.keys():
            vals['recurrence_error'] = False
        result = super().write(vals)
        if not trusted and {'user_id', 'assigned_user_ids'} & vals.keys():
            self._check_new_participant_assignment()
        for activity in self:
            if activity.id in previous_owners and previous_owners[activity.id] != activity.user_id.id:
                previous = self.env['res.users'].sudo().browse(previous_owners[activity.id])
                activity._record_history('reassigned', self.env._('Previously assigned to %(person)s.', person=previous.name))
        if not is_transition(self) and {'assignment_type', 'assigned_user_ids'} & vals.keys():
            self._expand_individual_assignments()
        return result

    def _stop_all_timers(self):
        sessions = self.env['activity.timer'].sudo().search([('activity_id', 'in', self.ids), ('is_running', '=', True)], order='id')
        internal(sessions)._stop_sessions()

    def unlink(self):
        if (not self.env.su and self._is_management_user()
                and not self.env.user.has_group('kz_activity_management.group_activity_manager')
                and self.filtered(lambda activity: not activity.active)):
            raise AccessError(self.env._('Only an Activity Manager can permanently delete closed activity history.'))
        return super().unlink()

    def _action_done(self, feedback=False, attachment_ids=None):
        self._lock_transition()
        active = self.filtered('active')
        if not active:
            return self.env['mail.message'], self.browse()
        for model, activities in active.grouped('res_model').items():
            if not model:
                continue
            source_ids = set(activities.mapped('res_id'))
            existing = set(self.env[model].sudo().browse(source_ids).exists().ids) if model in self.env else set()
            if source_ids - existing:
                raise UserError(self.env._('A source document no longer exists. Cancel the affected activity with a reason to retain its history, or contact an administrator.'))
        active._stop_all_timers()
        result = super(MailActivity, internal(active))._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for activity in active.exists():
            activity._record_history('done', feedback or '')
        return result

    def _record_history(self, event, details=''):
        self.ensure_one()
        self.env['activity.history'].sudo().create({
            'activity_id': self.id, 'actor_id': self.env.uid, 'responsible_id': self.user_id.id,
            'event': event, 'details': details,
        })

    def action_start_timer(self):
        self.ensure_one()
        self._require_management_user()
        self._lock_transition()
        if not self.active:
            raise UserError(self.env._('Reopen the activity before starting a timer.'))
        Timer = self.env['activity.timer']
        if Timer.search_count([('activity_id', '=', self.id), ('user_id', '=', self.env.uid), ('is_running', '=', True)]):
            raise UserError(self.env._('Your timer is already running for this activity.'))
        Timer.create({'activity_id': self.id, 'user_id': self.env.uid})
        return True

    def action_stop_timer(self):
        self.ensure_one()
        self._require_management_user()
        self._lock_transition()
        sessions = self.env['activity.timer'].search([('activity_id', '=', self.id), ('user_id', '=', self.env.uid), ('is_running', '=', True)])
        if sessions:
            sessions.action_stop_timer()
        return True

    @api.model
    def get_running_timers(self):
        self._require_management_user()
        sessions = self.env['activity.timer'].search([('user_id', '=', self.env.uid), ('is_running', '=', True)], limit=50)
        form_view = self.env.ref('kz_activity_management.mail_activity_view_form').id
        return [{'id': s.id, 'activity_id': s.activity_id.id, 'form_view_id': form_view,
                 'name': s.activity_id.summary or s.activity_id.display_name,
                 'start': fields.Datetime.to_string(s.start_time)} for s in sessions]

    def action_feedback_wizard(self):
        self.ensure_one()
        self.check_access('write')
        if not self.active:
            raise UserError(self.env._('This activity is already closed.'))
        return {'type': 'ir.actions.act_window', 'name': self.env._('Complete Activity'),
                'res_model': 'activity.feedback.wizard', 'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_activity_id': self.id}}

    def action_feedback_schedule_next(self, feedback=False, attachment_ids=None):
        action = super().action_feedback_schedule_next(feedback=feedback, attachment_ids=attachment_ids)
        if action and action.get('res_model') == 'mail.activity':
            # Follow-up creation needs the native scheduling footer, not the
            # app's create-disabled detail view selected by a generic form lookup.
            action['views'] = [(self.env.ref('mail.mail_activity_view_form_popup').id, 'form')]
        return action

    def action_cancel_wizard(self):
        self.ensure_one()
        self.check_access('write')
        if not self.active:
            raise UserError(self.env._('This activity is already closed.'))
        return {'type': 'ir.actions.act_window', 'name': self.env._('Cancel Activity'),
                'res_model': 'activity.cancel.wizard', 'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
                'context': {'default_activity_id': self.id}}

    def action_cancel(self):
        if not self._is_management_user():
            # Native Odoo 19 chatter cancellation is unlink; there is no native
            # action_cancel method to delegate to.
            return self.unlink()
        self.ensure_one()
        return self.action_cancel_wizard()

    def _action_cancel(self, reason):
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError(self.env._('Explain why this activity is being cancelled.'))
        self._lock_transition()
        for activity in self.filtered('active'):
            activity._stop_all_timers()
            internal(activity).write({'cancel_reason': reason, 'cancelled_date': fields.Datetime.now(), 'active': False})
            activity._record_history('cancelled', reason)
            activity._post_management_message(Markup('Activity cancelled: <b>%s</b><br/>Reason: %s') % (activity.summary or activity.activity_type_id.name, reason))
        return True

    def _post_management_message(self, body):
        self.ensure_one()
        # Narrow source message only, after activity authorization, as native completion.
        if self.res_model and self.res_id and self.res_model in self.env:
            source = self.env[self.res_model].sudo().browse(self.res_id).exists()
            if source and hasattr(source, 'message_post'):
                source.message_post(body=body, author_id=self.env.user.partner_id.id, subtype_xmlid='mail.mt_note')

    def action_reopen(self):
        self._require_management_user()
        return self._reopen_after_access()

    def _reopen_after_access(self):
        self._lock_transition()
        for activity in self.filtered(lambda a: not a.active):
            activity._record_history('reopened', activity.cancel_reason or activity.feedback or '')
            internal(activity).write({'active': True, 'cancel_reason': False, 'cancelled_date': False,
                                      'feedback': False, 'date_done': False, 'due_notified': False,
                                      'missed_notified': False, 'notification_error': False})
            activity._post_management_message(Markup('%s') % self.env._('Activity reopened. Previous transition messages remain in the source history.'))
        return True

    def action_unarchive(self):
        return self._reopen_after_access()

    def action_acknowledge_alarm(self):
        self.ensure_one()
        self.check_access('read')
        if self.env.uid not in (self.user_id | self.assigned_user_ids).ids:
            raise AccessError(self.env._('Only an assigned participant can acknowledge this reminder.'))
        internal(self).write({'alarm_acknowledged_user_ids': [fields.Command.link(self.env.uid)]})
        return True

    def action_retry_notifications(self):
        self._require_management_user()
        self.check_access('write')
        internal(self).write({'notification_error': False, 'recurrence_error': False})
        return True

    def action_open_document(self):
        self.ensure_one()
        self.check_access('read')
        if not self.res_model or not self.res_id or self.res_model not in self.env:
            raise UserError(self.env._('This is a personal activity, or its source is no longer available.'))
        source = self.env[self.res_model].browse(self.res_id).exists()
        if not source:
            raise UserError(self.env._('The source document was deleted. Activity details remain available here.'))
        source.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current'}

    def action_share_whatsapp(self):
        self.ensure_one()
        self.check_access('read')
        message = self.env._('Activity: %(summary)s\nDocument: %(document)s\nDeadline: %(deadline)s',
                            summary=self.summary or self.activity_type_id.name or '',
                            document=self.res_name or self.env._('Personal activity'),
                            deadline=format_date(self.env, self.date_deadline))
        return {'type': 'ir.actions.act_url', 'url': 'https://wa.me/?text=' + quote(message), 'target': 'new'}

    @api.model
    def _get_dashboard_role_domain(self):
        if self.env.user.has_group('kz_activity_management.group_activity_manager'):
            return []
        own = ['|', ('user_id', '=', self.env.uid), ('assigned_user_ids', 'in', [self.env.uid])]
        if self.env.user.has_group('kz_activity_management.group_activity_supervisor'):
            return ['|'] + own + [('supervisor_id', '=', self.env.uid)]
        return own

    @api.model
    def _get_dashboard_filter_domain(self, filters):
        domain = []
        for name in ('activity_type_id', 'user_id', 'supervisor_id', 'customer_id'):
            if filters.get(name):
                try:
                    value = int(filters[name])
                except (TypeError, ValueError):
                    raise ValidationError(self.env._('Select a valid filter value.')) from None
                if name == 'user_id':
                    domain += ['|', ('user_id', '=', value), ('assigned_user_ids', 'in', [value])]
                else:
                    domain.append((name, '=', value))
        for name in ('priority', 'res_model'):
            if filters.get(name):
                domain.append((name, '=', filters[name]))
        start, end = filters.get('date_from'), filters.get('date_to')
        try:
            start = fields.Date.to_date(start) if start else False
            end = fields.Date.to_date(end) if end else False
        except (TypeError, ValueError):
            raise ValidationError(self.env._('Enter a valid deadline range.')) from None
        if start and end and start > end:
            raise ValidationError(self.env._('Deadline From must be on or before Deadline To.'))
        if start:
            domain.append(('date_deadline', '>=', start))
        if end:
            domain.append(('date_deadline', '<=', end))
        return domain

    @api.model
    def _get_dashboard_domains(self, filters):
        base = Domain.AND([self._get_dashboard_role_domain(), self._get_dashboard_filter_domain(filters)])
        return {key: list(Domain.AND([base, sub])) for key, sub in {
            'all': Domain.TRUE,
            'planned': Domain.OR([self._state_domain('planned'), self._state_domain('today')]),
            'overdue': self._state_domain('overdue'), 'completed': self._state_domain('done'),
            'cancelled': self._state_domain('cancelled'),
        }.items()}

    @api.model
    def get_dashboard_data(self, filters=None):
        self._require_management_user()
        domains = self._get_dashboard_domains(filters or {})
        Activity = self.with_context(active_test=False)
        counts = {key: Activity.search_count(domain) for key, domain in domains.items()}
        rows = Activity._read_group(self._get_dashboard_role_domain(), ['res_model'], ['__count'])
        names = [row[0] for row in rows if row[0]]
        model_options = self.env['ir.model'].sudo().search_read([('model', 'in', names)], ['model', 'name'], order='name')
        scope = self.env._('Your assigned and shared activities')
        if self.env.user.has_group('kz_activity_management.group_activity_manager'):
            scope = self.env._('All activities in your selected companies')
        elif self.env.user.has_group('kz_activity_management.group_activity_supervisor'):
            scope = self.env._('Your assigned, shared and supervised activities')
        return {'counts': counts, 'domains': domains,
                'scope_label': scope,
                'views': {'list': self.env.ref('kz_activity_management.mail_activity_view_list').id,
                          'form': self.env.ref('kz_activity_management.mail_activity_view_form').id},
                'options': {'activity_types': self.env['mail.activity.type'].search_read([], ['name'], limit=200, order='name'),
                            'priorities': self._fields['priority']._description_selection(self.env), 'models': model_options},
                'deadline_policy': self.env._('Deadline status follows each responsible person’s timezone. Planned includes today.')}

    @api.model
    def get_dashboard_snapshot(self, filters=None, card_key='all', page=0):
        self._require_management_user()
        return {'data': self.get_dashboard_data(filters),
                'table': self.get_dashboard_table(card_key, filters, page)}

    @api.model
    def get_dashboard_filter_options(self, kind, query=''):
        self._require_management_user()
        query = str(query or '')[:100]
        if kind in ('user_id', 'supervisor_id'):
            domain = [('name', 'ilike', query), ('company_ids', 'in', self.env.companies.ids)]
            if kind == 'supervisor_id':
                domain.append(('share', '=', False))
            return self.env['res.users'].search_read(domain, ['name'], limit=30, order='name')
        if kind == 'customer_id':
            domain = Domain.AND([self._get_dashboard_role_domain(), [('customer_id', '!=', False)]])
            activity_query = self.with_context(active_test=False)._search(domain)
            partner_query = activity_query.select(self._field_to_sql(self._table, 'customer_id'))
            partners = self.env['res.partner'].search([('id', 'in', partner_query), ('name', 'ilike', query)], limit=30, order='name')
            return [{'id': p.id, 'name': p.display_name} for p in partners]
        return []

    @api.model
    def _get_dashboard_table_limit(self):
        value = self.env['ir.config_parameter'].sudo().get_param('kz_activity_management.table_limit', '10')
        try:
            return min(max(int(value), 1), 100)
        except (ValueError, TypeError):
            return 10

    @api.model
    def get_dashboard_table(self, card_key='all', filters=None, page=0):
        self._require_management_user()
        domains = self._get_dashboard_domains(filters or {})
        domain = domains.get(card_key, domains['all'])
        try:
            page = max(int(page), 0)
        except (ValueError, TypeError):
            page = 0
        limit = self._get_dashboard_table_limit()
        Activity = self.with_context(active_test=False)
        total = Activity.search_count(domain)
        page = min(page, max(0, (total - 1) // limit))
        records = Activity.search(domain, limit=limit, offset=page * limit, order='date_deadline asc, id desc')
        return {'records': [{'id': rec.id, 'document': rec.res_name or self.env._('Personal activity'),
                             'res_model': rec.res_model, 'res_id': rec.res_id,
                             'activity_type': rec.activity_type_id.name or '', 'summary': rec.summary or '',
                             'user': rec.user_id.sudo().name or self.env._('Unassigned'),
                             'deadline': fields.Date.to_string(rec.date_deadline),
                             'deadline_label': format_date(self.env, rec.date_deadline),
                             'priority': rec.priority or '0', 'status': rec.management_state, 'active': rec.active}
                            for rec in records], 'total': total, 'limit': limit, 'page': page}

    @api.model
    def _get_bell_domain(self):
        own = ['|', ('user_id', '=', self.env.uid), ('assigned_user_ids', 'in', [self.env.uid])]
        alarm = [('active', '=', True), ('alarm_datetime', '<=', fields.Datetime.now()),
                 ('alarm_datetime', '!=', False), ('alarm_acknowledged_user_ids', 'not in', [self.env.uid])]
        return list(Domain.AND([own, Domain.OR([self._state_domain('today'), self._state_domain('overdue'), alarm])]))

    @api.model
    def get_bell_count(self):
        self._require_management_user()
        return self.search_count(self._get_bell_domain())

    @api.model
    def action_open_bell_activity(self):
        self._require_management_user()
        return {'type': 'ir.actions.act_window', 'name': self.env._('Due Work & Reminders'),
                'res_model': self._name, 'view_mode': 'list,form', 'domain': self._get_bell_domain(),
                'views': [(self.env.ref('kz_activity_management.mail_activity_view_list').id, 'list'),
                          (self.env.ref('kz_activity_management.mail_activity_view_form').id, 'form')]}

    @api.model
    def _cron_progress(self, processed, remaining):
        if self.env.context.get('cron_id'):
            self.env['ir.cron']._commit_progress(processed, remaining=remaining)

    def _next_alarm_datetime(self, deadline):
        self.ensure_one()
        if not self.alarm_datetime:
            return False
        zone = ZoneInfo(self.user_id.sudo().tz or 'UTC')
        local = fields.Datetime.to_datetime(self.alarm_datetime).replace(tzinfo=timezone.utc).astimezone(zone)
        target = local + timedelta(days=(deadline - self.date_deadline).days)
        return target.astimezone(timezone.utc).replace(tzinfo=None)

    @api.model
    def _cron_create_recurring_activity(self, limit=50):
        Activity = self.with_context(active_test=False)
        domain = [('active', '=', False), ('cancelled_date', '=', False), ('is_recurring', '=', True),
                  ('recurrence_created', '=', False), ('recurrence_error', '=', False)]
        records = Activity.search(domain, order='id', limit=limit)
        for activity in records:
            try:
                with self.env.cr.savepoint():
                    locked = activity.try_lock_for_update()
                    if not locked:
                        continue
                    locked.invalidate_recordset()
                    if locked.recurrence_created:
                        continue
                    if locked.recurrence_interval < 1 or locked.recurrence_unit not in dict(RECURRENCE_UNITS):
                        raise ValidationError(self.env._('Select a repeat unit and an interval of at least 1.'))
                    deadline = locked.date_deadline + relativedelta(**{locked.recurrence_unit: locked.recurrence_interval})
                    if not locked.recurrence_end_date or deadline <= locked.recurrence_end_date:
                        locked.copy({'active': True, 'date_deadline': deadline, 'feedback': False,
                                     'date_done': False, 'cancel_reason': False, 'cancelled_date': False,
                                     'legacy_time_spent': 0.0, 'alarm_datetime': locked._next_alarm_datetime(deadline)})
                    internal(locked).write({'recurrence_created': True})
            except (ValidationError, UserError, AccessError, MissingError, ValueError) as error:
                _logger.warning('Recurring activity %s needs attention: %s', activity.id, error)
                internal(activity).write({'recurrence_error': str(error)})
        self._cron_progress(len(records), Activity.search_count(domain))

    @api.model
    def _cron_send_activity_notifications(self, limit=50):
        if self.env['ir.config_parameter'].sudo().get_param('kz_activity_management.due_emails_enabled', 'True') == 'False':
            return
        cases = [
            ('due', 'due_notified', self._state_domain('today'), 'kz_activity_management.mail_template_activity_due'),
            ('missed', 'missed_notified', self._state_domain('overdue'), 'kz_activity_management.mail_template_activity_missed'),
        ]
        processed, remaining_domains = 0, []
        for kind, flag, state_domain, xmlid in cases:
            domain = list(Domain.AND([state_domain, [(flag, '=', False), ('notification_error', '=', False)]]))
            remaining_domains.append(domain)
            template = self.env.ref(xmlid)
            records = self.search(domain, order='id', limit=limit)
            for activity in records:
                try:
                    with self.env.cr.savepoint():
                        activity._lock_transition()
                        if activity[flag] or not activity.active:
                            continue
                        log = dict(activity.sudo().notification_log or {})
                        people = (activity.user_id | activity.assigned_user_ids).sudo().filtered('active')
                        if not people:
                            raise UserError(self.env._('No active participants can receive this notification. Reassign the task before retrying.'))
                        missing = []
                        for person in people:
                            key = f'{kind}:{activity.date_deadline}:{person.id}'
                            if key in log:
                                continue
                            if not person.partner_id.email:
                                missing.append(person.name)
                                continue
                            mail_id = template.send_mail(activity.id, email_values={
                                'email_to': person.partner_id.email_formatted, 'recipient_ids': [fields.Command.clear()]})
                            log[key] = mail_id
                        internal(activity).write({flag: bool(people) and not missing, 'notification_log': log,
                            'notification_error': self.env._('No email address for: %s', ', '.join(missing)) if missing else False})
                except (ValidationError, UserError, AccessError, MissingError, ValueError) as error:
                    _logger.warning('Activity %s email could not be queued: %s', activity.id, error)
                    internal(activity).write({'notification_error': str(error)})
            processed += len(records)
        self._cron_progress(processed, sum(self.search_count(d) for d in remaining_domains))

    @api.model
    def _cron_send_activity_alarms(self, limit=50):
        if self.env['ir.config_parameter'].sudo().get_param('kz_activity_management.alarms_enabled', 'True') == 'False':
            return
        domain = [('active', '=', True), ('alarm_datetime', '!=', False),
                  ('alarm_datetime', '<=', fields.Datetime.now()), ('alarm_sent', '=', False)]
        records = self.search(domain, order='id', limit=limit)
        for activity in records:
            activity._lock_transition()
            if activity.alarm_sent or not activity.active:
                continue
            for person in (activity.user_id | activity.assigned_user_ids).sudo().filtered('active'):
                self.env['bus.bus']._sendone(person.partner_id, 'simple_notification', {
                    'title': self.env._('Activity Reminder'),
                    'message': activity.summary or activity.activity_type_id.name or '',
                    'type': 'warning', 'sticky': True})
            internal(activity).write({'alarm_sent': True})
        self._cron_progress(len(records), self.search_count(domain))

    def _to_store_defaults(self, target):
        result = super()._to_store_defaults(target)
        if self._is_management_user():
            result += ['management_details', 'priority', 'is_timer_running', 'active',
                       'time_spent', 'remaining_hours', 'assignment_type', 'cancel_reason']
        return result
