from odoo import api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

from ..engine import model_policy

class Base(models.AbstractModel):
    _inherit = 'base'

    def _am_policy(self):
        if (self.env.su or not self.env.uid or self._name.startswith('am.') or self._name == 'ir.model.access'):
            return None
        policy = self.env['am.policy']._for_env()
        return policy if policy.get('profiles') else None


    def _am_model_policy(self):
        policy = self._am_policy()
        return model_policy(policy, self._name, self._transient) if policy else {}

    def _am_hidden_views(self):
        """Return the view types hidden for the current user on this model."""
        return set(self._am_model_policy().get('hidden_views', ()))

    def _am_exempt_domain(self):
        user = self.env.user.sudo()
        if self._name == 'res.users':
            return Domain('id', '=', self.env.uid)
        if self._name == 'res.partner':
            partners = user.partner_id | user.company_ids.partner_id
            return Domain('id', 'in', partners.ids)
        return None

    def _am_exempt_records(self, records):
        if self._name == 'res.partner':
            exempt_domain = self._am_exempt_domain()
            if exempt_domain is not None:
                return records.sudo().filtered_domain(exempt_domain)
        return records.browse()

    def _am_record_domain(self, policy, operation):
        values = policy['domains'].get(self._name, {}).get(operation, ())
        if not values:
            return None
        context = {'uid': self.env.uid, 'company_id': self.env.company.id, 'company_ids': self.env.companies.ids}
        try:
            domain = Domain.AND(Domain(safe_eval(value, context)) for value in values)
            exempt = self._am_exempt_domain()
            return domain | exempt if exempt is not None else domain
        except Exception as exc:
            raise AccessError(self.env._('An access domain for %s is invalid. Ask an administrator to repair it.', self._description)) from exc

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result:
            return result
        policy = self._am_policy()
        if not policy:
            return None
        if model_policy(policy, self._name, self._transient).get('deny_' + operation):
            return self, lambda: AccessError(self.env._(
                'Your access profile does not allow you to %(operation)s %(model)s.',
                operation=operation, model=self._description,
            ))
        domain = self._am_record_domain(policy, operation)
        if domain is not None and self.ids:
            allowed = self.sudo().filtered_domain(domain)
            failing = self.browse(set(self.ids) - set(allowed.ids))
            failing -= self._am_exempt_records(failing)
            if failing:
                return failing, lambda: AccessError(self.env._(
                    'Your access profile does not allow you to %(operation)s these %(model)s records.',
                    operation=operation, model=self._description,
                ))
        return None

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        if not kwargs.get('bypass_access'):
            policy = self._am_policy()
            if policy:
                extra = self._am_record_domain(policy, 'read')
                if extra is not None:
                    domain = Domain(domain) & extra
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    def _am_check_values(self, vals, creating=False):
        policy = self._am_policy()
        if not policy:
            return
        rules = model_policy(policy, self._name, self._transient)
        if not creating and rules.get('no_archive') and self._active_name and self._active_name in vals:
            raise AccessError(self.env._('Archiving and unarchiving are disabled for %s.', self._description))
        field_rules = policy['fields'].get(self._name, {})
        for name in vals:
            if field_rules.get(name, {}).get('readonly'):
                raise AccessError(self.env._('The field %s is read-only in your access profile.', name))

    def _am_check_required(self):
        policy = self._am_policy()
        if not policy:
            return
        for name, rule in policy['fields'].get(self._name, {}).items():
            if rule.get('required') and name in self._fields:
                for record in self.sudo():
                    value = record[name]
                    if value is False or value is None or value == '' or (self._fields[name].relational and not value):
                        raise ValidationError(self.env._('The field %s is required by your access profile.', self._fields[name].string))

    @api.model_create_multi
    def create(self, vals_list):
        policy = self._am_policy()
        if not policy or not policy['profiles']:
            return super().create(vals_list)
        for vals in vals_list:
            self._am_check_values(vals, creating=True)
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            records._am_check_required()
            records.check_access('create')
        return records

    def write(self, vals):
        policy = self._am_policy()
        if not policy or not policy['profiles']:
            return super().write(vals)
        self._am_check_values(vals)
        with self.env.cr.savepoint():
            result = super().write(vals)
            self._am_check_required()
            self.check_access('write')
        return result

    def copy(self, default=None):
        if self._am_model_policy().get('no_duplicate'):
            raise AccessError(self.env._('Duplicating %s is disabled.', self._description))
        return super().copy(default=default)

    def load(self, fields, data):
        if self._am_model_policy().get('no_import'):
            raise AccessError(self.env._('Importing %s is disabled.', self._description))
        return super().load(fields, data)

    def export_data(self, fields_to_export):
        policy = self._am_policy()
        if policy:
            if self._am_model_policy().get('no_export'):
                raise AccessError(self.env._('Exporting %s is disabled.', self._description))
            for path in fields_to_export:
                model = self
                for part in path.split('/'):
                    name = part.split(':', 1)[0]
                    if model_policy(policy, model._name, model._transient).get('no_export'):
                        raise AccessError(self.env._('Exporting %s is disabled.', model._description))
                    restriction = policy['fields'].get(model._name, {}).get(name, {})
                    if restriction.get('no_export'):
                        raise AccessError(self.env._('Exporting the field %s is disabled.', path))
                    field = model._fields.get(name)
                    if not field or not field.relational:
                        break
                    model = self.env[field.comodel_name]
        return super().export_data(fields_to_export)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        policy = self._am_policy()
        if not policy:
            return result
        result = {name: dict(info) for name, info in result.items()}
        for name, rule in policy['fields'].get(self._name, {}).items():
            if name not in result:
                continue
            for flag in ('readonly', 'required'):
                if rule.get(flag) and (attributes is None or flag in attributes):
                    result[name][flag] = True
            for flag, attr in (('no_export', 'exportable'), ('no_filter', 'searchable'), ('no_group', 'groupable')):
                if rule.get(flag):
                    result[name][attr] = False
        return result

    @api.model
    def am_ui_policy(self):
        rules = self._am_model_policy()
        return {name: bool(rules.get(name)) for name in ('no_import','no_archive', 'no_duplicate', 'no_export', 'hide_send_message','hide_log_note', 'hide_activity', 'hide_chatter', 'hide_debug')}
