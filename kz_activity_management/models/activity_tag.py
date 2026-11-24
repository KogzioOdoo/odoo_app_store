from random import randint
from odoo import fields, models

class ActivityTag(models.Model):
    _name = 'activity.tag'
    _description = 'Activity Tag'
    _order = 'name'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char(
        string='Tag Name', required=True, translate=True,
        help="Enter a name to identify and organize activities using this tag.")
    color = fields.Integer(
        string='Color', default=_default_color,
        help="Choose a color to visually distinguish this tag from others.")
    active = fields.Boolean(
        default=True,
        help="Disable this option to archive the tag without deleting it.")
    company_id = fields.Many2one('res.company',string='Company',default=lambda self: self.env.company,help='Leave empty to share this tag with all companies.')
