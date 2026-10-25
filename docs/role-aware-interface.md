# Role-aware interface

The signed-in user's `/auth/me` response includes explicit permission names. Desktop and mobile navigation are built from those permissions.

- Cashiers see customers, product availability, POS, quotations and operational orders. Supplier identity, product cost, inventory valuation, stock movements, refunds and reports are not displayed.
- Optometrists see customers, examinations, product availability and optical-order quality work. Financial and supplier workspaces are absent.
- Managers see operational, stock and financial reporting workspaces, but not employee or tenant settings.
- Owners see all workspaces, including Employees and print branding.

Direct navigation does not bypass authorization: protected APIs return `403`, while tenant-scoped lookups do not disclose another tenant's records. Responsive mobile navigation uses the same permission list as the desktop sidebar.
