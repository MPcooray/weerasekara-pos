import { useEffect, useState } from "react";
import { Boxes, CircleHelp, LogOut, ReceiptText, Search, Settings, UsersRound } from "lucide-react";
import { LoginScreen } from "./features/auth/LoginScreen";
import { CustomerDirectory } from "./features/customers/CustomerDirectory";
import { CustomerProfile } from "./features/customers/CustomerProfile";
import { InventoryWorkspace } from "./features/inventory/InventoryWorkspace";
import { PosWorkspace } from "./features/pos/PosWorkspace";
import { getCurrentUser, hasSession, logout, type User } from "./lib/api";

export function App() {
  const [user, setUser] = useState<User | null>(null); const [checking, setChecking] = useState(hasSession()); const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null); const [section,setSection]=useState<"customers"|"inventory"|"pos">("customers");
  useEffect(() => { if (!hasSession()) return; getCurrentUser().then(setUser).catch(logout).finally(() => setChecking(false)); }, []);
  if (checking) return <main className="splash"><div className="brand__mark">T</div><div className="spinner" /><p>Opening your workspace…</p></main>;
  if (!user) return <LoginScreen onAuthenticated={setUser} />;
  function signOut() { logout(); setUser(null); setSelectedCustomer(null); }
  return <div className="app-shell"><aside className="sidebar"><div className="brand brand--light"><span className="brand__mark">T</span><span><b>Tetrova</b><small>Optical POS</small></span></div><nav aria-label="Main navigation"><button className={section==="customers"?"active":""} onClick={()=>{setSection("customers");setSelectedCustomer(null)}}><UsersRound /> Customers</button><button className={section==="inventory"?"active":""} onClick={()=>setSection("inventory")}><Boxes/>Products & stock</button><button className={section==="pos"?"active":""} onClick={()=>setSection("pos")}><ReceiptText/>POS & invoices</button><button disabled><Search /> Orders <small>Soon</small></button></nav><div className="sidebar__bottom"><button disabled><CircleHelp /> Help</button><button disabled><Settings /> Settings</button><button onClick={signOut}><LogOut /> Sign out</button></div></aside>
    <div className="workspace"><header className="app-header"><button className="mobile-brand" onClick={() => setSelectedCustomer(null)}><span className="brand__mark">T</span></button><div><strong>Weerasekara Optics</strong><small>Customer workspace</small></div><div className="user-menu"><span className="avatar">{user.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</span><span><b>{user.full_name}</b><small>{user.role}</small></span><button className="mobile-signout" onClick={signOut} aria-label="Sign out"><LogOut /></button></div></header>
      <main>{section==="pos"?<PosWorkspace role={user.role}/>:section==="inventory"?<InventoryWorkspace role={user.role}/>:selectedCustomer ? <CustomerProfile customerId={selectedCustomer} userRole={user.role} onBack={() => setSelectedCustomer(null)} /> : <CustomerDirectory onSelect={setSelectedCustomer} />}</main>
    </div><nav className="mobile-nav"><button className={section==="customers"?"active":""} onClick={() => {setSection("customers");setSelectedCustomer(null)}}><UsersRound />Customers</button><button className={section==="inventory"?"active":""} onClick={()=>setSection("inventory")}><Boxes/>Stock</button><button className={section==="pos"?"active":""} onClick={()=>setSection("pos")}><ReceiptText/>POS</button><button onClick={signOut}><LogOut />Sign out</button></nav>
  </div>;
}
