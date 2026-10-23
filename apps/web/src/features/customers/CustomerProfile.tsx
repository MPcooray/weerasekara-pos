import { useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, Mail, MapPin, Pencil, Phone, Plus, UserRound } from "lucide-react";
import { getCustomer, updateVisit, type Customer, type Visit } from "../../lib/api";
import { Modal } from "../../components/ui/Modal";
import { CustomerForm } from "./CustomerForm";
import { VisitForm } from "./VisitForm";
import { ExaminationPanel } from "../examinations/ExaminationPanel";

const statusLabel = (value: string) => value.replace("_", " ");
export function CustomerProfile({ customerId, onBack, userRole }: { customerId: string; onBack: () => void; userRole: string }) {
  const [customer, setCustomer] = useState<Customer | null>(null); const [error, setError] = useState(""); const [dialog, setDialog] = useState<"edit" | "visit" | null>(null); const [notice, setNotice] = useState("");
  useEffect(() => { getCustomer(customerId).then(setCustomer).catch((reason) => setError(reason.message)); }, [customerId]);
  if (error) return <div className="state-card"><h2>Couldn’t load this customer</h2><p>{error}</p><button className="button" onClick={onBack}>Back to customers</button></div>;
  if (!customer) return <div className="state-card"><div className="spinner" /><p>Loading customer profile…</p></div>;
  const visits = customer.visits ?? [];
  function visitSaved(visit: Visit) { setCustomer((current) => current ? { ...current, visits: [visit, ...(current.visits ?? [])] } : current); setDialog(null); setNotice("Visit created successfully"); }
  async function completeVisit(visit: Visit) {
    try {
      const saved = await updateVisit(customerId, visit.id, { status: "completed" });
      setCustomer((current) => current ? { ...current, visits: current.visits?.map((item) => item.id === saved.id ? saved : item) } : current);
      setNotice("Visit marked as completed");
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Unable to update visit"); }
  }
  return <div className="content"><button className="back-button" onClick={onBack}><ArrowLeft size={18} /> Customer directory</button>{notice && <div className="alert alert--success" role="status">{notice}</div>}
    <section className="profile-hero"><div className="avatar avatar--large">{customer.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><div className="profile-title"><p className="eyebrow">{customer.customer_number}</p><h2>{customer.full_name}</h2><p>Customer since {new Date(customer.created_at).toLocaleDateString("en-LK", { dateStyle: "medium" })}</p></div><div className="profile-actions"><button className="button button--ghost" onClick={() => setDialog("edit")}><Pencil size={17} /> Edit</button><button className="button button--primary" onClick={() => setDialog("visit")}><Plus size={17} /> New visit</button></div></section>
    <div className="profile-grid"><section className="panel"><header><div><p className="eyebrow">Customer profile</p><h3>Contact & personal details</h3></div></header><dl className="detail-list"><div><dt><Phone /> Mobile</dt><dd>{customer.mobile_number}</dd></div><div><dt><Phone /> Alternative</dt><dd>{customer.alternative_contact_number || "Not provided"}</dd></div><div><dt><Mail /> Email</dt><dd>{customer.email || "Not provided"}</dd></div><div><dt><CalendarDays /> Date of birth</dt><dd>{customer.date_of_birth ? new Date(`${customer.date_of_birth}T00:00:00`).toLocaleDateString("en-LK", { dateStyle: "long" }) : "Not provided"}</dd></div><div><dt><UserRound /> Gender</dt><dd>{customer.gender ? statusLabel(customer.gender) : "Not specified"}</dd></div><div><dt><MapPin /> Address</dt><dd>{customer.address || "Not provided"}</dd></div></dl>{customer.notes && <div className="notes-box"><span>Customer notes</span><p>{customer.notes}</p></div>}</section>
      <section className="panel"><header><div><p className="eyebrow">Care journey</p><h3>Visit history</h3></div><span className="count-pill">{visits.length} visits</span></header>{visits.length === 0 ? <div className="empty compact"><CalendarDays /><h4>No visits yet</h4><p>Create the first visit when this customer arrives.</p><button className="button button--small" onClick={() => setDialog("visit")}>Create visit</button></div> : <div className="timeline">{visits.map((visit) => <article key={visit.id}><span className="timeline__dot" /><div className="timeline__top"><strong>{visit.purpose}</strong><span className={`status status--${visit.status}`}>{statusLabel(visit.status)}</span></div><time>{new Date(visit.visit_at).toLocaleString("en-LK", { dateStyle: "medium", timeStyle: "short" })}</time>{visit.notes && <p>{visit.notes}</p>}{visit.status !== "completed" && visit.status !== "cancelled" ? <button className="timeline__action" onClick={() => completeVisit(visit)}>Mark completed</button> : null}</article>)}</div>}</section></div>
    <ExaminationPanel customerId={customer.id} visits={visits} userRole={userRole} />
    {dialog === "edit" && <Modal title="Edit customer" onClose={() => setDialog(null)} wide><CustomerForm customer={customer} onCancel={() => setDialog(null)} onSaved={(saved) => { setCustomer((current) => ({ ...current!, ...saved })); setDialog(null); setNotice("Customer details updated"); }} /></Modal>}
    {dialog === "visit" && <Modal title="Create a visit" onClose={() => setDialog(null)}><VisitForm customerId={customer.id} onCancel={() => setDialog(null)} onSaved={visitSaved} /></Modal>}
  </div>;
}
