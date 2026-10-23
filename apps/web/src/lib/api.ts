export type Health = { status: string; service: string; environment: string };
export type User = { id: string; tenant_id: string; email: string; full_name: string; role: string };
export type Gender = "female" | "male" | "other" | "prefer_not_to_say";
export type VisitStatus = "open" | "in_progress" | "completed" | "cancelled";
export type CustomerInput = { full_name: string; mobile_number: string; alternative_contact_number?: string | null; date_of_birth?: string | null; gender?: Gender | null; address?: string | null; email?: string | null; notes?: string | null };
export type Visit = { id: string; customer_id: string; visit_at: string; purpose: string; assigned_staff_id: string | null; status: VisitStatus; notes: string | null; created_at: string; updated_at: string };
export type Customer = CustomerInput & { id: string; tenant_id: string; customer_number: string; created_by_id: string; is_archived: boolean; created_at: string; updated_at: string; visits?: Visit[] };
export type CustomerPage = { items: Customer[]; page: number; page_size: number; total: number; pages: number };
export type PrescriptionType = "distance" | "near" | "progressive" | "occupational" | "other";
export type ExaminationStatus = "draft" | "finalized";
export type ExaminationInput = {
  visit_id?: string; examined_at?: string; prescription_type?: PrescriptionType | null; expires_on?: string | null; notes?: string | null;
  od_sphere?: string | null; od_cylinder?: string | null; od_axis?: number | null; od_add?: string | null; od_distance_va?: string | null; od_near_va?: string | null; od_prism?: string | null; od_prism_base?: string | null; od_notes?: string | null;
  os_sphere?: string | null; os_cylinder?: string | null; os_axis?: number | null; os_add?: string | null; os_distance_va?: string | null; os_near_va?: string | null; os_prism?: string | null; os_prism_base?: string | null; os_notes?: string | null;
  pd_binocular?: string | null; pd_right?: string | null; pd_left?: string | null;
};
export type Examination = ExaminationInput & {
  id: string; tenant_id: string; examination_number: string; customer_id: string; customer_name: string; visit_id: string; examiner_id: string; examiner_name: string; examined_at: string; status: ExaminationStatus; finalized_at: string | null; supersedes_id: string | null; revision_number: number; version: number; created_at: string; updated_at: string;
};
export type ComparisonChange = { field: string; earlier: string | number | null; later: string | number | null; difference: string | number | null };
export type ExaminationComparison = { earlier: Examination; later: Examination; changes: ComparisonChange[]; notice: string };
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "tetrova_access_token";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
function token() { return sessionStorage.getItem(TOKEN_KEY); }
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (token()) headers.set("Authorization", `Bearer ${token()}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg).join(". ") : body.detail;
    throw new ApiError(response.status, detail || "Something went wrong");
  }
  return body as T;
}
export const getHealth = (signal?: AbortSignal) => request<Health>("/health", { signal });
export async function login(tenant_slug: string, email: string, password: string): Promise<User> {
  const result = await request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ tenant_slug, email, password }) });
  sessionStorage.setItem(TOKEN_KEY, result.access_token);
  return getCurrentUser();
}
export function logout() { sessionStorage.removeItem(TOKEN_KEY); }
export function hasSession() { return Boolean(token()); }
export const getCurrentUser = () => request<User>("/auth/me");
export function getCustomers(search = "", page = 1) { return request<CustomerPage>(`/customers?${new URLSearchParams({ search, page: String(page), page_size: "12" })}`); }
export const getCustomer = (id: string) => request<Customer>(`/customers/${id}`);
export const createCustomer = (data: CustomerInput) => request<{ customer: Customer; duplicate_warnings: string[] }>("/customers", { method: "POST", body: JSON.stringify(data) });
export const updateCustomer = (id: string, data: Partial<CustomerInput>) => request<Customer>(`/customers/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const createVisit = (customerId: string, data: { visit_at: string; purpose: string; status: VisitStatus; notes?: string }) => request<Visit>(`/customers/${customerId}/visits`, { method: "POST", body: JSON.stringify(data) });
export const updateVisit = (customerId: string, visitId: string, data: { status: VisitStatus }) => request<Visit>(`/customers/${customerId}/visits/${visitId}`, { method: "PATCH", body: JSON.stringify(data) });
export const getExaminations = (customerId: string, dateFrom = "", dateTo = "") => request<Examination[]>(`/customers/${customerId}/examinations?${new URLSearchParams({ ...(dateFrom ? { date_from: dateFrom } : {}), ...(dateTo ? { date_to: dateTo } : {}) })}`);
export const createExamination = (customerId: string, data: ExaminationInput & { visit_id: string }) => request<Examination>(`/customers/${customerId}/examinations`, { method: "POST", body: JSON.stringify(data) });
export const updateExamination = (id: string, expectedVersion: number, data: ExaminationInput) => request<Examination>(`/examinations/${id}`, { method: "PATCH", body: JSON.stringify({ ...data, expected_version: expectedVersion }) });
export const finalizeExamination = (id: string, expectedVersion: number) => request<Examination>(`/examinations/${id}/finalize`, { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) });
export const createExaminationRevision = (id: string) => request<Examination>(`/examinations/${id}/revisions`, { method: "POST" });
export const compareExaminations = (earlierId: string, laterId: string) => request<ExaminationComparison>(`/examinations/compare/${earlierId}/${laterId}`);
