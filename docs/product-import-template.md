# Product import template reference

Template version: **1.0**. Sheets: **Instructions** and **Products**. Required headings end in `*`. SKU and Barcode columns use Excel text format to retain leading zeroes.

| Column | Required | Rule |
|---|---:|---|
| SKU | Yes | 1–64 characters; letters, digits, `.`, `_`, `/`, `-`; normalized uppercase; tenant-unique |
| Barcode | No | 4–64 text characters; tenant-unique when supplied |
| Product Name | Yes | 2–180 characters |
| Category | Yes | Dropdown: `spectacle_frame`, `sunglasses`, `prescription_lens`, `contact_lens`, `accessory`, `optical_service` |
| Brand | No | Up to 100 characters |
| Model | No | Up to 100 characters |
| Color | No | Stored as supported frame color, up to 80 characters |
| Size | No | Stored as supported frame size, up to 40 characters |
| Supplier | No | Exact active supplier business name within the tenant |
| Cost Price (LKR) | Yes | Nonnegative LKR amount, maximum two decimal places |
| Selling Price (LKR) | Yes | Nonnegative LKR amount, maximum two decimal places |
| Initial Quantity | Yes | Nonnegative whole units; applied only to new tracked products |
| Reorder Level | Yes | Nonnegative whole units |
| Description | No | Up to 4,000 characters |
| Track Stock | Yes | `Yes` or `No`; must be `No` for optical services |
| Frame Material | No | Up to 80 characters |
| Frame Shape | No | Up to 80 characters |
| Lens Type | No | Up to 80 characters |
| Lens Material | No | Up to 80 characters |
| Made To Order | No | `Yes` or `No`; defaults to `No` |

The included rows are fictional examples and should be replaced or removed. Unknown suppliers/categories are validation errors; the importer never silently creates either. Tax configuration and additional contact-lens attributes should be completed through the normal product editor when required.
