from odoo import api, models
from odoo.exceptions import AccessError

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_post(self, *, body='', subject=None, message_type='notification',
                     email_from=None, author_id=None, parent_id=False,
                     subtype_xmlid=None, subtype_id=False, partner_ids=None,
                     attachments=None, attachment_ids=None, body_is_html=False,
                     **kwargs):
        rules = self._am_model_policy()
        # Apply restrictions to manually posted chatter comments.
        # Keep automatic notifications working.
        if message_type == 'comment':
            # Hide Chatter: block all manual chatter comments.
            if rules.get('hide_chatter'):
                raise AccessError(self.env._('Posting messages in the chatter is disabled.'))

            note = self.env.ref('mail.mt_note')
            is_note = (
                subtype_xmlid == 'mail.mt_note'
                or subtype_id == note.id
                or (not subtype_xmlid and not subtype_id)
            )
            if is_note and rules.get('hide_log_note'):
                raise AccessError(self.env._('Posting log notes is disabled.'))
            if not is_note and rules.get('hide_send_message'):
                raise AccessError(self.env._('Sending chatter messages is disabled.'))
        return super().message_post(
            body=body,subject=subject,
            message_type=message_type,
            email_from=email_from,
            author_id=author_id,
            parent_id=parent_id,
            subtype_xmlid=subtype_xmlid,
            subtype_id=subtype_id,
            partner_ids=partner_ids,
            attachments=attachments,
            attachment_ids=attachment_ids,
            body_is_html=body_is_html,**kwargs,
        )


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            model = vals.get('res_model')
            if not model and vals.get('res_model_id'):
                model = (self.env['ir.model'].sudo().browse(vals['res_model_id']).model)
            if model and self.env[model]._am_model_policy().get('hide_activity'):
                raise AccessError(self.env._('Scheduling activities for this model is disabled.'))
        return super().create(vals_list)

class BaseImport(models.TransientModel):
    _inherit = 'base_import.import'

    def execute_import(self, fields, columns, options, dryrun=False):
        self.ensure_one()
        if self.env[self.res_model]._am_model_policy().get('no_import'):
            raise AccessError(self.env._('Importing this model is disabled.'))
        return super().execute_import(fields, columns, options, dryrun=dryrun)
