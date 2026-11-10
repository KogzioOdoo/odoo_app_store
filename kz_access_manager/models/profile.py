from odoo import api, fields, models
from odoo.exceptions import ValidationError
from ..engine import GLOBAL_FLAGS

class ConfigurationMixin(models.AbstractModel):
    _name = 'am.configuration.mixin'
    _description = 'Access configuration cache invalidation'

    def _am_invalidate(self):
        self.env.invalidate_all()
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._am_invalidate()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._am_invalidate()
        return result

    def unlink(self):
        result = super().unlink()
        self._am_invalidate()
        return result

class AccessProfile(models.Model):
    _name = 'am.profile'
    _inherit = ['am.configuration.mixin']
    _description = 'Access Profile'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, help='Enter a name for this access profile.')
    active = fields.Boolean(default=True,help='Enable or disable this access profile.')
    sequence = fields.Integer(default=10, help='Determines the display order of access profiles.')
    color = fields.Integer(default=4, help='Color used to identify this profile.')
    notes = fields.Text(help='Add internal notes about this access profile.')
    user_ids = fields.Many2many('res.users', string='Users', domain=[('share', '=', False)], help='Select the users who should receive this access profile.')
    group_ids = fields.Many2many('res.groups', string='User Groups', help='Apply this profile to all users belonging to the selected groups.')
    company_ids = fields.Many2many('res.company', string='Active Companies',help='Select the companies where this profile should apply. Leave empty to apply to all companies.')

    readonly = fields.Boolean(string='Read-only User', help='Prevents users from modifying business records.')
    disable_login = fields.Boolean(string='Disable Login', help='Prevents users from logging in.')
    hide_debug = fields.Boolean(string='Disable Developer Mode', help='Prevents users from accessing developer mode.')
    no_import = fields.Boolean(string='Disable Import', help='Disables the Import option for applicable models.')
    no_export = fields.Boolean(string='Disable Export', help='Disables the Export option for applicable models.')
    no_duplicate = fields.Boolean(string='Disable Duplicate', help='Prevents users from creating duplicate records.')
    no_archive = fields.Boolean(string='Disable Archive / Unarchive', help='Prevents users from archiving or unarchiving records.')
    hide_chatter = fields.Boolean(string='Hide Chatter', help='Hides the chatter on applicable records.')
    hide_send_message = fields.Boolean(string='Hide Send Message', help='Hides the Send Message option in the chatter.')
    hide_log_note = fields.Boolean(string='Hide Log Note', help='Hides the Log Note option in the chatter.')
    hide_activity = fields.Boolean(string='Hide Activities', help='Hides activities in the chatter.')
    hide_search_panel = fields.Boolean(string='Hide Search Panel', help='Hides the search panel in applicable views.')

    menu_ids = fields.Many2many('ir.ui.menu', string='Hidden Menus',help='Select the menus to hide from users, including their descendants.')
    server_action_ids = fields.Many2many('ir.actions.server', string='Restricted Server Actions', help='Select the server actions that users cannot execute.')
    report_action_ids = fields.Many2many('ir.actions.report', string='Restricted Reports', help='Select the reports that users cannot print.')
    window_action_ids = fields.Many2many('ir.actions.act_window', string='Restricted Window Actions', help='Select the window actions that users cannot open.')

    model_rule_ids = fields.One2many('am.model.rule', 'profile_id', string='Model Rules', copy=True,)

    field_rule_ids = fields.One2many('am.field.rule', 'profile_id', string='Field Rules', copy=True)

    domain_rule_ids = fields.One2many('am.domain.rule', 'profile_id', string='Record Domains', copy=True)

    node_rule_ids = fields.One2many('am.node.rule', 'profile_id', string='Buttons / Tabs / Filters', copy=True)

    rule_count = fields.Integer(compute='_compute_counts')
    user_count = fields.Integer(compute='_compute_counts')

    @api.depends('model_rule_ids', 'field_rule_ids', 'domain_rule_ids', 'node_rule_ids', 'user_ids')
    def _compute_counts(self):
        for record in self:
            record.rule_count = sum(len(record[name]) for name in ('model_rule_ids', 'field_rule_ids', 'domain_rule_ids', 'node_rule_ids'))
            record.user_count = len(record.user_ids)

    @api.constrains('user_ids', 'group_ids', 'active')
    def _check_audience(self):
        for profile in self:
            if profile.active and not (profile.user_ids or profile.group_ids):
                raise ValidationError(self.env._('An active profile needs at least one user or group. Save it as inactive while preparing it.'))

    def copy_data(self, default=None):
        # The standard Duplicate action creates the copy archived, so it is never applied by accident.
        vals_list = super().copy_data(default)
        for profile, vals in zip(self, vals_list):
            if not default or 'name' not in default:
                vals['name'] = self.env._('%s (copy)', profile.name)
            if not default or 'active' not in default:
                vals['active'] = False
        return vals_list

    def action_preview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Preview Effective Access'),
            'res_model': 'am.preview', 'view_mode': 'form', 'target': 'new',
            'context': {'default_user_id': self.user_ids[:1].id, 'default_company_id': self.env.company.id},
        }

    def _global_values(self):
        self.ensure_one()
        return {flag: bool(self[flag]) for flag in GLOBAL_FLAGS}
