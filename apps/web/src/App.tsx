import { useEffect, useState } from "react";
import { BarChart3, Boxes, CircleHelp, FileText, Glasses, LogOut, ReceiptText, ShieldCheck, UsersRound, type LucideIcon } from "lucide-react";
import { LoginScreen } from "./features/auth/LoginScreen";
import { PasswordChangeScreen } from "./features/auth/PasswordChangeScreen";
import { CustomerDirectory } from "./features/customers/CustomerDirectory";
import { CustomerProfile } from "./features/customers/CustomerProfile";
import { InventoryWorkspace } from "./features/inventory/InventoryWorkspace";
import { OrderWorkspace } from "./features/orders/OrderWorkspace";
import { PosWorkspace } from "./features/pos/PosWorkspace";
import { QuotationWorkspace } from "./features/pos/QuotationWorkspace";
import { ReportingWorkspace } from "./features/reporting/ReportingWorkspace";
import { StaffWorkspace } from "./features/staff/StaffWorkspace";
import { getBranding, getCurrentUser, hasSession, logout, logoutSession, type User } from "./lib/api";

type Section = "customers" | "inventory" | "pos" | "quotes" | "orders" | "reports" | "staff";
type NavItem = { section: Section; label: string; mobile: string; permission: string; icon: LucideIcon };
const navigation: NavItem[] = [
  { section: "customers", label: "Customers", mobile: "Customers", permission: "customers.view", icon: UsersRound },
  { section: "inventory", label: "Products & stock", mobile: "Stock", permission: "products.view", icon: Boxes },
  { section: "pos", label: "POS & invoices", mobile: "POS", permission: "pos.checkout", icon: ReceiptText },
  { section: "quotes", label: "Quotations", mobile: "Quotes", permission: "quotations.create", icon: FileText },
  { section: "orders", label: "Optical orders", mobile: "Orders", permission: "orders.view", icon: Glasses },
  { section: "reports", label: "Dashboard & reports", mobile: "Reports", permission: "reports.view", icon: BarChart3 },
  { section: "staff", label: "Employees", mobile: "Staff", permission: "staff.manage", icon: ShieldCheck },
];

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
  if (user.must_change_password) return <PasswordChangeScreen onChanged={setUser} />;
  async function signOut() { await logoutSession(); setUser(null); setSelectedCustomer(null); }
  function customers() { setSection("customers"); setSelectedCustomer(null); }
  const allowed = (permission: string) => user.permissions.includes(permission);
  const visibleNavigation = navigation.filter(item => allowed(item.permission));
  const sectionPermission = navigation.find(item => item.section === section)?.permission;
  const content = sectionPermission && !allowed(sectionPermission) ? <div className="content"><div className="alert alert--error">You do not have permission to access this workspace.</div></div> : section === "staff" ? <StaffWorkspace /> : section === "reports" ? <ReportingWorkspace permissions={user.permissions} /> : section === "orders" ? <OrderWorkspace role={user.role} /> : section === "quotes" ? <QuotationWorkspace role={user.role} /> : section === "pos" ? <PosWorkspace role={user.role} /> : section === "inventory" ? <InventoryWorkspace permissions={user.permissions} /> : selectedCustomer ? <CustomerProfile customerId={selectedCustomer} userRole={user.role} onBack={() => setSelectedCustomer(null)} /> : <CustomerDirectory onSelect={setSelectedCustomer} />;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand brand--light"><span className="brand__mark">T</span><span><b>Tetrova</b><small>Optical POS</small></span></div><nav aria-label="Main navigation">{visibleNavigation.map(item => { const Icon = item.icon; return <button key={item.section} className={section === item.section ? "active" : ""} onClick={() => item.section === "customers" ? customers() : setSection(item.section)}><Icon />{item.label}</button>; })}</nav><div className="sidebar__bottom"><button disabled><CircleHelp />Help</button><button onClick={signOut}><LogOut />Sign out</button></div></aside>
    <div className="workspace"><header className="app-header"><button className="mobile-brand" onClick={customers}><span className="brand__mark">T</span></button><div><strong>{businessName}</strong><small>Customer workspace</small></div><div className="user-menu"><span className="avatar">{user.full_name.split(" ").map(part => part[0]).slice(0, 2).join("")}</span><span><b>{user.full_name}</b><small>{user.role}</small></span><button className="mobile-signout" onClick={signOut} aria-label="Sign out"><LogOut /></button></div></header><main>{content}</main></div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{visibleNavigation.map(item => { const Icon = item.icon; return <button key={item.section} className={section === item.section ? "active" : ""} onClick={() => item.section === "customers" ? customers() : setSection(item.section)}><Icon />{item.mobile}</button>; })}</nav>
  </div>;
}
