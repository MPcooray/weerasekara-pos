import { FormEvent, useState } from "react";
import { changePassword, type User } from "../../lib/api";

export function PasswordChangeScreen({onChanged}:{onChanged:(user:User)=>void}){
  const [error,setError]=useState("");const [saving,setSaving]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();setSaving(true);setError("");const data=new FormData(event.currentTarget);const next=String(data.get("new"));if(next!==String(data.get("confirm"))){setError("New passwords do not match");setSaving(false);return;}try{onChanged(await changePassword(String(data.get("current")),next));}catch(reason){setError((reason as Error).message);}finally{setSaving(false);}}
  return <main className="splash"><form className="login-card" onSubmit={submit}><p className="eyebrow">Credential security</p><h2>Choose a new password</h2><p className="muted">Your temporary password must be replaced before accessing customer or business data.</p>{error&&<div className="alert alert--error">{error}</div>}<label>Temporary password<input name="current" type="password" minLength={12} required autoComplete="current-password"/></label><label>New password<input name="new" type="password" minLength={12} required autoComplete="new-password"/></label><label>Confirm new password<input name="confirm" type="password" minLength={12} required autoComplete="new-password"/></label><button className="button button--primary button--wide" disabled={saving}>{saving?"Updating…":"Update password"}</button></form></main>;
}
