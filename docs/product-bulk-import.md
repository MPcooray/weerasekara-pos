# Product bulk import

Owners and managers can open **Inventory → Import**, download the official workbook, upload it for validation, review every row, and explicitly confirm the import. Cashiers and optometrists cannot see or call import operations.

## Safe workflow

1. Register any required suppliers first. Supplier names must match an active supplier exactly, ignoring letter case.
2. Download a fresh template. Do not rename sheets or columns.
3. Fill the Products sheet. Keep SKU and barcode cells formatted as text.
4. Choose **Create New Only** or **Update Existing**, then upload the `.xlsx` file.
5. Review totals and row-level errors. Preview stores a tenant-bound snapshot but does not create products or stock.
6. Correct the workbook and upload again until all rows are valid. The CSV error report is available for errors and warnings.
7. Confirm within 30 minutes. The server rechecks current SKUs, barcodes and suppliers inside one transaction.

## Duplicate modes

**Create New Only** rejects an SKU already used by the same tenant and never overwrites it. **Update Existing** matches only the tenant-scoped normalized SKU; it updates permitted catalog fields while historical invoice lines and movements remain unchanged. Names are never used for matching. A barcode belonging to another SKU is always rejected.

## Stock behavior

Initial Quantity creates an `opening_stock` movement only for a newly created tracked product. The importer calls the existing inventory mutation service and never writes a balance directly. Quantity on an existing product is ignored with a warning—even in Update Existing mode. Receive later deliveries through the normal stock-receiving interface.

## Security and recovery

Files must be `.xlsx`, at most 5 MB, 2,000 product rows and 30 columns. Expanded ZIP content, formulas, external workbook links, malformed files and unsupported versions are rejected. The parser does not evaluate formulas. A preview token is random, stored only as a hash, bound to the tenant and expires after 30 minutes. Confirmation requires an idempotency key and is atomic; a catalog change returns a conflict and requires a new preview.

If confirmation is interrupted, check the import result/catalog before retrying with the same preview. Repeated confirmation returns the completed result and does not receive stock twice.
