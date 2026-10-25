# Phase 6 known issues and production readiness gaps

## High priority before public production

- Configure a production reverse proxy with HTTPS, request-size limits and rate limiting. The application does not provide distributed edge rate limiting.
- Automate encrypted PostgreSQL backups and perform a documented restore drill. Container volumes alone are not a backup.
- Replace all example secrets/passwords, restrict database exposure, and configure monitoring/alerting for API, database, disk and backup health.

## Medium priority

- Browser automation was not added because Playwright and its device browsers are not installed in this repository. Responsive behavior is covered by CSS/component checks and requires final testing on physical Android/iPad devices at 800×1280, 1280×800 and 1200×1920.
- Printing uses browser print/PDF. Direct Bluetooth ESC/POS, printer discovery and universal thermal-printer compatibility are intentionally unsupported.
- Search uses partial case-insensitive matching. This is appropriate for the planned shop dataset, but leading-wildcard name search may need PostgreSQL trigram indexes at larger multi-tenant scale.

## Low priority

- Several established frontend workflows remain large compact components. They are tested and functional, but should be decomposed when future phases add more behavior.
- Tenant branding supports a logo URL; binary logo upload/storage is not included.
- Offline operation and synchronization are not implemented. A network interruption can make the result of a submitted financial request uncertain, so operators must verify the record before retrying.

No unsupported printer/device combination is claimed as verified.
