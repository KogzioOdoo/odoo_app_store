User Access Control
=======================

Independent access-profile addon for Odoo 19.0, licensed under LGPL-3.0-or-later.

Install this directory in your server's addons path. Open Access Control as a
Settings administrator, create a profile, select users or groups, and configure
its restrictions. Company scope follows the active main company.

Model and record permissions, explicit field writes, required fields, standard
imports/exports, duplicate/archive, and standard report/server action restrictions
are checked on the server. Hidden fields, menus, buttons, tabs, and search
Trusted sudo operations and Odoo superuser mode bypass profile restrictions.
Settings administrators are restricted like other users, except that Disable
Login never applies to them, so they can always sign in and fix a profile.

Use Preview & Discovery to inspect effective restrictions and find view element
technical names. Multiple profiles combine restrictively and never grant access
beyond native Odoo permissions.
