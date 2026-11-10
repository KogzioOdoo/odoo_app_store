from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

from ..engine import condition_names

# Models a profile may never restrict: restricting them can lock administrators out.
PROTECTED_MODELS = ('res.users', 'res.groups')
PROTECTED_PREFIXES = ('am.', 'ir.', 'res.users.', 'res.groups.')

class RuleMixin(models.AbstractModel):
    _name = 'am.rule.mixin'
    _inherit = 'am.configuration.mixin'
    _description = 'Access Rule'
    _rec_name = 'model_id'

    profile_id = fields.Many2one('am.profile', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade', index=True, domain=[
        ('model', 'not like', 'am.%'), ('model', 'not like', 'ir.%'),
        ('model', 'not like', 'res.users%'), ('model', 'not like', 'res.groups%'),
    ], help='Model the rule applies to. Framework models (ir.*, res.users, res.groups) cannot be restricted.')
    model_name = fields.Char(string='Technical Model Name', related='model_id.model', readonly=True)

    @api.constrains('model_id')
    def _check_target_model(self):
        for rule in self:
            model = rule.model_id.model
            if model in PROTECTED_MODELS or model.startswith(PROTECTED_PREFIXES):
                raise ValidationError(self.env._('The framework model %s cannot be restricted: it could lock administrators out.', model))

class ConditionMixin(models.AbstractModel):
    _name = 'am.condition.mixin'
    _description = 'Rule Condition Mixin'

    condition = fields.Char(help=(
        "Expression using technical field names of the selected model, for example state == 'draft'. "
        "The restriction applies only while it is true; leave empty to always apply. "
        "Interface only: the fields must also be present in the view, and a conditional "
        "read-only or required setting is not enforced on the server."))

    @api.constrains('condition', 'model_id')
    def _check_condition(self):
        for rule in self.filtered('condition'):
            try:
                names = condition_names(rule.condition)
            except SyntaxError as exc:
                raise ValidationError(self.env._('Invalid condition: %s', exc)) from exc
            model = rule.model_id.model
            known = set(self.env[model]._fields) if model in self.env else set()
            if unknown := sorted(names - known):
                raise ValidationError(self.env._(
                    'Unknown field(s) in the condition: %(fields)s. Use technical field names of %(model)s.',
                    fields=', '.join(unknown), model=rule.model_id.name))

class ModelRule(models.Model):
    _name = 'am.model.rule'
    _inherit = 'am.rule.mixin'
    _description = 'Model Restriction'

    deny_read = fields.Boolean(string='Deny Read',help='Blocks reading records of this model.')
    deny_create = fields.Boolean(string='Deny Create', help='Blocks creating records of this model.')
    deny_write = fields.Boolean(string='Deny Edit', help='Blocks editing records of this model.')
    deny_unlink = fields.Boolean(string='Deny Delete',help='Blocks deleting records of this model.')
    no_import = fields.Boolean(string='Disable Import', help='Hides the Import option for this model.')
    no_export = fields.Boolean(string='Disable Export', help='Hides the export option for this model.')
    no_duplicate = fields.Boolean(string='Disable Duplicate', help='Hides the duplicate option for this model.')
    no_archive = fields.Boolean(string='Disable Archive / Unarchive', help='Hides the archive option for this model.')
    hide_chatter = fields.Boolean(string='Hide Chatter', help='Hides the chat option for this model.')
    hide_send_message = fields.Boolean(string='Hide Send Message', help='Hides Send Message in the chatter for this model.')
    hide_log_note = fields.Boolean(string='Hide Log Note', help='Hides Log Note in the chatter for this model.')
    hide_activity = fields.Boolean(string='Hide Activities', help='Hides Activities in the chatter for this model.')
    hide_search_panel = fields.Boolean(string='Hide Search Panel', help='Hides the search panel on views for this model.')
    hidden_view_type_ids = fields.Many2many('am.view.type',string='Hidden View Types',domain="[('id', 'in', available_view_type_ids)]",
        help='View types hidden for this model. Only the views of the selected model are listed.')
    available_view_type_ids = fields.Many2many('am.view.type',compute='_compute_available_view_type_ids')

    @api.depends('model_id')
    def _compute_available_view_type_ids(self):
        for rule in self:
            codes = set()
            if rule.model_id:
                model = rule.model_id.model
                views = self.env['ir.ui.view'].sudo().search([('model', '=', model)])
                codes.update(views.mapped('type'))
                actions = self.env['ir.actions.act_window'].sudo().search([('res_model', '=', model)])
                for action in actions:
                    codes.update(mode.strip() for mode in (action.view_mode or '').split(','))
            rule.available_view_type_ids = self.env['am.view.type'].search([('code', 'in', list(codes))])

    def _view_types(self):
        self.ensure_one()
        return self.hidden_view_type_ids.mapped('code')

