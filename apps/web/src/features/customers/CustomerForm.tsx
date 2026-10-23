import { FormEvent, useState } from "react";
import { createCustomer, updateCustomer, type Customer, type CustomerInput, type Gender } from "../../lib/api";

export function CustomerForm({ customer, onSaved, onCancel }: { customer?: Customer; onSaved: (customer: Customer, warnings: string[]) => void; onCancel: () => void }) {
  const [form, setForm] = useState<CustomerInput>({ full_name: customer?.full_name ?? "", mobile_number: customer?.mobile_number ?? "", alternative_contact_number: customer?.alternative_contact_number ?? "", date_of_birth: customer?.date_of_birth ?? "", gender: customer?.gender ?? null, address: customer?.address ?? "", email: customer?.email ?? "", notes: customer?.notes ?? "" });
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const set = (key: keyof CustomerInput, value: string) => setForm((current) => ({ ...current, [key]: value || null }));
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setSaving(true);
    try { if (customer) onSaved(await updateCustomer(customer.id, form), []); else { const result = await createCustomer(form); onSaved(result.customer, result.duplicate_warnings); } }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save customer"); } finally { setSaving(false); }
  }
  return <form className="customer-form" onSubmit={submit}>{error && <div className="alert alert--error" role="alert">{error}</div>}<div className="form-grid">
    <label className="span-2">Full name <span>*</span><input required autoFocus value={form.full_name} onChange={(e) => set("full_name", e.target.value)} placeholder="e.g. Nimal Perera" /></label>
    <label>Mobile number <span>*</span><input required value={form.mobile_number} onChange={(e) => set("mobile_number", e.target.value)} placeholder="077 123 4567" inputMode="tel" /></label>
    <label>Alternative contact<input value={form.alternative_contact_number ?? ""} onChange={(e) => set("alternative_contact_number", e.target.value)} placeholder="Optional" inputMode="tel" /></label>
    <label>Date of birth<input type="date" max={new Date().toISOString().slice(0, 10)} value={form.date_of_birth ?? ""} onChange={(e) => set("date_of_birth", e.target.value)} /></label>
    <label>Gender<select value={form.gender ?? ""} onChange={(e) => set("gender", e.target.value as Gender)}><option value="">Not specified</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option><option value="prefer_not_to_say">Prefer not to say</option></select></label>
    <label className="span-2">Email<input type="email" value={form.email ?? ""} onChange={(e) => set("email", e.target.value)} placeholder="Optional" /></label>
    <label className="span-2">Address<textarea rows={2} value={form.address ?? ""} onChange={(e) => set("address", e.target.value)} placeholder="Optional" /></label>
    <label className="span-2">Notes<textarea rows={3} value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} placeholder="Preferences or helpful context (optional)" /></label>
  </div><div className="form-actions"><button type="button" className="button button--ghost" onClick={onCancel}>Cancel</button><button className="button button--primary" disabled={saving}>{saving ? "Saving…" : customer ? "Save changes" : "Register customer"}</button></div></form>;
}
