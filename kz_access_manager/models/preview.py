import json
from lxml import etree
from odoo import fields, models
from odoo.exceptions import AccessError
from ..engine import model_policy

class Preview(models.TransientModel):
    _name = 'am.preview'
    _description = 'Preview Effective Access'

    user_id = fields.Many2one('res.users', required=True, domain=[('share', '=', False)])
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    model_id = fields.Many2one('ir.model', required=True)
    result = fields.Text(string='Effective Restrictions', readonly=True)
    elements = fields.Text(string='Available View Elements', readonly=True)

    def _check_admin(self):
        if not self.env.user._is_system():
            raise AccessError(self.env._('Only administrators can preview other users.'))

    def action_preview(self):
        self.ensure_one()
        self._check_admin()
        if self.company_id not in self.user_id.company_ids:
            self.result = self.env._('This user does not have access to the selected company.')
        else:
            target = self.env[self.model_id.model].with_user(self.user_id).with_context(allowed_company_ids=[self.company_id.id])
            policy = target._am_policy()
            if not policy:
                data = {'no_restrictions': True, 'message': 'No profile restrictions apply to this user.'}
            else:
                data = {
                    'profiles': policy['profiles'], 'model': model_policy(policy, target._name, target._transient),
                    'fields': policy['fields'].get(target._name, {}), 'nodes': policy['nodes'].get(target._name, []),
                    'record_domains': policy['domains'].get(target._name, {}),
                    'hidden_menu_ids': policy['menus'], 'restricted_action_ids': policy['actions'],
                }
            self.result = json.dumps(data, indent=2, ensure_ascii=False)
        return self._reopen()

    def action_discover(self):
        self.ensure_one()
        self._check_admin()
        found = set()
        target = self.env[self.model_id.model]
        for kind in ('form', 'list', 'kanban', 'search'):
            try:
                view = target.get_view(view_type=kind)
                root = etree.fromstring(view['arch'])
                for node in root.xpath('.//button[@name] | .//page[@name] | .//filter[@name]'):
                    if any(parent.tag == 'field' for parent in node.iterancestors()):
                        continue
                    found.add((kind, node.tag, node.get('name'), node.get('string') or ''))
            except (ValueError, AccessError, etree.XMLSyntaxError):
                continue
        self.elements = '\n'.join(' | '.join(row) for row in sorted(found)) or self.env._('No named elements found.')
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'name': self.env._('Preview & Discovery'), 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
