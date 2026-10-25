import { Children, FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { configuredApiOrigin, hasConfiguredApiOrigin } from '../api/config';
import { ApiError, request } from '../api/client';
import { Account, clearSession, hasPermission, readSession, saveSession, Session, signIn, signOut, verifySession } from '../auth/session';
import { filterIncidents } from '../features/incidents/filter';
import logoUrl from '../../../assets/brand/official-logo.svg';

type Row = Record<string, any>;
type Page = 'overview'|'incidents'|'responders'|'users'|'resources'|'reports'|'audit'|'coadmins'|'notifications'|'automation';
const labels: Record<Page,string> = { overview:'Overview', incidents:'Incident queue', responders:'Responders', users:'User accounts', resources:'Resources', reports:'Reports & analytics', audit:'Audit history', coadmins:'Co-Admins', notifications:'Notifications', automation:'Automation policy' };
const permissions: [string,string][] = [['view_dashboard','Dashboard'],['view_incidents','Incidents'],['update_incidents','Update incidents'],['assign_responders','Assign responders'],['manage_responders','Manage responders'],['manage_users','Manage users'],['manage_resources','Manage resources'],['view_reports','View reports'],['export_reports','Export reports'],['view_audit_logs','View audit logs']];
const statuses = ['Unassigned','Assigned','Accepted','En Route','On Scene','Resolved','Cancelled'];
const activeIncident = (x: Row) => !['Resolved','Cancelled'].includes(x.status);
const stamp = (x?: string) => x ? new Date(x).toLocaleString() : '—';
const failText = (error: unknown) => error instanceof Error ? error.message : 'The request failed.';

function Button({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) { return <button {...props}>{children}</button>; }
function Panel({ title, subtitle, action, children }: { title:string; subtitle?:string; action?:React.ReactNode; children:React.ReactNode }) { return <section className="panel"><header className="panel-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</header>{children}</section>; }
function Table({ headers, children }: {headers:string[];children:React.ReactNode}) { return <div className="table-wrap"><table><thead><tr>{headers.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{Children.toArray(children)}</tbody></table></div>; }
function Empty({ children='No records found.' }: {children?:React.ReactNode}) { return <div className="empty">{children}</div>; }

export function Dashboard() {
  const [origin, setOrigin] = useState('');
  const [session, setSession] = useState<Session|null>(null);
  const [page, setPage] = useState<Page>('overview');
  const [data, setData] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [directoryQuery, setDirectoryQuery] = useState('');
  const [directoryStatus, setDirectoryStatus] = useState('');
  const [dialog, setDialog] = useState<{ title:string; kind:string; row:Row }|null>(null);
  const configuration = useMemo(() => { try { return { origin: configuredApiOrigin(), error: '' }; } catch (e) { return { origin: '', error: hasConfiguredApiOrigin() ? failText(e) : '' }; } }, []);
  const configured = configuration.origin;
  const can = useCallback((permission: string) => !!session && hasPermission(session.account, permission), [session]);
  const api = useCallback(<T,>(path:string, options: Parameters<typeof request>[2] = {}) => {
    if (!session) throw new Error('Sign in to continue.');
    return request<T>(session.origin, path, { ...options, token: session.token });
  }, [session]);
  const run = useCallback(async (path:Page = page) => {
    if (!session) return;
    setBusy(true); setError('');
    try {
      let result: any;
      switch (path) {
        case 'overview': result = await api('/admin/dashboard'); setData([result]); break;
        case 'incidents': result = await api<Row[]>('/incidents'); setData(result); break;
        case 'responders': result = await api<Row[]>('/admin/responders'); setData(result); break;
        case 'users': result = await api<Row[]>('/admin/users?role=user'); setData(result); break;
        case 'resources': result = await api<Row[]>('/admin/resources'); setData(result); break;
        case 'reports': result = await api<Row>(`/admin/analytics?days=30`); setData([result]); break;
        case 'audit': result = await api<Row[]>('/admin/audit?limit=100'); setData(result); break;
        case 'coadmins': result = await api<Row[]>('/admin/coadmins'); setData(result); break;
        case 'notifications': result = await api<Row[]>('/notifications'); setData(result); break;
        case 'automation': result = await api<Row>('/admin/automation'); setData([result]); break;
      }
    } catch (e) { if (e instanceof ApiError && e.status === 401) { clearSession(); setSession(null); setError('Your admin session expired or was revoked. Sign in again.'); } else setError(failText(e)); }
    finally { setBusy(false); }
  }, [api, page, session]);
  useEffect(() => {
    const saved = readSession();
    if (!saved) return;
    if (configured && saved.origin !== configured) { clearSession(); setError('Saved session belongs to a different API origin. Sign in again.'); return; }
    verifySession(saved).then(valid => { setSession(valid); saveSession(valid); }).catch(() => { clearSession(); setError('Saved session could not be verified. Please sign in again.'); });
  }, [configured]);
  useEffect(() => { if (session) void run(page); }, [session, page, run]);
  const tell = (message:string) => { setNotice(message); window.setTimeout(() => setNotice(''), 5000); };
  const doLogin = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      const apiOrigin = configured || (form.get('origin') as string).trim().replace(/\/$/, '');
      const validOrigin = configuredApiOriginForLogin(apiOrigin);
      const next = await signIn(validOrigin, String(form.get('email')), String(form.get('password')));
      saveSession(next); setSession(next); setPage('overview');
    } catch (e) { setError(failText(e)); }
    finally { setBusy(false); }
  };
  const logout = async () => { if (session) await signOut(session); setSession(null); setData([]); setError(''); setPage('overview'); };
  const act = async (path:string, options:Parameters<typeof request>[2], success:string, reload = page) => {
    try { const result = await api<Row>(path, options); setDialog(null); tell(result?.activation_url ? `${success} ${result.activation_url} (expires ${stamp(result.expires_at)}).` : success); await run(reload); }
    catch(e) { if(e instanceof ApiError && e.status===401){clearSession();setSession(null);setError('Your admin session expired or was revoked. Sign in again.');}else setError(failText(e)); }
  };
  const filtered = useMemo(() => filterIncidents(data, { query:search, status:statusFilter, priority:priorityFilter, category:categoryFilter }), [data, search, statusFilter, priorityFilter, categoryFilter]);
  const filteredResponders = useMemo(() => data.filter(r => {
    const busy = Boolean(r.active_incident_id), available = Boolean(r.active && r.available && !busy);
    const stateMatch = !directoryStatus || (directoryStatus==='available'?available:directoryStatus==='busy'?busy:directoryStatus==='invited'?r.invitation_status==='pending':!r.active||!r.available);
    const text = `${r.display_name||''} ${r.email||''} ${(r.capabilities||[]).join(' ')} ${r.active_incident_reference||''} ${r.active_resource_name||''}`.toLowerCase();
    return stateMatch && (!directoryQuery || text.includes(directoryQuery.toLowerCase()));
  }), [data,directoryQuery,directoryStatus]);
  const filteredUsers = useMemo(() => data.filter(u => (!directoryStatus || (directoryStatus==='active'?u.active:!u.active)) && (!directoryQuery || `${u.display_name} ${u.email}`.toLowerCase().includes(directoryQuery.toLowerCase()))), [data,directoryQuery,directoryStatus]);
  const open = (title:string, kind:string, row:Row = {}) => { setError(''); setDialog({title,kind,row}); };
  useEffect(() => {
    if (!dialog) return;
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () => Array.from(document.querySelectorAll<HTMLElement>('.modal button:not(:disabled), .modal input:not(:disabled), .modal select:not(:disabled), .modal textarea:not(:disabled), .modal a[href]'));
    window.setTimeout(() => focusable()[0]?.focus(), 0);
    const handleKey = (event:KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setDialog(null); return; }
      if (event.key === 'Tab') {
        const nodes = focusable(); if (!nodes.length) return;
        if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes[nodes.length-1].focus(); }
        else if (!event.shiftKey && document.activeElement === nodes[nodes.length-1]) { event.preventDefault(); nodes[0].focus(); }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => { document.removeEventListener('keydown', handleKey); previous?.focus?.(); };
  }, [dialog]);

  if (!session && configuration.error) return <main className="login-screen"><section className="login-card"><div className="brand-mark">EC<span>OPS</span></div><p className="eyebrow">CONFIGURATION ERROR</p><h1>Dashboard unavailable</h1><p className="error" role="alert">{configuration.error}</p><small>Correct VITE_ECS_API_ORIGIN in the staging build environment.</small></section></main>;
  if (!session) return <main className="login-screen"><form className="login-card" onSubmit={doLogin}>
    <img className="login-logo" src={logoUrl} alt="Emergency Coordination"/><p className="eyebrow">EMERGENCY COORDINATION</p><h1>Operations center</h1><p className="muted">Sign in with an authorized administrator account.</p>
    {!configured && <label>HTTPS API origin<input name="origin" type="url" placeholder="https://api.example.org" required /></label>}
    <label>Email<input name="email" type="email" autoComplete="username" required /></label><label>Password<input name="password" type="password" autoComplete="current-password" minLength={12} required /></label>
    {error&&<p className="error" role="alert">{error}</p>}<Button className="primary" disabled={busy}>{busy?'Signing in…':'Sign in'}</Button>
    <small>Session is limited to this browser tab and verified with the service on reload.</small>
  </form></main>;

  const nav: Page[] = ['overview','incidents','responders','users','resources','reports','audit','notifications','automation','coadmins'];
  const visible = nav.filter(item => item==='overview' ? can('view_dashboard') : item==='incidents' ? can('view_incidents') : item==='responders' ? can('view_dashboard')||can('manage_responders') : item==='users' ? can('manage_users') : item==='resources' ? can('view_dashboard')||can('manage_resources') : item==='reports' ? can('view_reports') : item==='audit' ? can('view_audit_logs') : item==='notifications' ? true : item==='automation' ? session.account.role==='super_admin' : session.account.role==='super_admin');
  const noticeBar = notice && <div className="notice" role="status">{notice}</div>;
  const loading = busy && <div className="loading"><span className="spinner"/>Loading service records…</div>;
  const errorBar = error && <div className="error" role="alert">{error}<Button className="quiet" onClick={()=>void run()}>Retry</Button></div>;
  const incidentActions = (i:Row) => <div className="actions">
    <Button className="quiet" onClick={()=>openIncidentDetails(i)}>Details</Button>
    {can('assign_responders')&&activeIncident(i)&&<Button className="secondary" onClick={()=>open('Assign responder',i.responder_id?'reassign':'assign',i)}>{i.responder_id?'Reassign':'Assign'}</Button>}
    {can('update_incidents')&&activeIncident(i)&&<><Button className="secondary" onClick={()=>confirm(`Resolve ${i.reference}?`)&&void act(`/admin/incidents/${i.id}/resolve`,{method:'POST'},'Incident resolved.')}>Resolve</Button><Button className="danger-quiet" onClick={()=>confirm(`Cancel ${i.reference}?`)&&void act(`/admin/incidents/${i.id}/cancel`,{method:'POST'},'Incident cancelled.')}>Cancel</Button></>}
    {can('update_incidents')&&i.report?.status!=='reviewed'&&<Button className="quiet" onClick={()=>open('Review resolution report','review',i)}>Review report</Button>}
  </div>;
  const renderBody = () => {
    if (loading) return loading;
    if (errorBar && !data.length) return errorBar;
    switch(page) {
      case 'overview': {
        const d=data[0]||{}, critical=data.length?0:0;
        return <><div className="metric-grid">{[['Total incidents',d.total_incidents],['Unassigned',d.unassigned],['Active incidents',d.active_incidents],['Responders available',d.responders_available],['Responders busy',d.responders_busy],['Resources allocated',`${d.resources_allocated||0} / ${d.resources_total||0}`]].map(([k,v])=><article className="metric" key={String(k)}><span>{k}</span><strong>{v??'—'}</strong><small>Current service count</small></article>)}</div><Panel title="Operational overview" subtitle="Counts returned by the coordination API."><p className="muted">Open incidents and category analytics are available in the incident queue and reports.</p><Button className="primary" onClick={()=>{setData([]);setPage(can('view_incidents')?'incidents':'responders');}}>Open {can('view_incidents')?'incident queue':'responder list'}</Button></Panel></>;
      }
      case 'incidents': return <Panel title="Incident queue" subtitle={`${filtered.length} of ${data.length} incidents`}><div className="filters"><label>Search<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Reference, type, description, location" /></label><label>Status<select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">All statuses</option>{statuses.map(x=><option key={x}>{x}</option>)}</select></label><label>Priority<select value={priorityFilter} onChange={e=>setPriorityFilter(e.target.value)}><option value="">All priorities</option>{['Critical','High','Medium','Low'].map(x=><option key={x}>{x}</option>)}</select></label><label>Category<select value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}><option value="">All categories</option>{[...new Set(data.map(x=>x.emergency_type).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select></label></div><Table headers={['Incident','Priority','Status','Location','Reported','Actions']}>{filtered.map(i=><tr key={i.id}><td><b>{i.reference}</b><small>{i.emergency_type}</small></td><td><span className={`priority ${String(i.priority||'Normal').toLowerCase()}`}>{i.priority||'Normal'}</span></td><td><span className="status">{i.status}</span></td><td>{i.location_label||'Not provided'}</td><td>{stamp(i.created_at)}</td><td>{incidentActions(i)}</td></tr>)}</Table>{!filtered.length&&<Empty>No incidents match these filters.</Empty>}</Panel>;
      case 'responders': return <Panel title="Responder administration" subtitle="Account, availability, assignment, and invitation state." action={can('manage_responders')&&<Button className="primary" onClick={()=>open('Invite responder','invite')}>Invite responder</Button>}><div className="filters directory-filters"><label>Search<input aria-label="Search responders" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Name, email, capability, task"/></label><label>Availability<select aria-label="Filter responders" value={directoryStatus} onChange={e=>setDirectoryStatus(e.target.value)}><option value="">All responders</option><option value="available">Available</option><option value="busy">Busy</option><option value="unavailable">Unavailable or suspended</option><option value="invited">Invitation pending</option></select></label></div><Table headers={['Responder','Capabilities','Availability','Account / invitation','Active assignment','Actions']}>{filteredResponders.map(r=><tr key={r.id}><td><b>{r.display_name}</b><small>{r.email}</small></td><td>{(r.capabilities||[]).join(', ')}</td><td>{r.active_incident_id?'Busy':r.active&&r.available?'Available':'Unavailable'}</td><td>{r.active?'Active':'Suspended'} · {r.invitation_status||'—'}{r.invitation_expires_at&&<small>Expires {stamp(r.invitation_expires_at)}</small>}</td><td>{r.active_incident_reference||'—'}{r.active_resource_name&&<small>{r.active_resource_name}</small>}</td><td><div className="actions">{can('manage_responders')&&<>{r.active&&<Button className="quiet" onClick={()=>open('Edit capabilities','capabilities',r)}>Capabilities</Button>}{r.active&&<Button className="quiet" onClick={()=>void act(`/admin/responders/${r.id}/availability`,{method:'PATCH',body:JSON.stringify({available:!r.available})},'Availability updated.')}>{r.available?'Set unavailable':'Set available'}</Button>}<Button className="quiet" onClick={()=>{if(!r.active||confirm(`Suspend ${r.display_name}? The API rejects suspension while they have an active task.`))void act(`/admin/users/${r.id}/active?active=${!r.active}`,{method:'PATCH'},'Account state updated.');}}>{r.active?'Suspend':'Activate'}</Button>{!r.active&&r.invitation_status!=='accepted'&&<Button className="quiet" onClick={()=>void act(`/admin/invitations/responders/${r.id}/resend`,{method:'POST'},'Invitation resent.')}>Resend invitation</Button>}</>}</div></td></tr>)}</Table>{!filteredResponders.length&&<Empty>No responders match these filters.</Empty>}</Panel>;
      case 'users': return <Panel title="User accounts" subtitle={`${filteredUsers.length} of ${data.length} public accounts.`}><div className="filters directory-filters"><label>Search<input aria-label="Search users" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Name or email"/></label><label>Status<select aria-label="Filter user account status" value={directoryStatus} onChange={e=>setDirectoryStatus(e.target.value)}><option value="">All accounts</option><option value="active">Active</option><option value="suspended">Suspended</option></select></label></div><Table headers={['Name','Email','Created','Status','Actions']}>{filteredUsers.map(u=><tr key={u.id}><td>{u.display_name}</td><td>{u.email}</td><td>{stamp(u.created_at)}</td><td>{u.active?'Active':'Suspended'}</td><td><div className="actions">{can('view_incidents')&&<Button className="quiet" onClick={()=>void openUserHistory(u)}>Incident history</Button>}{can('manage_users')&&<Button className="secondary" onClick={()=>confirm(`${u.active?'Suspend':'Activate'} ${u.email}?`)&&void act(`/admin/users/${u.id}/active?active=${!u.active}`,{method:'PATCH'},'Account status updated.')}>{u.active?'Suspend':'Activate'}</Button>}</div></td></tr>)}</Table>{!filteredUsers.length&&<Empty>No accounts match these filters.</Empty>}</Panel>;
      case 'resources': return <Panel title="Resource inventory" subtitle="Current quantities and active allocations." action={can('manage_resources')&&<Button className="primary" onClick={()=>open('Add resource','resource')}>Add resource</Button>}><Table headers={['Resource','Type','Available','Allocated','Quantity','Status','Actions']}>{data.map(r=><tr key={r.id}><td>{r.name}</td><td>{r.kind}</td><td>{r.available}</td><td>{r.allocated}</td><td>{r.quantity}</td><td>{r.active?'Active':'Inactive'}</td><td>{can('manage_resources')&&<Button className="quiet" onClick={()=>open('Edit resource','resource',r)}>Edit</Button>}</td></tr>)}</Table>{!data.length&&<Empty>No resources configured.</Empty>}</Panel>;
      case 'reports': return <Reports api={api} canExport={can('export_reports')} />;
      case 'audit': return <Panel title="Audit history" subtitle="Administrative actions recorded by the service."><Table headers={['Time','Action','Entity','Details','Actor']}>{data.map(x=><tr key={x.id}><td>{stamp(x.created_at)}</td><td>{x.action}</td><td>{x.entity_type} · {String(x.entity_id).slice(0,8)}</td><td>{JSON.stringify(x.details)}</td><td>{String(x.actor_id).slice(0,8)}</td></tr>)}</Table>{!data.length&&<Empty>No audit events.</Empty>}</Panel>;
      case 'coadmins': return <Panel title="Co-Admin access" subtitle="Only Super Admins can manage scoped administrators." action={<Button className="primary" onClick={()=>open('Create Co-Admin','coadmin')}>Create Co-Admin</Button>}><Table headers={['Name','Email','Access','Permissions','Actions']}>{data.map(x=><tr key={x.id}><td>{x.display_name}</td><td>{x.email}</td><td>{x.active?'Active':'Suspended'}</td><td>{(x.permissions||[]).join(', ')||'None'}</td><td><div className="actions"><Button className="quiet" onClick={()=>open('Edit Co-Admin permissions','permissions',x)}>Permissions</Button><Button className="quiet" onClick={()=>confirm(`${x.active?'Revoke':'Restore'} ${x.email}?`)&&void act(`/admin/coadmins/${x.id}/active?active=${!x.active}`,{method:'PATCH'},'Co-Admin access updated.')}>{x.active?'Revoke':'Restore'}</Button></div></td></tr>)}</Table>{!data.length&&<Empty>No Co-Admins.</Empty>}</Panel>;
      case 'notifications': return <Panel title="Notifications" subtitle="Persistent in-app events for this account. Push and email delivery are not represented here." action={data.some(x=>!x.read)&&<Button className="secondary" onClick={()=>void act('/notifications/read-all',{method:'PATCH'},'Notifications marked read.')}>Mark all read</Button>}><div className="notification-list">{data.map(n=><article key={n.id} className={n.read?'read':''}><span className="notification-dot"/><div><b>{n.title}</b><p>{n.message}</p><small>{stamp(n.created_at)} · {n.kind}</small></div>{!n.read&&<Button className="quiet" onClick={()=>void act(`/notifications/${n.id}/read`,{method:'PATCH'},'Notification marked read.')}>Mark read</Button>}</article>)}{!data.length&&<Empty>No notifications yet.</Empty>}</div></Panel>;
      case 'automation': { const p=data[0]||{}; return <Panel title="Automatic assignment policy" subtitle={`${p.version||'Deterministic policy'} · server enforced`}><p className="callout">Automatic assignment requires a fresh, accurate incident and responder location, an active available responder with a matching capability, and no active workload. The backend is authoritative.</p><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);if(confirm('Save automatic assignment policy?'))void act('/admin/automation',{method:'PUT',body:JSON.stringify({enabled:f.get('enabled')==='on',max_severity:Number(f.get('severity'))})},'Policy saved.');}}><label className="check"><input name="enabled" type="checkbox" defaultChecked={p.enabled}/> Enable eligible automatic assignment</label><label>Maximum severity<select name="severity" defaultValue={p.max_severity||3}>{[1,2,3,4,5].map(x=><option key={x}>{x}</option>)}</select></label><Button className="primary">Save policy</Button></form></Panel>; }
    }
  };

  async function openIncidentDetails(row:Row) {
    setBusy(true); setError('');
    try {
      const [incident, updates, report] = await Promise.all([
        api<Row>(`/incidents/${row.id}`), api<Row[]>(`/incidents/${row.id}/updates`), api<Row>(`/incidents/${row.id}/report`).catch(()=>null),
      ]);
      setDialog({title:`${incident.reference} · ${incident.emergency_type}`,kind:'details',row:{...incident,updates,report}});
    } catch(e) { setError(failText(e)); }
    finally { setBusy(false); }
  }
  async function openUserHistory(user:Row) {
    setBusy(true); setError('');
    try {
      const incidents = await api<Row[]>('/incidents');
      setDialog({title:`${user.display_name} · incident history`,kind:'user-history',row:{incidents:incidents.filter(item=>item.reporter_id===user.id)}});
    } catch(e) { setError(failText(e)); }
    finally { setBusy(false); }
  }
  const onSaveDialog = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!dialog) return;
    const f = new FormData(event.currentTarget), r=dialog.row;
    const list = (name:string) => String(f.get(name)||'').split(',').map(x=>x.trim()).filter(Boolean);
    switch(dialog.kind) {
      case 'assign': case 'reassign': await assignAction(r, String(f.get('responder_id')), String(f.get('resource_id')||'')||null, dialog.kind); return;
      case 'review': await act(`/admin/incidents/${r.id}/report/review`,{method:'POST',body:JSON.stringify({note:f.get('note')})},'Resolution report marked reviewed.'); return;
      case 'invite': await act('/admin/invitations/responders',{method:'POST',body:JSON.stringify({display_name:f.get('name'),email:f.get('email'),capabilities:list('capabilities')})},'Responder invitation created.', 'responders'); return;
      case 'capabilities': await act(`/admin/responders/${r.id}/capabilities`,{method:'PUT',body:JSON.stringify(list('capabilities'))},'Capabilities updated.'); return;
      case 'resource': { const body=JSON.stringify({name:f.get('name'),kind:f.get('kind'),quantity:Number(f.get('quantity'))}); await act(r?`/admin/resources/${r.id}?active=${f.get('active')}`:'/admin/resources',{method:r?'PATCH':'POST',body},'Resource saved.'); return; }
      case 'coadmin': { const selected=Array.from(event.currentTarget.querySelectorAll<HTMLInputElement>('input[name="permissions"]:checked')).map(x=>x.value); await act('/admin/coadmins',{method:'POST',body:JSON.stringify({display_name:f.get('name'),email:f.get('email'),password:f.get('password'),permissions:selected})},'Co-Admin created.','coadmins'); return; }
      case 'permissions': { const selected=Array.from(event.currentTarget.querySelectorAll<HTMLInputElement>('input[name="permissions"]:checked')).map(x=>x.value); await act(`/admin/coadmins/${r.id}/permissions`,{method:'PATCH',body:JSON.stringify(selected)},'Permissions updated.','coadmins'); return; }
    }
  };
  const assignAction = async (incident:Row, responder_id:string, resource_id:string|null, kind:string) => {
    if (!responder_id) { setError('Choose a responder.'); return; }
    await act(`/admin/incidents/${incident.id}/${kind}`,{method:'POST',body:JSON.stringify({responder_id,resource_id})},'Responder assignment saved.');
  };

  return <div className="shell"><aside className="sidebar"><a className="brand" href="#overview" onClick={e=>{e.preventDefault();setData([]);setDirectoryQuery('');setDirectoryStatus('');setPage('overview')}}><img src={logoUrl} alt=""/><span><b>Emergency Coordination</b><small>Operations center</small></span></a><p className="nav-caption">WORKSPACE</p><nav>{visible.map(item=><button key={item} className={page===item?'nav-item active':'nav-item'} onClick={()=>{setError('');setData([]);setDirectoryQuery('');setDirectoryStatus('');setPage(item);setDialog(null)}}><span className="nav-icon" aria-hidden="true">{item==='overview'?'◫':item==='incidents'?'△':item==='responders'?'♙':item==='resources'?'▱':item==='reports'?'▥':item==='audit'?'≡':item==='notifications'?'◌':item==='automation'?'⚙':item==='coadmins'?'♧':'◎'}</span>{labels[item]}</button>)}</nav><div className="sidebar-foot"><span className="avatar">{session.account.display_name.split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase()}</span><span><b>{session.account.display_name}</b><small>{session.account.role==='super_admin'?'Super Admin':'Co-Admin'}</small></span><Button className="icon-button" aria-label="Sign out" onClick={()=>void logout()}>↗</Button></div></aside><main className="main"><header className="topbar"><div><p className="eyebrow">EMERGENCY COORDINATION / OPERATIONS</p><h1>{labels[page]}</h1><p className="muted">Current coordination records from your service.</p></div><div className="top-actions"><span className="service-state"><i/>Authenticated</span><Button className="secondary" onClick={()=>void run()}>↻ Refresh</Button></div></header>{noticeBar}{errorBar}{renderBody()}</main>
    {dialog&&<div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setDialog(null)}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><div><p className="eyebrow">OPERATIONS</p><h2 id="modal-title">{dialog.title}</h2></div><Button className="icon-button" aria-label="Close dialog" onClick={()=>setDialog(null)}>×</Button></header>
      {dialog.kind==='details'?<div className="incident-details"><div className="detail-grid">{[['Status',dialog.row.status],['Priority',dialog.row.priority],['Location',dialog.row.location_label],['Responder',dialog.row.responder_name||'Unassigned'],['Resource',dialog.row.resource_name||'None'],['Reported',stamp(dialog.row.created_at)],['Severity / urgency',`${dialog.row.severity} / ${dialog.row.urgency}`]].map(([k,v])=><div key={String(k)}><small>{k}</small><b>{v||'—'}</b></div>)}</div><div><h3>Original report</h3><p>{dialog.row.description}</p></div>{dialog.row.analysis&&<div className="callout"><b>Decision support · human review required</b><p>{dialog.row.analysis.result?.summary||dialog.row.analysis.status}</p>{dialog.row.analysis.result?.explanation&&<p>{dialog.row.analysis.result.explanation}</p>}{['admin','super_admin'].includes(session.account.role)&&(dialog.row.analysis.last_error_type||dialog.row.analysis.status==='unavailable')&&<Button className="secondary" onClick={()=>void act(`/admin/incidents/${dialog.row.id}/analysis/retry`,{method:'POST'},'Analysis retry queued.')}>Retry analysis</Button>}</div>}{dialog.row.report&&<div><h3>Resolution report · {dialog.row.report.status}</h3><p><b>Outcome:</b> {dialog.row.report.content?.outcome}</p><p><b>Cause:</b> {dialog.row.report.content?.cause}</p><p className="muted">Sources: {dialog.row.report.source_records?.length||0} persisted records. This summary is not an independent investigation.</p>{dialog.row.report.status!=='reviewed'&&can('update_incidents')&&<Button className="secondary" onClick={()=>open('Review resolution report','review',dialog.row)}>Mark reviewed with note</Button>}</div>}<div><h3>Response history</h3>{dialog.row.updates?.length?dialog.row.updates.map((u:Row)=><article className="history-row" key={u.id}><b>{u.kind}</b><p>{u.message}</p><small>{stamp(u.created_at)}</small></article>):<Empty>No response updates.</Empty>}</div><footer className="modal-actions"><Button className="secondary" onClick={()=>setDialog(null)}>Close</Button></footer></div>:
      dialog.kind==='user-history'?<div className="incident-details"><p className="muted">Incident references and response states; personal location details are not shown here.</p>{dialog.row.incidents.length?<Table headers={['Reference','Category','Status','Reported']}>{dialog.row.incidents.map((item:Row)=><tr key={item.id}><td><button className="quiet" onClick={()=>void openIncidentDetails(item)}>{item.reference}</button></td><td>{item.emergency_type}</td><td>{item.status}</td><td>{stamp(item.created_at)}</td></tr>)}</Table>:<Empty>No incidents have been submitted by this account.</Empty>}<footer className="modal-actions"><Button className="secondary" onClick={()=>setDialog(null)}>Close</Button></footer></div>:
      <form onSubmit={onSaveDialog} className="form-stack">
        {dialog.kind==='assign'||dialog.kind==='reassign'?<AssignmentFields api={api} incident={dialog.row} />:null}
        {dialog.kind==='review'&&<label>Review note<textarea name="note" required minLength={1} maxLength={1000}/></label>}
        {dialog.kind==='invite'&&<><label>Name<input name="name" required maxLength={120}/></label><label>Email<input name="email" type="email" required/></label><label>Capabilities, comma separated<input name="capabilities" required placeholder="medical, ambulance"/></label><p className="muted">The API handles delivery and returns an activation link only in supported environments.</p></>}
        {dialog.kind==='capabilities'&&<label>Capabilities, comma separated<input name="capabilities" defaultValue={(dialog.row.capabilities||[]).join(', ')} required/></label>}
        {dialog.kind==='resource'&&<><label>Name<input name="name" defaultValue={dialog.row?.name||''} required maxLength={120}/></label><label>Type<input name="kind" defaultValue={dialog.row?.kind||''} required maxLength={48}/></label><label>Quantity<input name="quantity" type="number" min={dialog.row?.allocated||0} max="10000" defaultValue={dialog.row?.quantity||1} required/></label>{dialog.row&&<label>Status<select name="active" defaultValue={String(dialog.row.active)}><option value="true">Active</option><option value="false">Inactive</option></select></label>}</>}
        {dialog.kind==='coadmin'&&<><label>Name<input name="name" required maxLength={120}/></label><label>Email<input name="email" type="email" required/></label><label>Initial password<input name="password" type="password" minLength={12} maxLength={128} required/></label><PermissionChoices /></>}
        {dialog.kind==='permissions'&&<PermissionChoices initial={dialog.row.permissions||[]} />}
        {error&&<p className="error" role="alert">{error}</p>}<footer className="modal-actions"><Button type="button" className="secondary" onClick={()=>setDialog(null)}>Cancel</Button><Button className="primary" disabled={busy}>{busy?'Saving…':'Save changes'}</Button></footer>
      </form>}
    </section></div>}
  </div>;
}

