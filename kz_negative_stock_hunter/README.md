# Negative Stock Hunter
### Identify negative inventory before it becomes a bigger problem.

Negative Stock Hunter is an Odoo 19 Inventory reporting module that helps teams quickly find products with negative on-hand quantities and investigate where the issue occurs.

## Why Negative Stock Hunter?

Negative stock can make inventory figures harder to trust and can signal missing, delayed, or incorrectly recorded stock operations. This module brings negative-quantity records into a focused report so users can review the affected products and locations.

## Key Features

- **Focused negative stock report** — identify products whose reported on-hand quantity is below zero.
- **Product and category context** — review the product and its category alongside the quantity.
- **Location and warehouse visibility** — locate where negative stock is reported.
- **Company context** — see the company associated with each report entry.
- **Recent stock movement details** — inspect available movement information to help investigate the reported quantity.
- **Visual quantity highlighting** — negative quantities are highlighted to make issues easier to spot.
- **Search, filters, and grouping** — narrow down report results using the available Odoo list-view tools.
- **Read-only report access** — authorized users can inspect report records without creating, editing, or deleting them through the report model.
- **Multi-company visibility rules** — report visibility follows the configured company access rules.

## Requirements

- Odoo 19.0
- Odoo Inventory (`stock`)

## Installation

1. Copy the `kz_negative_stock_hunter` folder into an Odoo custom addons directory.
2. Restart the Odoo server.
3. Sign in with an administrator account.
4. Open **Apps** and update the Apps List if required.
5. Search for **Negative Stock Hunter**.
6. Select **Install**.

## How to Use

1. Open the **Inventory** application.
2. Go to **Reporting → Negative Stock**.
3. Review the products and quantities shown in the report.
4. Use the product, location, warehouse, and company details to identify where the issue is occurring.
5. Use search, filters, and grouping to focus on the records you need to investigate.
6. Review the available stock movement details for additional context.

## Access and Security

The report is designed for read-only analysis. Users need the appropriate Inventory group and model read access to open it. Menu visibility also depends on the configured menu groups.

For multi-company databases, users should only see records permitted by the module's record rule and their allowed-company configuration. Validate access using a regular Inventory user as well as an administrator.

## Important Information

- Negative Stock Hunter is a reporting and investigation tool; it does not automatically fix stock discrepancies.
- Results depend on the report query and the inventory data currently stored in Odoo.
- Recent movement details are limited to the records and fields implemented in the installed module.
- Confirm the module's access rights and company rules in a test database before deploying to production.

## Compatibility

| Item | Details |
|---|---|
| Odoo version | 19.0 |
| Edition | Community and Enterprise, subject to the installed dependencies |
| Application | Inventory |
| Category | Inventory / Reporting |
| License | LGPL-3 |

## Author

**Kogzio Solutions**   
**Contact:** info@kogzio.com

## License

This module is distributed under the **GNU Lesser General Public License, version 3 (LGPL-3)**.
