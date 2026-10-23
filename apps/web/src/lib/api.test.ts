import { beforeEach, describe, expect, it, vi } from "vitest";
import { compareExaminations, createCustomer, login } from "./api";

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
});