function configuredApiOriginForLogin(value:string) { return import.meta.env.VITE_ECS_API_ORIGIN ? configuredApiOrigin() : validateOrigin(value); }
function validateOrigin(value:string) {
  const u=new URL(value);
  if(u.protocol!=='https:'||!u.hostname||u.username||u.password||(u.pathname!=='/'&&u.pathname!=='')||u.search||u.hash||/(^|\.)example(\.|$)|(^|\.)(test|invalid|localhost)$|your-api-host|your-domain/i.test(u.hostname)) throw new Error('Use a real HTTPS API origin without credentials, path, query, or fragment.');
  return u.origin;
}
function PermissionChoices({initial=[]}:{initial?:string[]}) { return <fieldset><legend>Permissions</legend><div className="permission-grid">{permissions.map(([key,label])=><label key={key} className="check"><input type="checkbox" name="permissions" value={key} defaultChecked={initial.includes(key)}/>{label}</label>)}</div></fieldset>; }
function AssignmentFields({api,incident}:{api:<T,>(path:string, options?:any)=>Promise<T>;incident:Row}) {
  const [choices,setChoices]=useState<Row[]>([]); const [resources,setResources]=useState<Row[]>([]); const [error,setError]=useState('');
  useEffect(()=>{api<Row>(`/admin/incidents/${incident.id}/recommendations`).then(result=>{setChoices(result.eligible_responders||[]);setResources(result.compatible_resources||[]);}).catch(e=>setError(failText(e)));},[api,incident.id]);
  return <>{error&&<p className="error" role="alert">{error}</p>}<p className="muted">Recommendations are supplied by the API; assignment eligibility is checked again by the backend.</p><label>Responder<select name="responder_id" required defaultValue=""><option value="" disabled>Select responder</option>{choices.map((x:Row)=><option key={x.responder_id} value={x.responder_id}>{x.display_name} · score {x.score}</option>)}</select></label><label>Resource<select name="resource_id" defaultValue=""><option value="">No resource</option>{resources.map((r:Row)=><option key={r.id} value={r.id}>{r.name} · {r.available} available</option>)}</select></label></>;
}
function Reports({api,canExport}:{api:<T,>(path:string,options?:any)=>Promise<T>;canExport:boolean}) {
  const [days,setDays]=useState(30);const [report,setReport]=useState<Row|null>(null);const [error,setError]=useState('');
  useEffect(()=>{api<Row>(`/admin/analytics?days=${days}`).then(setReport).catch(e=>setError(failText(e)));},[api,days]);
  const exportData=()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`operations-summary-${days}days.json`;a.click();URL.revokeObjectURL(url);};
  return <Panel title="Operational analytics" subtitle={report?.data_note||'Descriptive aggregates from persisted service records.'} action={<div className="actions"><label className="compact-label">Period<select value={days} onChange={e=>setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select></label>{canExport&&<Button className="secondary" onClick={exportData}>Export JSON</Button>}</div>}>{error&&<p className="error">{error}</p>}{report&&<><div className="metric-grid">{[['Incidents',report.incident_count],['Assignments',report.assignment_count],['Completed assignments',report.completed_assignment_count],['Resources allocated',report.resource_units_allocated]].map(([k,v])=><article className="metric" key={String(k)}><span>{k}</span><strong>{v??'—'}</strong><small>Last {days} days / current snapshot</small></article>)}</div><div className="report-grid"><div><h3>Incident statuses</h3>{Object.entries(report.status_counts||{}).map(([k,v])=><div className="bar-row" key={k}><span>{k}</span><i><b style={{width:`${100*Number(v)/Math.max(1,...Object.values(report.status_counts||{}).map(Number))}%`}}/></i><b>{String(v)}</b></div>)}</div><div><h3>Categories</h3>{Object.entries(report.category_counts||{}).map(([k,v])=><div className="bar-row" key={k}><span>{k}</span><b>{String(v)}</b></div>)}</div></div><div className="metric-grid"><article className="metric"><span>Average assignment delay</span><strong>{report.average_assignment_delay_minutes??'—'} min</strong></article><article className="metric"><span>Assignment to completion</span><strong>{report.average_assignment_to_completion_minutes??'—'} min</strong></article></div><p className="muted">No forecasts or dispatch recommendations are shown. Resource allocation is a current snapshot.</p></>}</Panel>;
}
