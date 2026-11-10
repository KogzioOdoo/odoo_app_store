from odoo import api, models
from odoo.tools import ormcache
from ..engine import FIELD_FLAGS, GLOBAL_FLAGS, MODEL_FLAGS, empty_policy, merge_flags

class Policy(models.AbstractModel):
    _name = 'am.policy'
    _description = 'Effective Access Policy'

    @api.model
    def _for_env(self):
        if self.env.su or not self.env.uid:
            return empty_policy()
        user = self.env.user.sudo()
        return self._compiled(
            self.env.uid,
            self.env.company.id,
            tuple(sorted(user._get_group_ids()))
        )

    @api.model
    @ormcache('uid', 'company_id', 'group_ids')
    def _compiled(self, uid, company_id, group_ids):
        result = empty_policy()
        profiles = self.env['am.profile'].sudo().search([
            ('active', '=', True), '|', ('user_ids', 'in', [uid]), ('group_ids', 'in', list(group_ids)),
            '|', ('company_ids', '=', False), ('company_ids', 'in', [company_id]),
        ])
        for profile in profiles:
            result['profiles'].append({'id': profile.id, 'name': profile.name})
            merge_flags(result['global'], profile._global_values(), GLOBAL_FLAGS)
            result['menus'].extend(profile.menu_ids.ids)
            result['actions'].extend(profile.server_action_ids.ids)
            result['actions'].extend(profile.report_action_ids.ids)
            result['actions'].extend(profile.window_action_ids.ids)

            for rule in profile.model_rule_ids:
                target = result['models'].setdefault(rule.model_name, {})
                merge_flags(target, {flag: rule[flag] for flag in MODEL_FLAGS}, MODEL_FLAGS)
                target.setdefault('hidden_views', []).extend(rule._view_types())

            for rule in profile.field_rule_ids:
                values = {flag: rule[flag] for flag in FIELD_FLAGS}
                conditional = {}
                if rule.condition:
                    for flag in ('invisible', 'readonly', 'required'):
                        if values[flag]:
                            conditional[flag + '_if'] = rule.condition
                            values[flag] = False
                for field in rule.field_ids:
                    target = result['fields'].setdefault(rule.model_name, {}).setdefault(field.name, {})
                    merge_flags(target, values, FIELD_FLAGS)
                    for key, condition in conditional.items():
                        target.setdefault(key, []).append(condition)

            for rule in profile.node_rule_ids:
                result['nodes'].setdefault(rule.model_name, []).append({'kind': rule.kind, 'name': rule.node_name, 'condition': rule.condition or False})

            for rule in profile.domain_rule_ids:
                for operation in ('read', 'create', 'write', 'unlink'):
                    if rule['for_' + operation]:
                        result['domains'].setdefault(rule.model_name, {}).setdefault(operation, []).append(rule.domain)
        result['menus'] = sorted(set(result['menus']))
        result['actions'] = sorted(set(result['actions']))
        return result

    @api.model
    def _login_disabled(self, user):
        if not user or user._is_system() or user._is_superuser():
            return False
        return self._blocked_account(user.id, tuple(sorted(user._get_group_ids())))

    @api.model
    @ormcache('uid', 'group_ids')
    def _blocked_account(self, uid, group_ids):
        return bool(self.env['am.profile'].sudo().search_count([
            ('active', '=', True), ('disable_login', '=', True),
            '|', ('user_ids', 'in', [uid]), ('group_ids', 'in', list(group_ids)),
        ], limit=1))
