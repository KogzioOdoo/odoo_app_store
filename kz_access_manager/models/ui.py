from copy import deepcopy
from inspect import unwrap
from lxml import etree

from odoo import api, models
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request
from odoo.tools import ormcache

from ..engine import transform_view

# Private marker: a client cannot forge a Python object through RPC, so only
# get_views() below can switch the single-view check off.
_BULK_KEY = 'am_bulk_views'
_BULK = object()

class BaseViews(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        # Hidden view types are removed from window actions by the controllers
        # (see controllers/main.py). get_views() must never drop a requested
        # view: a missing entry crashes the client (View.loadView) and
        # embedded x2many / dialog views also come through here.
        bulk = self.with_context(**{_BULK_KEY: _BULK})
        return super(BaseViews, bulk).get_views(views, options=options)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        if self.env.context.get(_BULK_KEY) is not _BULK and view_type in self._am_hidden_views():
            raise AccessError(self.env._('The %s view is disabled by your access profile.', view_type))
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        policy = self._am_policy()
        if not policy or not policy['profiles']:
            return result
        result = dict(result)
        root = etree.fromstring(result['arch'])

        def relation_of(model_name, field_name):
            field = self.env[model_name]._fields.get(field_name)
            return field.comodel_name if field and field.relational else None

        root = transform_view(root, self._name, policy, relation_of,
                              lambda name: self.env[name]._transient)
        result['arch'] = etree.tostring(root, encoding='unicode')
        return result

class Menus(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @ormcache('self.env.uid', 'self.env.company.id', 'tuple(self.env.companies.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        parent = super()._visible_menu_ids
        ids = set(unwrap(parent.__func__)(self, debug=debug))
        policy = self._am_policy()
        if not policy or not policy['menus']:
            return ids
        hidden = self.sudo().search([('id', 'child_of', policy['menus'])]).ids
        return ids - set(hidden)

    @api.model
    def load_menus(self, debug):
        return deepcopy(self._am_load_menus(debug))

    @api.model
    @ormcache('self.env.uid', 'self.env.company.id', 'tuple(self.env.companies.ids)', 'debug', 'self.env.lang')
    def _am_load_menus(self, debug):
        parent = super().load_menus
        return unwrap(parent.__func__)(self, debug)

    @api.model
    def load_menus_root(self):
        return deepcopy(self._am_load_menus_root())

    @api.model
    @ormcache('self.env.uid', 'self.env.company.id', 'tuple(self.env.companies.ids)', 'self.env.lang')
    def _am_load_menus_root(self):
        parent = super().load_menus_root
        return unwrap(parent.__func__)(self)

class Actions(models.Model):
    _inherit = 'ir.actions.actions'

    @api.model
    def get_bindings(self, model_name):
        result = super().get_bindings(model_name)
        policy = self._am_policy()
        if policy and policy['actions']:
            hidden = set(policy['actions'])
            result = {kind: [item for item in items if item['id'] not in hidden] for kind, items in result.items()}
        return result

    def _am_check_action(self):
        policy = self._am_policy()
        if policy and set(self.ids) & set(policy['actions']):
            raise AccessError(self.env._('This action or report is disabled by your access profile.'))

class ServerActions(models.Model):
    _inherit = 'ir.actions.server'

    def run(self):
        self.env['ir.actions.actions'].browse(self.ids)._am_check_action()
        return super().run()

class WindowActions(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        self.env['ir.actions.actions'].browse(self.ids)._am_check_action()
        return super()._get_action_dict()

class Reports(models.Model):
    _inherit = 'ir.actions.report'

    def _am_check_report(self, report_ref):
        report = self._get_report(report_ref)
        self.env['ir.actions.actions'].browse(report.ids)._am_check_action()

    @api.model
    def _render_qweb_html(self, report_ref, docids, data=None):
        self._am_check_report(report_ref)
        return super()._render_qweb_html(report_ref, docids, data=data)

    @api.model
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._am_check_report(report_ref)
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    @api.model
    def _render_qweb_text(self, report_ref, docids, data=None):
        self._am_check_report(report_ref)
        return super()._render_qweb_text(report_ref, docids, data=data)

class Users(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, credential, env):
        result = super()._check_credentials(credential, env)
        if self.env['am.policy']._login_disabled(self):
            raise AccessDenied()
        return result

    def write(self, vals):
        result = super().write(vals)
        if any(isinstance(id_, int) for id_ in self._ids) and any(
                name in vals for name in ('group_ids', 'company_ids', 'company_id', 'active')
        ):
            self.env.registry.clear_cache()
        return result

class Groups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        result = super().write(vals)
        if any(isinstance(id_, int) for id_ in self._ids) and any(
                name in vals for name in ('user_ids', 'implied_ids', 'implied_by_ids')
        ):
            self.env.registry.clear_cache()
        return result

class Http(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate(cls, endpoint):
        super()._authenticate(endpoint)
        if request.env.uid and (request.session.uid or endpoint.routing.get('auth') == 'bearer'):
            if request.env['am.policy']._login_disabled(request.env.user):
                request.session.logout(keep_db=True)
                raise AccessDenied()
            policy = request.env['am.policy']._for_env()
            if policy['global'].get('hide_debug'):
                request.session.debug = ''

    @classmethod
    def _am_debug_disabled(cls):
        uid = request.session.uid
        if not uid:
            return False
        policy = request.env(user=uid)['am.policy']._for_env()
        return bool(policy['global'].get('hide_debug'))

    @classmethod
    def _handle_debug(cls):
        super()._handle_debug()
        if cls._am_debug_disabled():
            request.session.debug = ''

    def session_info(self):
        result = super().session_info()
        policy = self.env['am.policy']._for_env()
        result['am_hide_debug'] = bool(policy['global'].get('hide_debug'))
        return result
