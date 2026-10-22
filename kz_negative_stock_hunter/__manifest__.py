# -*- coding: utf-8 -*-
#    Kogzio Solutions | Negative Stock Hunder
#    Copyright (C) 2026-TODAY Kogzio Solutions (<https://www.kogzio.com>)
#    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Negative Stock Hunter',
    'version': '19.0.1.0.0',
    'category': 'Warehouse',
    'summary': 'Find Negative stock and the last moves that caused it',
    'description': """
Negative Stock Hunter
=====================
Finds every product and internal location where the on-hand quantity is
below zero and shows the last stock moves that caused it, so warehouse and
accounting teams can fix it fast.
 
Key features:
- List of negative stock by product and location
- Last stock moves for each product and location
- Filters by company, warehouse and product category
- Email alert when any quantity falls below zero
- Value of the negative quantity (cost x quantity)

Compatible with Odoo 19 Community and Enterprise.
   Contact: info@kogzio.com
   Website: https://www.kogzio.com
    """,
    'author': 'Kogzio Solutions',
    'maintainer':'Kogzio Solutions',
    'website': 'https://www.kogzio.com',
    'depends': ['stock','mail','purchase'],
    'data': [
        'security/ir.model.access.csv',
        'security/negative_stock_report_security.xml',
        'data/negative_stock_mail_template.xml',
        'data/negative_stock_cron.xml',
        'views/negative_stock_report_views.xml',
        'views/negative_stock_report_menus.xml',
        'views/negative_stock_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    "application": True,
}
