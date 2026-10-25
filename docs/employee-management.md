# Employee management

Only an owner can open **Employees** or use `/api/v1/staff` endpoints.

## Creating an employee

Create the account with the minimum required information: full name, email, role and a temporary password of at least 12 characters. The employee can authenticate with that password, but all business endpoints remain blocked until they replace it through the forced password-change screen.

Do not send passwords through ordinary email or chat. Communicate the temporary password separately and ask the employee to change it immediately.

## Access changes

- Role and active-state changes take effect for existing access tokens on their next API request because authorization reads the current database user.
- Deactivation invalidates practical access immediately; login and authenticated endpoints reject inactive accounts.
- Resetting credentials clears login lockout state and forces another password change.
- Normal administration deactivates accounts instead of deleting them, preserving references and audit history.
- An owner cannot change their own role or deactivate their own account in the employee screen.
- The final active owner cannot be demoted or deactivated.
- Employee IDs are always resolved inside the authenticated tenant.

Employee creation, updates, role changes and credential resets are recorded in `audit_logs`. Passwords and password hashes are never included in audit records or application responses.
