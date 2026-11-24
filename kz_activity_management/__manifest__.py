# -*- coding: utf-8 -*-
#  Kogzio Solutions | Activity Management
#  Copyright (C) 2026-TODAY Kogzio Solutions (<https://www.kogzio.com>)
#  License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    'name': 'Activity Management',
    'version': '19.0.1.1.1',
    'category' : 'Productivity',
    'website': 'https://www.kogzio.com',
    'summary': 'Team activities, follow-ups, shared work, timers and reminders',
    'description': """
Activity Management 
====================
Manage, track and monitor business activities from a centralized dashboard.

Built for Odoo 19 using the standard mail and portal dependencies.
Validate installation and upgrade on your own Odoo database.
WhatsApp sharing opens a prefilled message for the user to review and send;
the activity title, document name and deadline are included in that user-confirmed link.

Contact: info@kogzio.com
Website: https://www.kogzio.com/
    """,
    'depends': ['mail','portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'security/ir_rule_assignment.xml',

        'data/mail_template.xml',
        'data/ir_cron.xml',
        'data/ir_cron_alarm.xml',

        'views/activity_tag_views.xml',
        'views/mail_activity_views.xml',
        'views/res_users_views.xml',
        'views/dashboard_views.xml',
        'views/activity_report_views.xml',
        'views/res_config_settings_views.xml',

        'wizard/activity_cancel_wizard_views.xml',
        'wizard/activity_feedback_wizard_views.xml',
        'wizard/activity_mass_wizard_views.xml',
        'wizard/activity_bulk_close_wizard_views.xml',
        'wizard/activity_schedule_views.xml',


        'views/portal_templates.xml',

        'views/menus.xml',

    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'kz_activity_management/static/src/js/dashboard.js',
            'kz_activity_management/static/src/xml/dashboard.xml',
            'kz_activity_management/static/src/scss/dashboard.scss',
            'kz_activity_management/static/src/js/bell.js',
            'kz_activity_management/static/src/js/activity_patch.js',
            'kz_activity_management/static/src/xml/bell.xml',
            'kz_activity_management/static/src/xml/activity_info.xml',
        ]
    },
    'author': 'Kogzio Solutions',
    'maintainer': 'Kogzio Solutions',
    'support': 'info@kogzio.com',
    'license': 'LGPL-3',

}


