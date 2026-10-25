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
export type ProductCategory = "spectacle_frame" | "sunglasses" | "prescription_lens" | "contact_lens" | "accessory" | "optical_service";
export type Product = { id:string; name:string; sku:string; barcode:string|null; category:ProductCategory; brand:string|null; model:string|null; description:string|null; supplier_id:string|null; cost_price_minor:number; selling_price_minor:number; tax_rate:number; tax_inclusive:boolean; tax_exempt:boolean; track_stock:boolean; made_to_order:boolean; reorder_threshold:number; is_archived:boolean; quantity:number; version:number; stock_version:number; created_at:string; updated_at:string };
export type ProductInput = Omit<Product,"id"|"is_archived"|"quantity"|"version"|"stock_version"|"created_at"|"updated_at"|"tax_exempt"|"made_to_order"> & {tax_exempt?:boolean;made_to_order?:boolean};
export type ProductPage = { items:Product[]; page:number; page_size:number; total:number; pages:number };
export type Supplier = { id:string; business_name:string; contact_person:string|null; telephone:string|null; email:string|null; address:string|null; notes:string|null; is_archived:boolean; created_at:string; updated_at:string };
export type SupplierInput = Omit<Supplier,"id"|"is_archived"|"created_at"|"updated_at">;
export type MovementType = "opening_stock"|"stock_received"|"manual_adjustment"|"damaged_stock"|"supplier_return"|"customer_return"|"sale_deduction"|"sale_reversal";
export type StockMovement = { id:string; product_id:string; location_id:string; quantity_delta:number; movement_type:MovementType; reason:string|null; reference:string|null; actor_id:string; balance_after:number; created_at:string };
export type InventorySummary = { active_products:number; tracked_products:number; total_units:number; low_stock_products:number; out_of_stock_products:number; valuation_minor:number; by_category:Record<string,number> };
export type CheckoutLineInput={product_id:string;quantity:number;line_discount_minor:number;expected_unit_price_minor:number};
export type CheckoutInput={customer_id?:string|null;examination_id?:string|null;invoice_discount_minor:number;lines:CheckoutLineInput[];notes?:string|null};
export type CheckoutLine={id?:string|null;product_id:string;product_name:string;sku:string|null;quantity:number;unit_price_minor:number;line_discount_minor:number;invoice_discount_minor:number;tax_rate_bps:number;tax_exempt:boolean;tax_inclusive:boolean;tax_minor:number;line_total_minor:number;stock_available:number|null};
export type CheckoutPreview={lines:CheckoutLine[];subtotal_minor:number;discount_minor:number;tax_minor:number;total_minor:number;paid_minor:number;outstanding_minor:number};
export type InvoiceSummary={id:string;invoice_number:string;customer_id:string|null;invoice_at:string;status:string;total_minor:number;paid_minor:number;outstanding_minor:number;credited_minor:number;refunded_minor:number;refundable_minor:number};
export type PaymentMethod="cash"|"card"|"bank_transfer";
export type Payment={id:string;invoice_id:string;amount_minor:number;method:PaymentMethod;reference:string|null;paid_at:string;actor_id:string;created_at:string};
export type InvoiceDetail=InvoiceSummary&{location_id:string;examination_id:string|null;actor_id:string;subtotal_minor:number;discount_minor:number;tax_minor:number;notes:string|null;lines:CheckoutLine[];payments:Payment[]};
export type InvoicePage={items:InvoiceSummary[];page:number;page_size:number;total:number;pages:number;total_outstanding_minor:number};
export type PaymentResult={payment:Payment;invoice:InvoiceSummary};
export type QuotationLineInput={product_id:string;quantity:number;line_discount_minor:number};
export type QuotationInput={customer_id?:string|null;examination_id?:string|null;expires_on?:string|null;invoice_discount_minor:number;notes?:string|null;lines:QuotationLineInput[]};
export type Quotation={id:string;quotation_number:string;customer_id:string|null;examination_id:string|null;status:string;expires_on:string|null;subtotal_minor:number;discount_minor:number;tax_minor:number;total_minor:number;converted_invoice_id:string|null;issued_at:string|null;notes:string|null;created_at:string;updated_at:string;lines:Array<QuotationLineInput&{id:string;product_name:string;sku:string|null;unit_price_minor:number;invoice_discount_minor:number;tax_minor:number;line_total_minor:number}>};
export type QuotationPage={items:Quotation[];page:number;page_size:number;total:number;pages:number};
export type ReturnRecord={id:string;invoice_id:string;return_number:string;status:string;reason:string;total_minor:number;finalized_at:string|null;created_at:string;credit_note_id:string|null;lines:Array<{id:string;invoice_line_id:string;quantity:number;amount_minor:number;restock:boolean}>};
export type CreditNote={id:string;invoice_id:string;return_id:string|null;credit_note_number:string;status:string;reason:string;total_minor:number;issued_at:string|null;lines:Array<{description:string;quantity:number;subtotal_minor:number;discount_minor:number;tax_minor:number;amount_minor:number}>};
export type Refund={id:string;invoice_id:string;credit_note_id:string;amount_minor:number;method:PaymentMethod;reason:string;reference:string|null;actor_id:string;refunded_at:string};
export type Branding={business_display_name:string;business_address:string|null;business_contact:string|null;logo_url:string|null;invoice_footer:string|null;receipt_footer:string|null;business_registration:string|null;tax_registration:string|null;default_currency:string};
export type NamedAmount={name:string;amount_minor:number;quantity:number};
export type TrendPoint={date:string;invoiced_minor:number;payments_minor:number};
export type FinancialReport={date_from:string;date_to:string;timezone:string;invoiced_sales_minor:number;payments_received_minor:number;refunds_minor:number;outstanding_minor:number;credit_notes_minor:number;discounts_minor:number;tax_minor:number;payment_methods:NamedAmount[];top_products:NamedAmount[];sales_by_staff:NamedAmount[];trend:TrendPoint[]};
export type Dashboard={today_invoiced_minor:number;today_payments_minor:number;outstanding_minor:number;today_refunds_minor:number;pending_quotations:number;low_stock_products:number;recent_transactions:Array<{kind:string;reference:string;amount_minor:number;occurred_at:string}>;trend:TrendPoint[]};
export type PrintDocument={document_type:string;document_id:string;document_number:string;occurred_at:string;status:string;customer_name:string|null;related_number:string|null;payment_method:string|null;external_reference:string|null;reason:string|null;subtotal_minor:number;discount_minor:number;tax_minor:number;total_minor:number;paid_minor:number;outstanding_minor:number;lines:Array<{description:string;sku:string|null;quantity:number;unit_price_minor:number;discount_minor:number;tax_minor:number;total_minor:number}>;branding:Branding};
export type OrderStatus="draft"|"confirmed"|"awaiting_lenses"|"in_preparation"|"quality_check"|"ready_for_collection"|"collected"|"cancelled";
export type OrderInput={customer_id:string;visit_id?:string|null;examination_id:string;invoice_id?:string|null;frame_product_id?:string|null;frame_details?:string|null;lens_type:string;lens_material?:string|null;refractive_index?:string|null;coatings:string[];tint?:string|null;right_lens_details?:string|null;left_lens_details?:string|null;fitting_instructions?:string|null;expected_collection_date?:string|null;internal_notes?:string|null;assigned_staff_id?:string|null};
export type OpticalOrder={id:string;order_number:string;customer_id:string;visit_id:string|null;examination_id:string;invoice_id:string|null;frame_product_id:string|null;assigned_staff_id:string|null;status:OrderStatus;expected_collection_date:string|null;overdue:boolean;outstanding_minor:number;frame_snapshot:Record<string,unknown>|null;prescription_snapshot:Record<string,unknown>;lens_type:string;lens_material:string|null;refractive_index:string|null;coatings:string[];tint:string|null;right_lens_details:string|null;left_lens_details:string|null;fitting_instructions:string|null;internal_notes:string|null;created_at:string;updated_at:string;version:number;events:Array<{id:string;from_status:string|null;to_status:string;actor_id:string;reason:string|null;created_at:string}>;supplier_order:{id:string;supplier_id:string;supplier_reference:string|null;ordered_on:string|null;expected_delivery:string|null;received_on:string|null;status:string;notes:string|null;version:number}|null;quality_check:{id:string;prescription_verified:boolean;lenses_inspected:boolean;frame_inspected:boolean;fitting_confirmed:boolean;remarks:string|null;actor_id:string;checked_at:string}|null;collection:{id:string;actor_id:string;collected_at:string;notes:string|null;outstanding_minor_at_collection:number;outstanding_override:boolean}|null};
export type OrderPage={items:OpticalOrder[];page:number;page_size:number;total:number;pages:number};
export type StaffOption={id:string;full_name:string;role:string};
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "tetrova_access_token";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
function token() { return sessionStorage.getItem(TOKEN_KEY); }
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (token()) headers.set("Authorization", `Bearer ${token()}`);
  const controller = options.signal ? null : new AbortController();
  const timeout = controller ? globalThis.setTimeout(() => controller.abort(), 15000) : null;
  try {
    const response = await fetch(`${API_URL}${path}`, { ...options, headers, signal: options.signal ?? controller?.signal });
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && token()) {
        sessionStorage.removeItem(TOKEN_KEY);
        if (typeof window !== "undefined") window.dispatchEvent(new Event("tetrova:session-expired"));
      }
      const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg).join(". ") : body.detail;
      throw new ApiError(response.status, detail || "Something went wrong");
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new ApiError(0, "The server took too long to respond. Please try again.");
    throw new ApiError(0, "Cannot reach the server. Check the connection and try again. For payments, refunds, or checkout, verify the record before submitting again.");
  } finally {
    if (timeout !== null) globalThis.clearTimeout(timeout);
  }
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
export function getProducts(search="", page=1){ return request<ProductPage>(`/products?${new URLSearchParams({search,page:String(page),page_size:"20"})}`); }
export const createProduct=(data:ProductInput)=>request<Product>("/products",{method:"POST",body:JSON.stringify(data)});
export const updateProduct=(id:string,data:Partial<ProductInput>&{is_archived?:boolean})=>request<Product>(`/products/${id}`,{method:"PATCH",body:JSON.stringify(data)});
export const getSuppliers=()=>request<Supplier[]>("/suppliers");
export const createSupplier=(data:SupplierInput)=>request<Supplier>("/suppliers",{method:"POST",body:JSON.stringify(data)});
export const updateSupplier=(id:string,data:Partial<SupplierInput>&{is_archived?:boolean})=>request<Supplier>(`/suppliers/${id}`,{method:"PATCH",body:JSON.stringify(data)});
export const getInventorySummary=()=>request<InventorySummary>("/inventory/summary");
export const getMovements=(id:string)=>request<StockMovement[]>(`/products/${id}/movements`);
export const createMovement=(id:string,data:{quantity_delta:number;movement_type:MovementType;reason?:string;reference?:string;expected_version:number})=>request<StockMovement>(`/products/${id}/movements`,{method:"POST",body:JSON.stringify(data)});
export const previewCheckout=(data:CheckoutInput)=>request<CheckoutPreview>("/checkout/preview",{method:"POST",body:JSON.stringify(data)});
export const confirmCheckout=(data:CheckoutInput,key:string)=>request<InvoiceDetail>("/checkout/confirm",{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(data)});
export const getInvoices=(options:{search?:string;customerId?:string;paymentStatus?:string;page?:number}={})=>request<InvoicePage>(`/invoices?${new URLSearchParams({search:options.search??"",payment_status:options.paymentStatus??"all",page:String(options.page??1),page_size:"20",...(options.customerId?{customer_id:options.customerId}:{})})}`);
export const getInvoice=(id:string)=>request<InvoiceDetail>(`/invoices/${id}`);
export const recordPayment=(invoiceId:string,data:{amount_minor:number;method:PaymentMethod;reference?:string|null},key:string)=>request<PaymentResult>(`/invoices/${invoiceId}/payments`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(data)});
export const getQuotations=(search="",page=1)=>request<QuotationPage>(`/quotations?${new URLSearchParams({search,page:String(page),page_size:"20"})}`);
export const createQuotation=(data:QuotationInput)=>request<Quotation>("/quotations",{method:"POST",body:JSON.stringify(data)});
export const updateQuotation=(id:string,data:QuotationInput)=>request<Quotation>(`/quotations/${id}`,{method:"PUT",body:JSON.stringify(data)});
export const issueQuotation=(id:string,key:string)=>request<Quotation>(`/quotations/${id}/issue`,{method:"POST",headers:{"Idempotency-Key":key}});
export const conversionPreview=(id:string)=>request<{changed:boolean;differences:string[];current_total_minor:number;quoted_total_minor:number}>(`/quotations/${id}/conversion-preview`);
export const convertQuotation=(id:string,approve_changes:boolean,key:string)=>request<InvoiceDetail>(`/quotations/${id}/convert`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify({approve_changes})});
export const getReturns=(invoiceId:string)=>request<ReturnRecord[]>(`/invoices/${invoiceId}/returns`);
export const createReturn=(invoiceId:string,data:{reason:string;lines:Array<{invoice_line_id:string;quantity:number;restock:boolean}>},key:string)=>request<ReturnRecord>(`/invoices/${invoiceId}/returns`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(data)});
export const approveReturn=(id:string,key:string)=>request<ReturnRecord>(`/returns/${id}/approve`,{method:"POST",headers:{"Idempotency-Key":key}});
export const getCreditNote=(id:string)=>request<CreditNote>(`/credit-notes/${id}`);
export const recordRefund=(id:string,data:{amount_minor:number;method:PaymentMethod;reason:string;reference?:string|null},key:string)=>request<Refund>(`/credit-notes/${id}/refunds`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(data)});
export const getBranding=()=>request<Branding>("/tenant/branding");
export const updateBranding=(data:Partial<Branding>)=>request<Branding>("/tenant/branding",{method:"PATCH",body:JSON.stringify(data)});
export const getFinancialReport=(dateFrom:string,dateTo:string)=>request<FinancialReport>(`/reports/financial?${new URLSearchParams({date_from:dateFrom,date_to:dateTo})}`);
export const getDashboard=()=>request<Dashboard>("/dashboard");
export const getPrintDocument=(type:string,id:string)=>request<PrintDocument>(`/print-documents/${type}/${id}`);
export async function downloadFinancialCsv(dateFrom:string,dateTo:string){const response=await fetch(`${API_URL}/reports/financial.csv?${new URLSearchParams({date_from:dateFrom,date_to:dateTo})}`,{headers:{Authorization:`Bearer ${token()}`}});if(!response.ok)throw new ApiError(response.status,"CSV export failed");const blob=await response.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=`financial-${dateFrom}-${dateTo}.csv`;anchor.click();URL.revokeObjectURL(url);}
export const getOrders=(options:{search?:string;status?:string;overdue?:boolean;ready?:boolean;assignedStaffId?:string;page?:number}={})=>request<OrderPage>(`/orders?${new URLSearchParams({search:options.search??"",...(options.status?{status:options.status}:{}),...(options.overdue?{overdue:"true"}:{}),...(options.ready?{ready:"true"}:{}),...(options.assignedStaffId?{assigned_staff_id:options.assignedStaffId}:{}),page:String(options.page??1),page_size:"20"})}`);
export const getOrder=(id:string)=>request<OpticalOrder>(`/orders/${id}`);
export const createOrder=(data:OrderInput,key:string)=>request<OpticalOrder>("/orders",{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify(data)});
export const updateOrder=(id:string,data:OrderInput,version:number)=>request<OpticalOrder>(`/orders/${id}`,{method:"PUT",body:JSON.stringify({...data,expected_version:version})});
export const transitionOrder=(id:string,status:OrderStatus,version:number,reason:string,key:string)=>request<OpticalOrder>(`/orders/${id}/transitions`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify({status,expected_version:version,reason:reason||null})});
export const updateOrderSupplier=(id:string,data:{supplier_id:string;supplier_reference?:string|null;ordered_on?:string|null;expected_delivery?:string|null;received_on?:string|null;status:string;notes?:string|null;expected_version?:number|null})=>request(`/orders/${id}/supplier`,{method:"PUT",body:JSON.stringify(data)});
export const recordOrderQuality=(id:string,data:{prescription_verified:boolean;lenses_inspected:boolean;frame_inspected:boolean;fitting_confirmed:boolean;remarks?:string|null})=>request(`/orders/${id}/quality-check`,{method:"POST",body:JSON.stringify(data)});
export const collectOrder=(id:string,version:number,allow:boolean,notes:string,key:string)=>request<OpticalOrder>(`/orders/${id}/collect`,{method:"POST",headers:{"Idempotency-Key":key},body:JSON.stringify({expected_version:version,allow_outstanding_balance:allow,notes:notes||null})});
export const getOrderStaff=()=>request<StaffOption[]>("/orders/staff/options");
