# -*- coding: utf-8 -*-
#  Kogzio Solutions | Access Manager
#  Copyright (C) 2026-TODAY Kogzio Solutions (<https://www.kogzio.com>)
#  License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Access Manager',
    'version': '19.0.1.0.1',
    'category': 'Extra Tools',
    'summary': 'User and company access profiles for models, fields, records, and views',
    'description': """
Access Manager
==============
Control what each user can see and do from one place: menus, models, fields,
records, buttons, tabs, views, chatter, import/export and developer mode.

Compatible with Odoo 19 Community and Enterprise.

Contact: info@kogzio.com
Website: https://www.kogzio.com
""",
    'license': 'LGPL-3',
    'author': 'Kogzio Solutions',
    'maintainer':'Kogzio Solutions',
    'website': 'https://www.kogzio.com',
    'depends': ['base', 'web', 'mail', 'base_import'],
    'data': [
        'security/ir.model.access.csv',
        'data/view_type_data.xml',
        'views/profile_views.xml',
        'views/rule_views.xml',
        'views/preview_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kz_access_manager/static/src/js/access_controls.js',
            'kz_access_manager/static/src/xml/chatter.xml',
            'kz_access_manager/static/src/scss/access_manager.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'auto_install': False,
    'installable': True,
}
