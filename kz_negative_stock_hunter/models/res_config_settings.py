from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_email_alerts = fields.Boolean(
        string='Enable Email Alerts',
        config_parameter='kz_negative_stock_hunter.alert_enabled',
        help='Enable email notifications when negative stock is detected.',
    )

    alert_recipient_email = fields.Char(
        string='Alert Email Recipients',
        config_parameter='kz_negative_stock_hunter.alert_email',
        help='Enter multiple email addresses separated by commas.',
    )
