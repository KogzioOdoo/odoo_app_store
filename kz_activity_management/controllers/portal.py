from odoo import http
from odoo.fields import Domain
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class ActivityPortal(CustomerPortal):
    def _portal_enabled(self):
        user = request.env.user
        return user.share and user.sudo().activity_portal_enabled

    def _ownership_domain(self):
        user = request.env.user
        return list(Domain.AND([
            ['|', ('user_id', '=', user.id), ('assigned_user_ids', 'in', [user.id])],
            ['|', ('company_id', '=', False), ('company_id', 'in', user.sudo().company_ids.ids)],
        ]))

    def _get_my_activity(self, activity_id):
        if not self._portal_enabled():
            return request.env['mail.activity']
        return request.env['mail.activity'].sudo().with_context(active_test=False).search(
            Domain.AND([self._ownership_domain(), [('id', '=', activity_id)]]), limit=1)

    @http.route(['/my/activity', '/my/activity/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_activity(self, page=1, search='', status='active', sortby='deadline', **kwargs):
        if not request.env.user.share:
            return request.redirect('/web')
        if not self._portal_enabled():
            raise request.not_found()
        statuses = {'active': [('active', '=', True)], 'all': [],
                    'done': [('active', '=', False), ('cancelled_date', '=', False)],
                    'cancelled': [('active', '=', False), ('cancelled_date', '!=', False)],
                    'overdue': [('management_state', '=', 'overdue')],
                    'today': [('management_state', '=', 'today')]}
        if status not in statuses:
            status = 'active'
        orders = {'deadline': 'date_deadline asc, id desc', 'summary': 'summary asc, id desc', 'recent': 'write_date desc, id desc'}
        if sortby not in orders:
            sortby = 'deadline'
        search = str(search or '')[:100]
        domain = Domain.AND([self._ownership_domain(), statuses[status]])
        if search:
            domain &= Domain.OR([[('summary', 'ilike', search)], [('res_name', 'ilike', search)]])
        Activity = request.env['mail.activity'].sudo().with_context(active_test=False)
        total = Activity.search_count(domain)
        page = min(max(int(page), 1), max(1, (total + 19) // 20))
        args = {'search': search, 'status': status, 'sortby': sortby}
        pager = portal_pager('/my/activity', total, page=page, step=20, url_args=args)
        activities = Activity.search(domain, limit=20, offset=pager['offset'], order=orders[sortby])
        return request.render('kz_activity_management.portal_my_activity', {
            'activity': activities, 'total': total, 'pager': pager, 'search': search,
            'selected_status': status, 'sortby': sortby, 'page_name': 'activity',
        })

    @http.route('/my/activity/<int:activity_id>', type='http', auth='user', website=True)
    def portal_activity_detail(self, activity_id, **kwargs):
        activity = self._get_my_activity(activity_id)
        if not activity:
            raise request.not_found()
        return request.render('kz_activity_management.portal_activity_detail', {
            'activity': activity, 'page_name': 'activity',
            'status_label': dict(activity._fields['state']._description_selection(request.env)).get(activity.state, activity.state),
        })

    @http.route('/my/activity/<int:activity_id>/done', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_activity_done(self, activity_id, **post):
        activity = self._get_my_activity(activity_id)
        if not activity:
            raise request.not_found()
        if activity.active:
            feedback = str(post.get('feedback') or '').strip()[:5000]
            activity.action_feedback(feedback=feedback)
        return request.redirect('/my/activity?status=done', code=303)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'activity_count' in counters:
            values['activity_count'] = (request.env['mail.activity'].sudo().search_count(self._ownership_domain())
                                        if self._portal_enabled() else 0)
        return values