class FieldRule(models.Model):
    _name = 'am.field.rule'
    _inherit = ['am.rule.mixin', 'am.condition.mixin']
    _description = 'Field Restriction'

    field_ids = fields.Many2many('ir.model.fields', string='Fields', required=True, domain="[('model_id', '=', model_id)]", help='Fields the rule applies to.')
    invisible = fields.Boolean(string='Invisible', help='Hide in standard views; does not make field values confidential through APIs.')
    readonly = fields.Boolean(string='Read-only',help='Also rejects explicit field writes through RPC and imports (server side only when no condition is set).')
    required = fields.Boolean(string='Required',help='Enforced after create and write as well as in the form (server side only when no condition is set).')
    no_open = fields.Boolean(string='Hide Internal Link', help='Hides the link that opens the related record.')
    no_create = fields.Boolean(string='Disable Relational Create / Create & Edit', help='UI convenience. Restrict the related model to deny creation through APIs.')
    no_export = fields.Boolean(string='Exclude from Export', help='Fields cannot be selected in export.')
    no_filter = fields.Boolean(string='Hide from Custom Filters', help='Fields cannot be used in custom filters.')
    no_group = fields.Boolean(string='Hide from Group By', help='Fields cannot be used in Group By.')

    @api.onchange('model_id')
    def _onchange_model(self):
        self.field_ids = self.field_ids.filtered(lambda field: field.model_id == self.model_id)

    @api.constrains('field_ids', 'model_id', 'required', 'readonly')
    def _check_fields(self):
        for rule in self:
            if not rule.field_ids or any(field.model_id != rule.model_id for field in rule.field_ids):
                raise ValidationError(self.env._('Select fields belonging to the selected model.'))
            if rule.required and any(field.ttype == 'boolean' for field in rule.field_ids):
                raise ValidationError(self.env._('Required is not meaningful for Boolean fields. Use a record domain to require a true value.'))
            if rule.readonly and any(field.name in ('id', 'display_name', 'create_uid', 'create_date', 'write_uid', 'write_date') for field in rule.field_ids):
                raise ValidationError(self.env._('System-maintained fields cannot have write restrictions.'))

class DomainRule(models.Model):
    _name = 'am.domain.rule'
    _inherit = 'am.rule.mixin'
    _description = 'Record Domain Restriction'

    domain = fields.Text(required=True, default='[]', help='Allowed records. Variables: uid, company_id, company_ids. Multiple rules are combined using AND.')
    for_read = fields.Boolean(string='Read', default=True, help='The domain applies when reading existing records.')
    for_create = fields.Boolean(string='Create', help='The domain applies when creating a new record.')
    for_write = fields.Boolean(string='Edit', help='The domain applies when editing a record.')
    for_unlink = fields.Boolean(string='Delete', help='The domain applies when deleting a record.')

    def _evaluate(self, uid, company_id, company_ids):
        self.ensure_one()
        return Domain(safe_eval(self.domain, {'uid': uid, 'company_id': company_id, 'company_ids': company_ids}))

    @api.constrains('domain', 'model_id', 'for_read', 'for_create', 'for_write', 'for_unlink')
    def _check_domain(self):
        for rule in self:
            if not any(rule[field] for field in ('for_read', 'for_create', 'for_write', 'for_unlink')):
                raise ValidationError(self.env._('A domain rule must apply to at least one operation.'))
            try:
                rule._evaluate(self.env.uid, self.env.company.id, self.env.companies.ids).optimize_full(self.env[rule.model_id.model].sudo())
            except Exception as exc:
                raise ValidationError(self.env._('Invalid record domain: %s', str(exc))) from exc

class NodeRule(models.Model):
    _name = 'am.node.rule'
    _inherit = ['am.rule.mixin', 'am.condition.mixin']
    _description = 'Button, Tab, or Search Filter Restriction'

    kind = fields.Selection([('button', 'Button / Smart Button'), ('page', 'Notebook Tab'), ('filter', 'Search Filter / Group By')], default='button', required=True, help='Choose what to hide: a button, a notebook tab, or a search filter / group by.')
    node_name = fields.Char(string='Technical Name', required=True, help='Exact name attribute from the view XML. Use Discover View Elements to find it.')
    label = fields.Char(string='Label / Notes', help=' Optional note to remember what this item is.')

