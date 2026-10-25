import { beforeEach, describe, expect, it, vi } from "vitest";
import { compareExaminations, confirmCheckout, createCustomer, createOrder, createQuotation, getCustomers, getInvoices, login, logoutSession, previewCheckout, recordPayment, recordRefund, transitionOrder } from "./api";

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  });
});

describe("authenticated customer API", () => {
  it("stores the token and loads the signed-in user", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "signed-token" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "1", tenant_id: "2", email: "staff@example.com", full_name: "Staff", role: "owner" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = await login("weerasekara-optics", "staff@example.com", "password");
    expect(user.role).toBe("owner");
    expect(storage.get("tetrova_access_token")).toBe("signed-token");
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Authorization")).toBe("Bearer signed-token");
  });

  it("sends only the supplied customer registration fields", async () => {
    storage.set("tetrova_access_token", "token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ customer: {}, duplicate_warnings: [] }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await createCustomer({ full_name: "Nimal Perera", mobile_number: "0771234567" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({ full_name: "Nimal Perera", mobile_number: "0771234567" });
  });

  it("requests a server-calculated prescription comparison", async () => {
    storage.set("tetrova_access_token", "token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ earlier: {}, later: {}, changes: [], notice: "Numerical differences only" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await compareExaminations("exam-one", "exam-two");
    expect(fetchMock.mock.calls[0][0]).toContain("/examinations/compare/exam-one/exam-two");
    expect(result.notice).toContain("Numerical");
  });

  it("previews and confirms checkout with an idempotency key", async () => {
    storage.set("tetrova_access_token", "token");
    const checkout = {
      invoice_discount_minor: 0,
      lines: [{
        product_id: "product-1",
        quantity: 1,
        line_discount_minor: 0,
        expected_unit_price_minor: 125000,
      }],
    };
    const response = {
      lines: [], subtotal_minor: 125000, discount_minor: 0, tax_minor: 0,
      total_minor: 125000, paid_minor: 0, outstanding_minor: 125000,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(response), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...response, id: "invoice-1", invoice_number: "INV-2026-000001",
        customer_id: null, invoice_at: "2026-10-24T10:00:00Z", status: "finalized",
        location_id: "location-1", examination_id: null, actor_id: "user-1", notes: null,
      }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await previewCheckout(checkout);
    await confirmCheckout(checkout, "stable-checkout-key");

    expect(fetchMock.mock.calls[0][0]).toContain("/checkout/preview");
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Idempotency-Key"))
      .toBe("stable-checkout-key");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(checkout);
  });

  it("loads tenant-scoped invoice history through the authenticated API", async () => {
    storage.set("tetrova_access_token", "token");
    const page = { items: [], page: 1, page_size: 20, total: 0, pages: 1, total_outstanding_minor: 0 };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(page), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await getInvoices({ paymentStatus: "outstanding" })).toEqual(page);
    expect(fetchMock.mock.calls[0][0]).toContain("/invoices");
    expect(fetchMock.mock.calls[0][0]).toContain("payment_status=outstanding");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization"))
      .toBe("Bearer token");
  });

  it("records payments with an idempotency key and no payment credentials", async () => {
    storage.set("tetrova_access_token", "token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ payment: {}, invoice: {} }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await recordPayment("invoice-1", { amount_minor: 100000, method: "card", reference: "TERM-1" }, "payment-key-1");
    const options = fetchMock.mock.calls[0][1];
    expect(new Headers(options.headers).get("Idempotency-Key")).toBe("payment-key-1");
    expect(JSON.parse(options.body)).toEqual({ amount_minor: 100000, method: "card", reference: "TERM-1" });
  });

  it("creates quotation drafts and submits refunds with idempotency", async () => {
    storage.set("tetrova_access_token", "token");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "quote-1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "refund-1" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await createQuotation({ invoice_discount_minor: 0, lines: [{ product_id: "p1", quantity: 1, line_discount_minor: 0 }] });
    await recordRefund("credit-1", { amount_minor: 5000, method: "cash", reason: "Approved return" }, "refund-key-1");
    expect(fetchMock.mock.calls[0][0]).toContain("/quotations");
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Idempotency-Key")).toBe("refund-key-1");
  });

  it("creates and transitions optical orders with persistent idempotency keys", async () => {
    storage.set("tetrova_access_token", "token");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "order-1" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "order-1", status: "confirmed" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await createOrder({ customer_id: "customer-1", examination_id: "exam-1", lens_type: "Progressive", coatings: [] }, "order-create-key");
    await transitionOrder("order-1", "confirmed", 1, "Approved", "order-transition-key");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Idempotency-Key")).toBe("order-create-key");
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("Idempotency-Key")).toBe("order-transition-key");
  });

  it("clears an expired authenticated session on 401", async () => {
    storage.set("tetrova_access_token", "expired-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Session expired" }), { status: 401 }),
    ));
    await expect(getCustomers()).rejects.toThrow("Session expired");
    expect(storage.has("tetrova_access_token")).toBe(false);
  });

  it("turns a browser network failure into an actionable financial warning", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(confirmCheckout({ invoice_discount_minor: 0, lines: [] }, "safe-key"))
      .rejects.toThrow("verify the record before submitting again");
  });

  it("revokes the server token before clearing the local session", async () => {
    storage.set("tetrova_access_token", "active-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await logoutSession();
    expect(fetchMock.mock.calls[0][0]).toContain("/auth/logout");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization"))
      .toBe("Bearer active-token");
    expect(storage.has("tetrova_access_token")).toBe(false);
  });
});
