# Role and permission matrix

Phase 7.1 uses the central matrix in `apps/api/app/core/permissions.py` as the source of truth. API authorization is mandatory; hidden navigation is only a usability measure.

| Capability | Owner | Manager | Cashier | Optometrist |
| --- | --- | --- | --- | --- |
| View/create/edit customers | Yes | Yes | Yes | Yes |
| Archive customers | Yes | Yes | No | No |
| View clinical records | Yes | Yes | Finalized only | Yes |
| Create/finalize examinations | Yes | No | No | Yes |
| Checkout, invoices and payments | Yes | Yes | Yes | No |
| Create quotations | Yes | Yes | Yes | No |
| Request returns | Yes | Yes | Yes | No |
| Approve returns and issue refunds | Yes | Yes | No | No |
| View products and availability | Yes | Yes | Yes | Yes |
| Manage products, suppliers and stock | Yes | Yes | No | No |
| View supplier costs and stock valuation | Yes | Yes | No | No |
| View/manage optical orders | Yes | Yes | Yes | Yes |
| Supplier tracking | Yes | Yes | No | No |
| Quality checks | Yes | Yes | No | Yes |
| Collect orders | Yes | Yes | Yes | No |
| Override collection with balance | Yes | Yes | No | No |
| Dashboard and financial reports | Yes | Yes | No | No |
| Employee accounts | Yes | No | No | No |
| Tenant/print settings | Yes | No | No | No |

The project deliberately retains four roles. Inventory clerk and lab technician roles were not added because current workflows do not justify separate stable permission bundles yet.

Changes to this matrix require backend tests for allowed and denied paths. Never rely on a frontend role name to protect an endpoint.
