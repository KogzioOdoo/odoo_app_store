"""Framework-independent restriction merging and XML transformation.

This file deliberately has no Odoo imports, so important policy behavior can be
tested without a running ERP. A checked flag always means a restriction.
"""
import ast
from copy import deepcopy

GLOBAL_FLAGS = (
    'readonly', 'disable_login', 'hide_debug', 'no_import', 'no_export',
    'no_duplicate', 'no_archive', 'hide_chatter', 'hide_send_message',
    'hide_log_note', 'hide_activity', 'hide_search_panel',
)
MODEL_FLAGS = (
    'deny_read', 'deny_create', 'deny_write', 'deny_unlink', 'no_import',
    'no_export', 'no_duplicate', 'no_archive', 'hide_chatter',
    'hide_send_message', 'hide_log_note', 'hide_activity', 'hide_search_panel',
)
FIELD_FLAGS = (
    'invisible', 'readonly', 'required', 'no_open', 'no_create', 'no_export',
    'no_filter', 'no_group',
)
VIEW_TYPES = (
    'list', 'form', 'kanban', 'calendar', 'pivot', 'graph', 'activity',
    'gantt', 'cohort', 'map', 'hierarchy',
)
FRAMEWORK_MODELS = {
    'res.users', 'res.groups', 'res.company', 'res.lang', 'res.currency',
    'res.currency.rate', 'decimal.precision', 'res.device',
}
FRAMEWORK_PREFIXES = ('ir.', 'am.', 'bus.', 'base.', 'web.', 'res.users.', 'res.groups.', 'res.device.', 'discuss.', 'mail.')

# Names a view expression may read besides the record's own fields.
CONDITION_CONTEXT_NAMES = frozenset({
    'context', 'parent', 'uid', 'id', 'current_date', 'today', 'allowed_company_ids',
})


def condition_names(expression):
    """Return the names an expression reads that must be technical field names.

    Raises SyntaxError when the expression is not valid Python.
    """
    tree = ast.parse(expression, mode='eval')
    bound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    read = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return read - bound - CONDITION_CONTEXT_NAMES


CHATTER_FLAGS = ('hide_chatter', 'hide_send_message', 'hide_log_note', 'hide_activity')

def empty_policy():
    return {
        'global': {}, 'models': {}, 'fields': {}, 'nodes': {},
        'domains': {}, 'menus': [], 'actions': [], 'profiles': [],
    }

def business_model(model_name, transient=False):
    return not (
        transient or model_name in FRAMEWORK_MODELS
        or model_name.startswith(FRAMEWORK_PREFIXES)
    )

def merge_flags(target, source, flags):
    for flag in flags:
        if source.get(flag):
            target[flag] = True


def model_policy(policy, model_name, transient=False):
    result = deepcopy(policy.get('models', {}).get(model_name, {}))
    global_flags = policy.get('global', {})
    business = business_model(model_name, transient)
    if not business:
        global_flags = {k: v for k, v in global_flags.items() if k not in CHATTER_FLAGS}
    merge_flags(result, global_flags, GLOBAL_FLAGS)
    if global_flags.get('readonly') and business:
        result.update(deny_create=True, deny_write=True, deny_unlink=True,
                      no_duplicate=True, no_archive=True, no_import=True,
                      hide_send_message=True, hide_log_note=True, hide_activity=True)
    return result

def combine_conditions(existing, conditions):
    parts = [f'({condition})' for condition in conditions]
    if existing and existing not in ('False', '0'):
        parts.insert(0, f'({existing})')
    return ' or '.join(parts)

def hide_action_views(action, hidden):
    """Remove hidden view types from a window-action dict, in place.

    The first remaining view becomes the default one. Returns False when no
    real view is left (everything is hidden), True otherwise.
    """
    hidden = set(hidden or ())
    if not hidden:
        return True
    views = action.get('views')
    if not views:
        views = [[False, mode] for mode in (action.get('view_mode') or '').split(',') if mode]
    kept = [list(view) for view in views if view[1] not in hidden]
    if not any(view[1] != 'search' for view in kept):
        return False
    action['views'] = kept
    action['view_mode'] = ','.join(view[1] for view in kept if view[1] != 'search')
    if action.get('mobile_view_mode') in hidden:
        action['mobile_view_mode'] = action['view_mode'].split(',')[0]
    return True

def transform_view(root, model_name, policy, relation_of=lambda model, field: None,
                   is_transient=lambda model: False):
    def visit(node, model, view_type):
        rules = model_policy(policy, model, is_transient(model))
        tag = node.tag if isinstance(node.tag, str) else ''
        if tag in VIEW_TYPES or tag == 'tree':
            view_type = 'list' if tag == 'tree' else tag
            for flag, attr in (
                ('deny_create', 'create'), ('deny_write', 'edit'),
                ('deny_unlink', 'delete'), ('no_duplicate', 'duplicate'),
                ('no_import', 'import'), ('no_export', 'export_xlsx'),
            ):
                if rules.get(flag):
                    node.set(attr, 'false')
            if rules.get('no_archive'):
                node.set('data-am-no-archive', '1')
            if rules.get('no_export'):
                node.set('data-am-no-export', '1')
        name = node.get('name')
        field_rules = policy.get('fields', {}).get(model, {}).get(name, {})
        node_rules = policy.get('nodes', {}).get(model, [])
        if tag == 'field':
            for flag in ('invisible', 'readonly', 'required'):
                if field_rules.get(flag):
                    node.set(flag, 'True')
                    if flag == 'invisible' and view_type == 'list':
                        node.set('column_invisible', 'True')
                conditions = field_rules.get(flag + '_if')
                if conditions:
                    node.set(flag, combine_conditions(node.get(flag), conditions))
            if field_rules.get('no_filter'):
                node.set('selectable', 'False')
            if field_rules.get('no_open') or field_rules.get('no_create'):
                additions = {}
                if field_rules.get('no_open'):
                    additions['no_open'] = True
                if field_rules.get('no_create'):
                    additions.update(no_create=True, no_quick_create=True, no_create_edit=True)
                    node.set('can_create', 'False')
                try:
                    options = ast.literal_eval(node.get('options', '{}'))
                    if not isinstance(options, dict):
                        options = {}
                except (ValueError, SyntaxError):
                    options = None
                if options is not None:
                    options.update(additions)
                    node.set('options', repr(options))
        if tag == 'chatter' and rules.get('hide_chatter'):
            parent = node.getparent() if hasattr(node, 'getparent') else None
            if parent is not None:
                parent.remove(node)
                return
            node.set('invisible', 'True')
        if tag == 'searchpanel' and rules.get('hide_search_panel'):
            parent = node.getparent() if hasattr(node, 'getparent') else None
            if parent is not None:
                parent.remove(node)
                return
        for rule in node_rules:
            if tag == rule['kind'] and name == rule['name']:
                if tag == 'filter':
                    parent = node.getparent() if hasattr(node, 'getparent') else None
                    if parent is not None:
                        parent.remove(node)
                        return
                condition = rule.get('condition')
                node.set('invisible', combine_conditions(node.get('invisible'), [condition]) if condition else 'True')
        child_model = relation_of(model, name) if tag == 'field' and name else None
        for child in list(node):
            visit(child, child_model or model, view_type)

    visit(root, model_name, root.tag)
    return root
