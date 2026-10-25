import { useEffect, useState } from "react";
import { BarChart3, Boxes, CircleHelp, FileText, Glasses, LogOut, ReceiptText, Settings, UsersRound } from "lucide-react";
import { LoginScreen } from "./features/auth/LoginScreen";
import { CustomerDirectory } from "./features/customers/CustomerDirectory";
import { CustomerProfile } from "./features/customers/CustomerProfile";
import { InventoryWorkspace } from "./features/inventory/InventoryWorkspace";
import { OrderWorkspace } from "./features/orders/OrderWorkspace";
import { PosWorkspace } from "./features/pos/PosWorkspace";
import { QuotationWorkspace } from "./features/pos/QuotationWorkspace";
import { ReportingWorkspace } from "./features/reporting/ReportingWorkspace";
import { getBranding, getCurrentUser, hasSession, logout, type User } from "./lib/api";

type Section = "customers" | "inventory" | "pos" | "quotes" | "orders" | "reports";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(hasSession());
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("customers");
  const [businessName, setBusinessName] = useState("Weerasekara Optics");
  useEffect(() => { if (!hasSession()) return; getCurrentUser().then(setUser).catch(logout).finally(() => setChecking(false)); }, []);
  useEffect(() => { const expired = () => { setUser(null); setSelectedCustomer(null); }; window.addEventListener("tetrova:session-expired", expired); return () => window.removeEventListener("tetrova:session-expired", expired); }, []);
  useEffect(() => { if (user) getBranding().then(x => setBusinessName(x.business_display_name)).catch(() => undefined); }, [user]);
  if (checking) return <main className="splash"><div className="brand__mark">T</div><div className="spinner" /><p>Opening your workspace…</p></main>;
  if (!user) return <LoginScreen onAuthenticated={setUser} />;
  function signOut() { logout(); setUser(null); setSelectedCustomer(null); }
  function customers() { setSection("customers"); setSelectedCustomer(null); }
  const canReport = user.role === "owner" || user.role === "manager";
  const content = section === "reports" ? <ReportingWorkspace /> : section === "orders" ? <OrderWorkspace role={user.role} /> : section === "quotes" ? <QuotationWorkspace role={user.role} /> : section === "pos" ? <PosWorkspace role={user.role} /> : section === "inventory" ? <InventoryWorkspace role={user.role} /> : selectedCustomer ? <CustomerProfile customerId={selectedCustomer} userRole={user.role} onBack={() => setSelectedCustomer(null)} /> : <CustomerDirectory onSelect={setSelectedCustomer} />;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand brand--light"><span className="brand__mark">T</span><span><b>Tetrova</b><small>Optical POS</small></span></div><nav aria-label="Main navigation"><button className={section === "customers" ? "active" : ""} onClick={customers}><UsersRound />Customers</button><button className={section === "inventory" ? "active" : ""} onClick={() => setSection("inventory")}><Boxes />Products & stock</button><button className={section === "pos" ? "active" : ""} onClick={() => setSection("pos")}><ReceiptText />POS & invoices</button><button className={section === "quotes" ? "active" : ""} onClick={() => setSection("quotes")}><FileText />Quotations</button><button className={section === "orders" ? "active" : ""} onClick={() => setSection("orders")}><Glasses />Optical orders</button>{canReport && <button className={section === "reports" ? "active" : ""} onClick={() => setSection("reports")}><BarChart3 />Dashboard & reports</button>}</nav><div className="sidebar__bottom"><button disabled><CircleHelp />Help</button><button disabled><Settings />Settings</button><button onClick={signOut}><LogOut />Sign out</button></div></aside>
    <div className="workspace"><header className="app-header"><button className="mobile-brand" onClick={customers}><span className="brand__mark">T</span></button><div><strong>{businessName}</strong><small>Customer workspace</small></div><div className="user-menu"><span className="avatar">{user.full_name.split(" ").map(part => part[0]).slice(0, 2).join("")}</span><span><b>{user.full_name}</b><small>{user.role}</small></span><button className="mobile-signout" onClick={signOut} aria-label="Sign out"><LogOut /></button></div></header><main>{content}</main></div>
    <nav className="mobile-nav" aria-label="Mobile navigation"><button className={section === "customers" ? "active" : ""} onClick={customers}><UsersRound />Customers</button><button className={section === "inventory" ? "active" : ""} onClick={() => setSection("inventory")}><Boxes />Stock</button><button className={section === "pos" ? "active" : ""} onClick={() => setSection("pos")}><ReceiptText />POS</button><button className={section === "quotes" ? "active" : ""} onClick={() => setSection("quotes")}><FileText />Quotes</button><button className={section === "orders" ? "active" : ""} onClick={() => setSection("orders")}><Glasses />Orders</button>{canReport && <button className={section === "reports" ? "active" : ""} onClick={() => setSection("reports")}><BarChart3 />Reports</button>}</nav>
  </div>;
}
