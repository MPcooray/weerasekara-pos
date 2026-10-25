import enum

from app.models.user import User, UserRole


class Permission(str, enum.Enum):
    DASHBOARD_VIEW = "dashboard.view"
    CUSTOMERS_VIEW = "customers.view"
    CUSTOMERS_CREATE = "customers.create"
    CUSTOMERS_EDIT = "customers.edit"
    CUSTOMERS_ARCHIVE = "customers.archive"
    EXAMINATIONS_VIEW = "examinations.view"
    EXAMINATIONS_CREATE = "examinations.create"
    PRESCRIPTIONS_FINALIZE = "prescriptions.finalize"
    POS_CHECKOUT = "pos.checkout"
    INVOICES_VIEW = "invoices.view"
    PAYMENTS_RECORD = "payments.record"
    QUOTATIONS_CREATE = "quotations.create"
    RETURNS_REQUEST = "returns.request"
    RETURNS_APPROVE = "returns.approve"
    REFUNDS_ISSUE = "refunds.issue"
    PRODUCTS_VIEW = "products.view"
    PRODUCTS_MANAGE = "products.manage"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_RECEIVE = "inventory.receive"
    SUPPLIERS_VIEW = "suppliers.view"
    SUPPLIERS_MANAGE = "suppliers.manage"
    SUPPLIER_COSTS_VIEW = "supplier_costs.view"
    ORDERS_VIEW = "orders.view"
    ORDERS_MANAGE = "orders.manage"
    ORDERS_SUPPLIER = "orders.supplier"
    ORDERS_QUALITY = "orders.quality"
    ORDERS_COLLECT = "orders.collect"
    ORDERS_OVERRIDE_BALANCE = "orders.override_balance"
    REPORTS_VIEW = "reports.view"
    STAFF_MANAGE = "staff.manage"
    SETTINGS_MANAGE = "settings.manage"


_all = set(Permission)
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.OWNER: _all,
    UserRole.MANAGER: _all
    - {
        Permission.EXAMINATIONS_CREATE,
        Permission.PRESCRIPTIONS_FINALIZE,
        Permission.STAFF_MANAGE,
        Permission.SETTINGS_MANAGE,
    },
    UserRole.CASHIER: {
        Permission.CUSTOMERS_VIEW,
        Permission.CUSTOMERS_CREATE,
        Permission.CUSTOMERS_EDIT,
        Permission.EXAMINATIONS_VIEW,
        Permission.POS_CHECKOUT,
        Permission.INVOICES_VIEW,
        Permission.PAYMENTS_RECORD,
        Permission.QUOTATIONS_CREATE,
        Permission.RETURNS_REQUEST,
        Permission.PRODUCTS_VIEW,
        Permission.ORDERS_VIEW,
        Permission.ORDERS_MANAGE,
        Permission.ORDERS_COLLECT,
    },
    UserRole.OPTOMETRIST: {
        Permission.CUSTOMERS_VIEW,
        Permission.CUSTOMERS_CREATE,
        Permission.CUSTOMERS_EDIT,
        Permission.EXAMINATIONS_VIEW,
        Permission.EXAMINATIONS_CREATE,
        Permission.PRESCRIPTIONS_FINALIZE,
        Permission.PRODUCTS_VIEW,
        Permission.ORDERS_VIEW,
        Permission.ORDERS_MANAGE,
        Permission.ORDERS_QUALITY,
    },
}


def has_permission(user: User, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[user.role]


def roles_for(permission: Permission) -> set[UserRole]:
    return {role for role, permissions in ROLE_PERMISSIONS.items() if permission in permissions}


def permission_names(role: UserRole) -> list[str]:
    return sorted(permission.value for permission in ROLE_PERMISSIONS[role])


CUSTOMER_WRITE_ROLES = roles_for(Permission.CUSTOMERS_EDIT)
CUSTOMER_ARCHIVE_ROLES = roles_for(Permission.CUSTOMERS_ARCHIVE)
EXAMINATION_FULL_READ_ROLES = roles_for(Permission.EXAMINATIONS_VIEW) - {UserRole.CASHIER}
EXAMINATION_WRITE_ROLES = roles_for(Permission.EXAMINATIONS_CREATE)
INVENTORY_WRITE_ROLES = roles_for(Permission.INVENTORY_ADJUST)
SUPPLIER_WRITE_ROLES = roles_for(Permission.SUPPLIERS_MANAGE)
CHECKOUT_ROLES = roles_for(Permission.POS_CHECKOUT)
PAYMENT_WRITE_ROLES = roles_for(Permission.PAYMENTS_RECORD)
QUOTATION_WRITE_ROLES = roles_for(Permission.QUOTATIONS_CREATE)
RETURN_REQUEST_ROLES = roles_for(Permission.RETURNS_REQUEST)
RETURN_APPROVE_ROLES = roles_for(Permission.RETURNS_APPROVE)
REFUND_WRITE_ROLES = roles_for(Permission.REFUNDS_ISSUE)
REPORT_READ_ROLES = roles_for(Permission.REPORTS_VIEW)
BRANDING_WRITE_ROLES = roles_for(Permission.SETTINGS_MANAGE)
ORDER_WRITE_ROLES = roles_for(Permission.ORDERS_MANAGE)
ORDER_SUPPLIER_ROLES = roles_for(Permission.ORDERS_SUPPLIER)
ORDER_QUALITY_ROLES = roles_for(Permission.ORDERS_QUALITY)
ORDER_COLLECTION_ROLES = roles_for(Permission.ORDERS_COLLECT)
