import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PrintDocument } from "../../lib/api";
import { PrintableDocument } from "./PrintPreview";

const document: PrintDocument = {
  document_type: "invoice", document_id: "invoice-1", document_number: "INV-2026-000001",
  occurred_at: "2026-10-24T10:00:00Z", status: "finalized", customer_name: "Nimal Perera",
  related_number: null, payment_method: null, external_reference: null, reason: null,
  subtotal_minor: 125000, discount_minor: 5000, tax_minor: 18000, total_minor: 138000,
  paid_minor: 100000, outstanding_minor: 38000,
  lines: [{ description: "Classic Frame", sku: "FR-1", quantity: 1, unit_price_minor: 125000, discount_minor: 5000, tax_minor: 18000, total_minor: 138000 }],
  branding: { business_display_name: "Weerasekara Optics", business_address: "Colombo", business_contact: "011 234 5678", logo_url: null, invoice_footer: "Thank you", receipt_footer: "Come again", business_registration: null, tax_registration: null, default_currency: "LKR" },
};

describe("financial print layouts", () => {
  it("renders invoice snapshot totals and tenant branding", () => {
    const output = renderToStaticMarkup(<PrintableDocument document={document} paper="a4" />);
    expect(output).toContain("INV-2026-000001");
    expect(output).toContain("Weerasekara Optics");
    expect(output).toContain("Classic Frame");
    expect(output).toContain("Outstanding");
    expect(output).toContain("print-document--a4");
  });

  it("renders the same immutable document as an 80 mm receipt", () => {
    const output = renderToStaticMarkup(<PrintableDocument document={{ ...document, document_type: "receipt" }} paper="thermal" />);
    expect(output).toContain("print-document--thermal");
    expect(output).toContain("Come again");
    expect(output).toContain("1,380.00");
  });
});
