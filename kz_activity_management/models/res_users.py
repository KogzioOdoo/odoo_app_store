from odoo import api,fields, models
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    supervisor_id = fields.Many2one('res.users',string='Activity Supervisor',index=True,copy=False,help='Supervisor of this user in activity management.')
    subordinate_ids = fields.One2many('res.users','supervisor_id',string='Team Members',help='Shows the users assigned to this supervisor for activity management.')
    activity_portal_enabled = fields.Boolean(string='Portal Activity Access',help='Allow this portal user to view and complete activities explicitly assigned to them. Existing assigned portal users are retained during upgrade.')

    @api.constrains('supervisor_id')
    def _check_supervisor_cycle(self):
        # A user cannot supervise himself, and loops (A -> B -> A) are blocked.
        if self._has_cycle('supervisor_id'):
            raise ValidationError(self.env._('A user cannot be their own supervisor (directly or indirectly).'))
