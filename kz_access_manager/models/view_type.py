from odoo import fields, models

class AccessViewType(models.Model):
    _name = 'am.view.type'
    _description = 'View Type'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True, help='Name shown when choosing the view types to hide.')
    code = fields.Char(required=True, help='Technical view type, for example kanban.')
    sequence = fields.Integer(default=10, help='Determines the display order of view types.')

    _code_uniq = models.Constraint('UNIQUE(code)', 'The view type code must be unique.')
