from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.web.controllers.action import Action
from odoo.addons.web.controllers.dataset import DataSet

from ..engine import hide_action_views

def clean_window_action(action):
    """Remove the view types hidden by the user's access profiles from an action."""
    if not (isinstance(action, dict) and action.get('type') == 'ir.actions.act_window'):
        return action
    model = action.get('res_model')
    if not model or model not in request.env:
        return action
    hidden = request.env[model]._am_hidden_views()
    if hidden and not hide_action_views(action, hidden):
        raise AccessError(request.env._(
            'All views of "%s" are disabled by your access profile. Please contact your administrator.',
            action.get('name') or request.env[model]._description,
        ))
    return action

class AccessAction(Action):
    @http.route()
    def load(self, *args, **kwargs):
        return clean_window_action(super().load(*args, **kwargs))

    @http.route()
    def run(self, *args, **kwargs):
        return clean_window_action(super().run(*args, **kwargs))

class AccessDataSet(DataSet):
    @http.route()
    def call_button(self, *args, **kwargs):
        return clean_window_action(super().call_button(*args, **kwargs))