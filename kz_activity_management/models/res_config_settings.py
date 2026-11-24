from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activity_table_limit = fields.Integer(
        string='Dashboard Table Records',config_parameter='kz_activity_management.table_limit',default=10,
        help='Number of activity shown per page in the dashboard table.',
    )
    activity_due_emails_enabled = fields.Boolean(
        string='Due and Overdue Emails',config_parameter='kz_activity_management.due_emails_enabled',default=True,
        help='Enable automatic email notifications for activities that are due today or overdue.',
    )
    activity_alarms_enabled = fields.Boolean(
        string='Reminder Popups',config_parameter='kz_activity_management.alarms_enabled',default=True,
        help='Enable activity reminder popup notifications and work bell alerts at the scheduled reminder time.',
    )

    @api.constrains('activity_table_limit')
    def _check_activity_table_limit(self):
        if any(not 1 <= settings.activity_table_limit <= 100 for settings in self):
            raise ValidationError(self.env._('Choose a dashboard page size between 1 and 100.'))
