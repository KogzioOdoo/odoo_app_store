import logging
from html import escape
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class NegativeStockAlert(models.Model):
    _name = 'negative.stock.alert'
    _description = 'Negative Stock Alert Tracking'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product',required=True,index=True,ondelete='cascade')
    location_id = fields.Many2one('stock.location',required=True,index=True,ondelete='cascade')
    company_id = fields.Many2one('res.company',required=True,index=True)
    quantity = fields.Float(readonly=True)
    active_issue = fields.Boolean(default=False, index=True)
    last_alert_date = fields.Datetime(readonly=True)

    _product_location_company_unique = models.Constraint(
        'unique(product_id, location_id, company_id)',
        'An alert record already exists for this product and location.',
    )

    @api.model
    def _get_alert_recipients(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'kz_negative_stock_hunter.alert_email', ''
        ) or ''

        return ','.join(
            email.strip()
            for email in value.replace(';', ',').split(',')
            if email.strip()
        )
    @api.model
    def _cron_check_negative_stock(self):
        # Check whether email alerts are enabled.
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'kz_negative_stock_hunter.alert_enabled',
            'False',
        )

        if enabled.lower() not in ('true', '1', 'yes'):
            _logger.info('Negative Stock Hunter: email alerts are disabled')
            return

        # Get the recipient email address.
        recipient = self._get_alert_recipients()

        if not recipient:
            _logger.warning('Negative Stock Hunter: configure an alert recipient email.')
            return

        Report = self.env['negative.stock.report'].sudo()
        Alert = self.sudo()

        reports = Report.search([('quantity', '<', 0)])
        current_issues = {}

        # Identify each issue by product, location, and company.
        for report in reports:
            key = (
                report.product_id.id,
                report.location_id.id,
                report.company_id.id or self.env.company.id,
            )
            current_issues[key] = report

        # Mark recovered issues as inactive.
        active_alerts = Alert.search([('active_issue', '=', True)])

        for alert in active_alerts:
            key = (
                alert.product_id.id,
                alert.location_id.id,
                alert.company_id.id,
            )
            if key not in current_issues:
                alert.write({'active_issue': False})

        template = self.env.ref( 'kz_negative_stock_hunter.email_template_negative_stock_alert',raise_if_not_found=False)

        if not template:
            _logger.error('Negative Stock Hunter email template was not found')
            return

        for key, report in current_issues.items():
            alert = Alert.search([
                ('product_id', '=', key[0]),
                ('location_id', '=', key[1]),
                ('company_id', '=', key[2]),
            ], limit=1)

            if alert and alert.active_issue:
                # Do not send duplicate emails for an existing issue.
                alert.write({'quantity': report.quantity})
                continue

            if not alert:
                alert = Alert.create({
                    'product_id': key[0],
                    'location_id': key[1],
                    'company_id': key[2],
                    'quantity': report.quantity,
                })
            else:
                alert.write({'quantity': report.quantity})

            try:
                template.send_mail(alert.id,force_send=False,email_values={'email_to': recipient},)
                alert.write({
                    'active_issue': True,
                    'last_alert_date': fields.Datetime.now(),
                })
            except Exception:
                _logger.exception(
                    'Failed to queue negative stock alert for product %s '
                    'at location %s.',
                    report.product_id.display_name,
                    report.location_id.display_name,
                )

    @api.model
    def _cron_send_daily_summary(self):
        # Check whether email alerts are enabled.
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'kz_negative_stock_hunter.alert_enabled','False',
        )

        if enabled.lower() not in ('true', '1', 'yes'):
            _logger.info('Negative Stock Hunter: daily summary is disabled')
            return

        recipient = self._get_alert_recipients()
        
        if not recipient:
            _logger.warning('Negative Stock Hunter: configure an alert recipient email')
            return

        alerts = self.sudo().search([('active_issue', '=', True)], order='company_id, location_id, product_id')

        if not alerts:
            _logger.info('Negative Stock Hunter: no active negative stock issues')
            return

        rows = []

        for alert in alerts:
            rows.append(
                '<tr>'
                f'<td>{escape(alert.product_id.display_name or "")}</td>'
                f'<td>{escape(alert.location_id.display_name or "")}</td>'
                f'<td>{escape(alert.company_id.display_name or "")}</td>'
                f'<td>{alert.quantity}</td>'
                '</tr>'
            )

        body = (
            '<p>Hello,</p>'
            '<p>Here is the daily summary of unresolved negative stock issues.</p>'
            '<table border="1" cellpadding="6" cellspacing="0">'
            '<thead><tr>'
            '<th>Product</th><th>Location</th>'
            '<th>Company</th><th>On Hand Quantity</th>'
            '</tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody>'
            '</table>'
            '<p>Please review and correct these stock issues.</p>'
            '<p>Negative Stock Hunter</p>'
        )

        try:
            self.env['mail.mail'].sudo().create({
                'subject': 'Daily Negative Stock Summary',
                'email_to': recipient,
                'body_html': body,
                'auto_delete': False,
            }).send()
        except Exception:
            _logger.exception('Negative Stock Hunter: failed to send daily summary')
