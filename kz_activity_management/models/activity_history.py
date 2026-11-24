from odoo import fields, models

class ActivityHistory(models.Model):
    _name = 'activity.history'
    _description = 'Activity Transition History'
    _order = 'occurred_at desc, id desc'

    activity_id = fields.Many2one(
        'mail.activity', required=True, ondelete='cascade', index=True,
        help="The activity associated with this history record.")
    occurred_at = fields.Datetime(
        required=True, default=fields.Datetime.now, readonly=True,
        help="Shows the date and time when this activity event occurred.")
    actor_id = fields.Many2one(
        'res.users', string='Changed By', readonly=True,
        help="Shows the user who performed this action.")
    responsible_id = fields.Many2one(
        'res.users', string='Responsible Person', readonly=True,
        help="Shows the person responsible for the activity when this event occurred.")
    event = fields.Selection([
        ('done', 'Completed'), ('cancelled', 'Cancelled'), ('reopened', 'Reopened'),
        ('reassigned', 'Reassigned'),
    ], required=True, readonly=True,
        help="Shows the action recorded in the activity history.")
    details = fields.Text(
        readonly=True,
        help="Additional information about the recorded activity event.")
