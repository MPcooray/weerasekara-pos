import { FormEvent, useState } from "react";
import { CheckCircle2, Save } from "lucide-react";
import { createExamination, finalizeExamination, updateExamination, type Examination, type ExaminationInput, type Visit } from "../../lib/api";

type Props = { customerId: string; visits: Visit[]; examination?: Examination; onSaved: (exam: Examination) => void; onCancel: () => void };
const eyeFields = [
  ["sphere", "SPH", "0.25"], ["cylinder", "CYL", "0.25"], ["axis", "Axis", "1"], ["add", "ADD", "0.25"],
] as const;

export function ExaminationForm({ customerId, visits, examination, onSaved, onCancel }: Props) {
  const [form, setForm] = useState<ExaminationInput>({
    visit_id: examination?.visit_id ?? visits[0]?.id ?? "", examined_at: examination?.examined_at ?? new Date().toISOString(),
    prescription_type: examination?.prescription_type ?? null, expires_on: examination?.expires_on ?? "", notes: examination?.notes ?? "",
    od_sphere: examination?.od_sphere ?? "", od_cylinder: examination?.od_cylinder ?? "", od_axis: examination?.od_axis ?? null, od_add: examination?.od_add ?? "", od_distance_va: examination?.od_distance_va ?? "", od_near_va: examination?.od_near_va ?? "", od_prism: examination?.od_prism ?? "", od_prism_base: examination?.od_prism_base ?? "", od_notes: examination?.od_notes ?? "",
    os_sphere: examination?.os_sphere ?? "", os_cylinder: examination?.os_cylinder ?? "", os_axis: examination?.os_axis ?? null, os_add: examination?.os_add ?? "", os_distance_va: examination?.os_distance_va ?? "", os_near_va: examination?.os_near_va ?? "", os_prism: examination?.os_prism ?? "", os_prism_base: examination?.os_prism_base ?? "", os_notes: examination?.os_notes ?? "",
    pd_binocular: examination?.pd_binocular ?? "", pd_right: examination?.pd_right ?? "", pd_left: examination?.pd_left ?? "",
  });
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const set = (key: keyof ExaminationInput, value: string | number | null) => setForm((current) => ({ ...current, [key]: value }));
  const payload = () => Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value === "" ? null : value])) as ExaminationInput;
  async function save(finalize: boolean) {
    setSaving(true); setError("");
    try {
      let saved: Examination;
      if (examination) saved = await updateExamination(examination.id, examination.version, payload());
      else saved = await createExamination(customerId, payload() as ExaminationInput & { visit_id: string });
      if (finalize) saved = await finalizeExamination(saved.id, saved.version);
      onSaved(saved);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save examination"); }
    finally { setSaving(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); void save(false); }
  if (!visits.length) return <div className="empty compact"><h4>A visit is required</h4><p>Create a customer visit before starting an examination.</p><button className="button" onClick={onCancel}>Close</button></div>;
  return <form className="exam-form" onSubmit={submit}>{error && <div className="alert alert--error" role="alert">{error}</div>}
    <div className="exam-meta"><label>Related visit<select required value={form.visit_id} onChange={(event) => set("visit_id", event.target.value)} disabled={Boolean(examination)}>{visits.map((visit) => <option key={visit.id} value={visit.id}>{new Date(visit.visit_at).toLocaleDateString("en-LK")} · {visit.purpose}</option>)}</select></label><label>Prescription type<select value={form.prescription_type ?? ""} onChange={(event) => set("prescription_type", event.target.value)}><option value="">Select before finalizing</option><option value="distance">Distance</option><option value="near">Near</option><option value="progressive">Progressive</option><option value="occupational">Occupational</option><option value="other">Other</option></select></label><label>Expiration date<input type="date" value={form.expires_on ?? ""} onChange={(event) => set("expires_on", event.target.value)} /></label></div>
    <p className="form-hint">Drafts may be incomplete. Optical powers use 0.25 D steps; no measurement is inferred.</p>
    <div className="eyes-grid">{(["od", "os"] as const).map((eye) => <fieldset className={`eye-card eye-card--${eye}`} key={eye}><legend><span>{eye.toUpperCase()}</span>{eye === "od" ? "Right eye" : "Left eye"}</legend><div className="power-grid">{eyeFields.map(([name, label, step]) => { const key = `${eye}_${name}` as keyof ExaminationInput; return <label key={name}>{label}<input type="number" step={step} min={name === "axis" ? 0 : name === "add" ? 0 : -30} max={name === "axis" ? 180 : name === "add" ? 6 : 30} value={form[key] ?? ""} onChange={(event) => set(key, name === "axis" && event.target.value ? Number(event.target.value) : event.target.value)} placeholder={name === "axis" ? "0–180" : "±0.00"} /></label>; })}</div><div className="eye-details"><label>Distance VA<input value={form[`${eye}_distance_va`] ?? ""} onChange={(event) => set(`${eye}_distance_va`, event.target.value)} placeholder="e.g. 6/6" /></label><label>Near VA<input value={form[`${eye}_near_va`] ?? ""} onChange={(event) => set(`${eye}_near_va`, event.target.value)} placeholder="e.g. N6" /></label><label>Prism<input type="number" step="0.25" min="0" max="20" value={form[`${eye}_prism`] ?? ""} onChange={(event) => set(`${eye}_prism`, event.target.value)} /></label><label>Base<input value={form[`${eye}_prism_base`] ?? ""} onChange={(event) => set(`${eye}_prism_base`, event.target.value)} placeholder="In / Out / Up / Down" /></label></div><label>Clinical notes<textarea rows={2} value={form[`${eye}_notes`] ?? ""} onChange={(event) => set(`${eye}_notes`, event.target.value)} /></label></fieldset>)}</div>
    <div className="pd-grid"><label>Binocular PD (mm)<input type="number" step="0.5" min="20" max="90" value={form.pd_binocular ?? ""} onChange={(event) => set("pd_binocular", event.target.value)} /></label><label>Right monocular PD<input type="number" step="0.5" min="20" max="90" value={form.pd_right ?? ""} onChange={(event) => set("pd_right", event.target.value)} /></label><label>Left monocular PD<input type="number" step="0.5" min="20" max="90" value={form.pd_left ?? ""} onChange={(event) => set("pd_left", event.target.value)} /></label></div>
    <label>Examination notes<textarea rows={3} value={form.notes ?? ""} onChange={(event) => set("notes", event.target.value)} placeholder="Optional overall notes" /></label>
    <div className="form-actions"><button type="button" className="button button--ghost" onClick={onCancel}>Cancel</button><button className="button" disabled={saving}><Save size={17} /> {saving ? "Saving…" : "Save draft"}</button><button type="button" className="button button--primary" disabled={saving} onClick={() => void save(true)}><CheckCircle2 size={17} /> Finalize</button></div>
  </form>;
}
