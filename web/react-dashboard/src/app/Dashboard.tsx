import { Children, FormEvent, Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { configuredApiOrigin } from '../api/config';
import { ApiError, request } from '../api/client';
import { Account, clearSession, hasPermission, readSession, saveSession, Session, signIn, signOut, verifySession } from '../auth/session';
import { filterIncidents } from '../features/incidents/filter';
import { IERCS_ICON } from '../branding';
const logoUrl = IERCS_ICON;

type Row = Record<string, any>;
type OverviewModel = { dashboard:Row; incidents:Row[]; responders:Row[]; notifications:Row[]; activity:Row[]; analytics:Row|null };
type Page = 'overview'|'incidents'|'responders'|'users'|'resources'|'reports'|'historical'|'audit'|'coadmins'|'notifications'|'automation';
const labels: Record<Page,string> = { overview:'Overview', incidents:'Incident queue', responders:'Responders', users:'User accounts', resources:'Resources', reports:'Reports & analytics', historical:'Historical/Public Data', audit:'Audit history', coadmins:'Co-Admins', notifications:'Notifications', automation:'Automation policy' };
const permissions: [string,string][] = [['view_dashboard','Dashboard'],['view_incidents','Incidents'],['update_incidents','Update incidents'],['assign_responders','Assign responders'],['manage_responders','Manage responders'],['manage_users','Manage users'],['manage_resources','Manage resources'],['view_reports','View reports'],['export_reports','Export reports'],['view_audit_logs','View audit logs']];
const statuses = ['Unassigned','Assigned','Accepted','En Route','On Scene','Resolved','Cancelled'];
const activeIncident = (x: Row) => !['Resolved','Cancelled'].includes(x.status);
const stamp = (x?: string) => x ? new Date(x).toLocaleString() : '—';
const failText = (error: unknown) => error instanceof Error ? error.message : 'The request failed.';

function Button({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) { return <button {...props}>{children}</button>; }
function Panel({ title, subtitle, action, children }: { title:string; subtitle?:string; action?:React.ReactNode; children:React.ReactNode }) { return <section className="panel"><header className="panel-head"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</header>{children}</section>; }
function Table({ headers, children }: {headers:string[];children:React.ReactNode}) { return <div className="table-wrap"><table><thead><tr>{headers.map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{Children.toArray(children)}</tbody></table></div>; }
function Empty({ children='No records found.' }: {children?:React.ReactNode}) { return <div className="empty">{children}</div>; }
function NavIcon({ page }: { page:Page }) {
  const paths: Record<Page, React.ReactNode> = {
    overview: <><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="11" width="7" height="10" rx="1.5"/><rect x="3" y="14" width="8" height="7" rx="1.5"/></>,
    incidents: <><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5m0 3h.01"/></>,
    notifications: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12h4"/></>,
    responders: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m6-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm6-7.8a4 4 0 0 1 0 7.6M20 15a4 4 0 0 1 2 3.5V21"/></>,
    users: <><circle cx="9" cy="8" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m3-13a4 4 0 0 0 0 8m3 5v-2a7 7 0 0 0-4-6.3"/></>,
    resources: <><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/></>,
    reports: <><path d="M3 3v18h18M8 15l4-4 3 3 6-7"/></>,
    historical: <><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/></>,
    audit: <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
    automation: <><circle cx="12" cy="12" r="4"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.5.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.5-.9l-1.7.7-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.8l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.5-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.5.9l1.7-.7 1.4 2.4-1.4 1.1a7 7 0 0 1 0 1.7Z" transform="translate(-1 -1)"/></>,
    coadmins: <><circle cx="9" cy="8" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m3-13v6m-3-3h6"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[page]}</svg>;
}

export function Dashboard() {
  const [session, setSession] = useState<Session|null>(null);
  const [page, setPage] = useState<Page>('overview');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [data, setData] = useState<Row[]>([]);
  const [overviewData, setOverviewData] = useState<OverviewModel|null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [activationLink, setActivationLink] = useState<{ url:string; expiresAt?:string }|null>(null);
  const [globalQuery, setGlobalQuery] = useState('');
  const [lastUpdated, setLastUpdated] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [directoryQuery, setDirectoryQuery] = useState('');
  const [directoryStatus, setDirectoryStatus] = useState('');
  const [dialog, setDialog] = useState<{ title:string; kind:string; row:Row }|null>(null);
  const configuration = useMemo(() => { try { return { origin: configuredApiOrigin(), error: '' }; } catch { return { origin: '', error: 'The coordination service is unavailable. Please contact your administrator.' }; } }, []);
  const configured = configuration.origin;
  const can = useCallback((permission: string) => !!session && hasPermission(session.account, permission), [session]);
  const api = useCallback(<T,>(path:string, options: Parameters<typeof request>[2] = {}) => {
    if (!session) throw new Error('Sign in to continue.');
    return request<T>(session.origin, path, { ...options, token: session.token });
  }, [session]);
  const run = useCallback(async (path:Page = page, silent = false) => {
    if (!session) return;
    if (!silent) { setBusy(true); setError(''); }
    try {
      let result: any;
      switch (path) {
        case 'overview': {
          const [dashboard, incidents, responders, notifications, analytics, activity] = await Promise.all([
            api<Row>('/admin/dashboard'),
            can('view_incidents') ? api<Row[]>('/incidents') : Promise.resolve([]),
            can('view_dashboard') || can('manage_responders') ? api<Row[]>('/admin/responders') : Promise.resolve([]),
            api<Row[]>('/notifications'),
            can('view_reports') ? api<Row>('/admin/analytics?days=7') : Promise.resolve(null),
            can('view_audit_logs') ? api<Row[]>('/admin/audit?limit=6') : Promise.resolve([]),
          ]);
          result = { dashboard, incidents, responders, notifications, analytics, activity } satisfies OverviewModel;
          setOverviewData(result);
          setData([dashboard]);
          break;
        }
        case 'incidents': result = await api<Row[]>('/incidents'); setData(result); break;
        case 'responders': result = await api<Row[]>('/admin/responders'); setData(result); break;
        case 'users': result = await api<Row[]>('/admin/users?role=user'); setData(result); break;
        case 'resources': result = await api<Row[]>('/admin/resources'); setData(result); break;
        case 'reports': result = await api<Row>(`/admin/analytics?days=30`); setData([result]); break;
        case 'historical': result = await api<Row>('/admin/public-disaster-data'); setData([result]); break;
        case 'audit': result = await api<Row[]>('/admin/audit?limit=100'); setData(result); break;
        case 'coadmins': result = await api<Row[]>('/admin/coadmins'); setData(result); break;
        case 'notifications': result = await api<Row[]>('/notifications'); setData(result); setOverviewData(previous => previous ? { ...previous, notifications:result } : previous); break;
        case 'automation': result = await api<Row>('/admin/automation'); setData([result]); break;
      }
      setError('');
      setLastUpdated(new Date().toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' }));
    } catch (e) { if (e instanceof ApiError && e.status === 401) { clearSession(); setSession(null); setError('Your admin session expired or was revoked. Sign in again.'); } else setError(failText(e)); }
    finally { if (!silent) setBusy(false); }
  }, [api, can, page, session]);
  useEffect(() => {
    if (!configured) { clearSession(); return; }
    const saved = readSession();
    if (!saved) return;
    if (configured && saved.origin !== configured) { clearSession(); setError('Saved session belongs to a different API origin. Sign in again.'); return; }
    verifySession(saved).then(valid => { setSession(valid); saveSession(valid); }).catch(() => { clearSession(); setError('Saved session could not be verified. Please sign in again.'); });
  }, [configured]);
  useEffect(() => { if (session) void run(page); }, [session, page, run]);
  useEffect(() => {
    if (!session || !['overview','incidents','reports','notifications'].includes(page)) return;
    let refreshing = false;
    const timer = window.setInterval(() => {
      if (document.hidden || dialog || refreshing) return;
      refreshing = true;
      void run(page, true).finally(() => { refreshing = false; });
    }, 12000);
    return () => window.clearInterval(timer);
  }, [dialog, page, run, session]);
  const tell = (message:string) => { setNotice(message); window.setTimeout(() => setNotice(''), 5000); };
  const doLogin = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      const next = await signIn(configured, String(form.get('email')), String(form.get('password')));
      saveSession(next); setSession(next); setPage('overview');
    } catch (e) { setError(failText(e)); }
    finally { setBusy(false); }
  };
  const logout = async () => { if (session) await signOut(session); setSession(null); setData([]); setOverviewData(null); setActivationLink(null); setError(''); setPage('overview'); };
  const act = async (path:string, options:Parameters<typeof request>[2], success:string, reload = page) => {
    try { const result = await api<Row>(path, options); setDialog(null); setActivationLink(result?.activation_url ? { url:result.activation_url, expiresAt:result.expires_at } : null); tell(success); await run(reload); }
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

  if (!session && configuration.error) return <main className="login-screen"><section className="login-card configuration-card"><img className="login-logo" src={logoUrl} alt="IERCS"/><p className="eyebrow">IERCS · EMERGENCY COORDINATION</p><h1>Dashboard unavailable</h1><p className="error" role="alert">{configuration.error}</p></section></main>;
  if (!session) return <main className="login-screen"><form className="login-card" onSubmit={doLogin}>
    <img className="login-logo" src={logoUrl} alt="IERCS"/><p className="eyebrow">IERCS · EMERGENCY COORDINATION</p><h1>Operations center</h1><p className="muted">Sign in with an authorized administrator account.</p>
    <label>Email<input name="email" type="email" autoComplete="username" required /></label><label>Password<input name="password" type="password" autoComplete="current-password" minLength={12} required /></label>
    {error&&<p className="error" role="alert">{error}</p>}<Button className="primary" disabled={busy}>{busy?'Signing in…':'Sign in'}</Button>
    <small>Session is limited to this browser tab and verified with the service on reload.</small>
  </form></main>;

  const nav: Page[] = ['overview','incidents','notifications','responders','users','resources','reports','historical','audit','automation','coadmins'];
  const visible = nav.filter(item => item==='overview' ? can('view_dashboard') : item==='incidents' ? can('view_incidents') : item==='responders' ? can('view_dashboard')||can('manage_responders') : item==='users' ? can('manage_users') : item==='resources' ? can('view_dashboard')||can('manage_resources') : item==='reports'||item==='historical' ? can('view_reports') : item==='audit' ? can('view_audit_logs') : item==='notifications' ? true : item==='automation' ? session.account.role==='super_admin' : session.account.role==='super_admin');
  const noticeBar = notice && <div className="notice" role="status">{notice}</div>;
  const invitationNotice = activationLink && <div className="activation-notice" role="status">
    <span>One-time responder activation link{activationLink.expiresAt ? ` · expires ${stamp(activationLink.expiresAt)}` : ''}. Copy it now:</span>
    <a href={activationLink.url}>{activationLink.url}</a>
  </div>;
  const loading = busy && <div className="loading"><span className="spinner"/>Loading service records…</div>;
  const errorBar = error && <div className="error" role="alert">{error}<Button className="quiet" onClick={()=>void run()}>Retry</Button></div>;
  const openIncidentsWithFilter = (filter:string, value:string) => {
    setSearch(''); setGlobalQuery(''); setStatusFilter(filter==='status'?value:''); setPriorityFilter(filter==='priority'?value:''); setCategoryFilter(filter==='category'?value:''); setData([]); setPage('incidents');
  };
  const openPage = (target:Page) => { setError(''); setData([]); setDirectoryQuery(''); setDirectoryStatus(''); setDialog(null); setPage(target); setMobileMenuOpen(false); };
  const submitGlobalSearch = () => { setSearch(globalQuery); setStatusFilter(''); setPriorityFilter(''); setCategoryFilter(''); setPage('incidents'); };
  const incidentActions = (i:Row) => <div className="actions">
    <Button className="quiet" onClick={()=>openIncidentDetails(i)}>Details</Button>
    {can('assign_responders')&&activeIncident(i)&&<Button className="secondary" onClick={()=>open('Assign responder',i.responder_id?'reassign':'assign',i)}>{i.responder_id?'Reassign':'Assign'}</Button>}
    {can('update_incidents')&&activeIncident(i)&&<><Button className="secondary" onClick={()=>confirm(`Resolve ${i.reference}?`)&&void act(`/admin/incidents/${i.id}/resolve`,{method:'POST'},'Incident resolved.')}>Resolve</Button><Button className="danger-quiet" onClick={()=>confirm(`Cancel ${i.reference}?`)&&void act(`/admin/incidents/${i.id}/cancel`,{method:'POST'},'Incident cancelled.')}>Cancel</Button></>}
    {can('update_incidents')&&i.report?.status!=='reviewed'&&<Button className="quiet" onClick={()=>open('Review resolution report','review',i)}>Review report</Button>}
  </div>;
  const renderBody = () => {
    if (loading) return loading;
    if (errorBar && !data.length) return null;
    switch(page) {
      case 'overview': return overviewData ? <Overview model={overviewData} canViewIncidents={can('view_incidents')} canViewReports={can('view_reports')} canViewAudit={can('view_audit_logs')} canManageAutomation={session.account.role==='super_admin'} canAssign={can('assign_responders')} onPage={openPage} onFilter={openIncidentsWithFilter} onIncident={openIncidentDetails} onAssign={row=>open('Assign responder',row.responder_id?'reassign':'assign',row)} /> : loading;
      case 'incidents': return <Panel title="Incident queue" subtitle={`${filtered.length} of ${data.length} incidents`}><div className="filters"><label>Search<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Reference, type, description, location" /></label><label>Status<select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">All statuses</option>{statuses.map(x=><option key={x}>{x}</option>)}</select></label><label>Priority<select value={priorityFilter} onChange={e=>setPriorityFilter(e.target.value)}><option value="">All priorities</option>{['Critical','High','Medium','Low'].map(x=><option key={x}>{x}</option>)}</select></label><label>Category<select value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}><option value="">All categories</option>{[...new Set(data.map(x=>x.emergency_type).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select></label><Button className="quiet" onClick={()=>{setSearch('');setStatusFilter('');setPriorityFilter('');setCategoryFilter('');}}>Clear filters</Button></div><Table headers={['Incident','Priority','Status','Location','Reported','Actions']}>{filtered.map(i=><tr key={i.id}><td><b>{i.reference}</b><small>{i.emergency_type}</small></td><td><span className={`priority ${String(i.priority||'Normal').toLowerCase()}`}>{i.priority||'Normal'}</span></td><td><span className="status">{i.status}</span></td><td>{i.location_label||'Not provided'}</td><td>{stamp(i.created_at)}</td><td>{incidentActions(i)}</td></tr>)}</Table>{!filtered.length&&<Empty>No incidents match these filters.</Empty>}</Panel>;
      case 'responders': return <Panel title="Responder administration" subtitle="Account, availability, assignment, and invitation state." action={can('manage_responders')&&<Button className="primary" onClick={()=>open('Invite responder','invite')}>Invite responder</Button>}><div className="filters directory-filters"><label>Search<input aria-label="Search responders" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Name, email, capability, task"/></label><label>Availability<select aria-label="Filter responders" value={directoryStatus} onChange={e=>setDirectoryStatus(e.target.value)}><option value="">All responders</option><option value="available">Available</option><option value="busy">Busy</option><option value="unavailable">Unavailable or suspended</option><option value="invited">Invitation pending</option></select></label></div><Table headers={['Responder','Capabilities','Availability','Account / invitation','Active assignment','Actions']}>{filteredResponders.map(r=><tr key={r.id}><td><b>{r.display_name}</b><small>{r.email}</small></td><td>{(r.capabilities||[]).join(', ')}</td><td>{r.active_incident_id?'Busy':r.active&&r.available?'Available':'Unavailable'}</td><td>{r.active?'Active':'Suspended'} · {r.invitation_status||'—'}{r.invitation_expires_at&&<small>Expires {stamp(r.invitation_expires_at)}</small>}</td><td>{r.active_incident_id?(can('view_incidents')?<Button className="quiet small" onClick={()=>void openIncidentDetails({id:r.active_incident_id})}>{r.active_incident_reference||'Assigned incident'}</Button>:r.active_incident_reference||'Assigned incident'):'—'}{r.active_resource_name&&<small>{r.active_resource_name}</small>}</td><td><div className="actions">{can('manage_responders')&&<>{r.active&&<Button className="quiet" onClick={()=>open('Edit capabilities','capabilities',r)}>Capabilities</Button>}{r.active&&<Button className="quiet" onClick={()=>void act(`/admin/responders/${r.id}/availability`,{method:'PATCH',body:JSON.stringify({available:!r.available})},'Availability updated.')}>{r.available?'Set unavailable':'Set available'}</Button>}<Button className="quiet" onClick={()=>{if(!r.active||confirm(`Suspend ${r.display_name}? The API rejects suspension while they have an active task.`))void act(`/admin/users/${r.id}/active?active=${!r.active}`,{method:'PATCH'},'Account state updated.');}}>{r.active?'Suspend':'Activate'}</Button>{!r.active&&r.invitation_status!=='accepted'&&<Button className="quiet" onClick={()=>void act(`/admin/invitations/responders/${r.id}/resend`,{method:'POST'},'Invitation resent.')}>Resend invitation</Button>}</>}</div></td></tr>)}</Table>{!filteredResponders.length&&<Empty>No responders match these filters.</Empty>}</Panel>;
      case 'users': return <Panel title="User accounts" subtitle={`${filteredUsers.length} of ${data.length} public accounts.`}><div className="filters directory-filters"><label>Search<input aria-label="Search users" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Name or email"/></label><label>Status<select aria-label="Filter user account status" value={directoryStatus} onChange={e=>setDirectoryStatus(e.target.value)}><option value="">All accounts</option><option value="active">Active</option><option value="suspended">Suspended</option></select></label></div><Table headers={['Name','Email','Created','Status','Actions']}>{filteredUsers.map(u=><tr key={u.id}><td>{u.display_name}</td><td>{u.email}</td><td>{stamp(u.created_at)}</td><td>{u.active?'Active':'Suspended'}</td><td><div className="actions">{can('view_incidents')&&<Button className="quiet" onClick={()=>void openUserHistory(u)}>Incident history</Button>}{can('manage_users')&&<Button className="secondary" onClick={()=>confirm(`${u.active?'Suspend':'Activate'} ${u.email}?`)&&void act(`/admin/users/${u.id}/active?active=${!u.active}`,{method:'PATCH'},'Account status updated.')}>{u.active?'Suspend':'Activate'}</Button>}</div></td></tr>)}</Table>{!filteredUsers.length&&<Empty>No accounts match these filters.</Empty>}</Panel>;
      case 'resources': return <Panel title="Resource inventory" subtitle="Current quantities and active allocations." action={can('manage_resources')&&<Button className="primary" onClick={()=>open('Add resource','resource')}>Add resource</Button>}><Table headers={['Resource','Type','Available','Allocated','Quantity','Current allocation','Status','Actions']}>{data.map(r=><tr key={r.id}><td>{r.name}</td><td>{r.kind}</td><td>{r.available}</td><td>{r.allocated}</td><td>{r.quantity}</td><td>{(r.allocations||[]).length?(r.allocations||[]).map((a:Row)=><div key={a.incident_id}>{can('view_incidents')?<Button className="quiet small" onClick={()=>void openIncidentDetails({id:a.incident_id})}>{a.incident_reference||'Incident'}</Button>:<span>{a.incident_reference||'Incident'}</span>}<small>{a.responder_name||'Responder not available'}</small></div>):'—'}</td><td>{r.active?'Active':'Inactive'}</td><td>{can('manage_resources')&&<Button className="quiet" onClick={()=>open('Edit resource','resource',r)}>Edit</Button>}</td></tr>)}</Table>{!data.length&&<Empty>No resources configured.</Empty>}</Panel>;
      case 'reports': return <Reports api={api} canExport={can('export_reports')} canDrill={can('view_incidents')} onFilter={openIncidentsWithFilter} />;
      case 'historical': return <HistoricalPublicData model={data[0]||{}} api={api} canImport={session?.account.role==='super_admin'} onImported={model=>{setData([model]);setLastUpdated(new Date().toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' }));}} />;
      case 'audit': return <Panel title="Audit history" subtitle="Administrative actions recorded by the service."><Table headers={['Time','Action','Entity','Details','Actor']}>{data.map(x=><tr key={x.id}><td>{stamp(x.created_at)}</td><td>{x.action}</td><td>{x.entity_type} · {String(x.entity_id).slice(0,8)}</td><td>{JSON.stringify(x.details)}</td><td>{String(x.actor_id).slice(0,8)}</td></tr>)}</Table>{!data.length&&<Empty>No audit events.</Empty>}</Panel>;
      case 'coadmins': { const rows=data.filter(x=>(!directoryStatus||(directoryStatus==='active'?x.active:!x.active))&&(!directoryQuery||`${x.display_name} ${x.email}`.toLowerCase().includes(directoryQuery.toLowerCase()))); return <Panel title="Co-Admin access" subtitle="Only Super Admins can manage scoped administrators." action={<Button className="primary" onClick={()=>open('Create Co-Admin','coadmin')}>Create Co-Admin</Button>}><div className="filters directory-filters"><label>Search<input aria-label="Search Co-Admins" value={directoryQuery} onChange={e=>setDirectoryQuery(e.target.value)} placeholder="Name or email"/></label><label>Status<select aria-label="Filter Co-Admin status" value={directoryStatus} onChange={e=>setDirectoryStatus(e.target.value)}><option value="">All accounts</option><option value="active">Active</option><option value="suspended">Suspended</option></select></label></div><Table headers={['Name','Email','Access','Permissions','Actions']}>{rows.map(x=><tr key={x.id}><td>{x.display_name}</td><td>{x.email}</td><td>{x.active?'Active':'Suspended'}</td><td>{(x.permissions||[]).join(', ')||'None'}</td><td><div className="actions"><Button className="quiet" onClick={()=>open('Edit Co-Admin permissions','permissions',x)}>Permissions</Button><Button className="quiet" onClick={()=>confirm(`${x.active?'Revoke':'Restore'} ${x.email}?`)&&void act(`/admin/coadmins/${x.id}/active?active=${!x.active}`,{method:'PATCH'},'Co-Admin access updated.')}>{x.active?'Revoke':'Restore'}</Button></div></td></tr>)}</Table>{!rows.length&&<Empty>No Co-Admins match these filters.</Empty>}</Panel>; }
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

  return <div className="shell">
    <aside className={`sidebar${mobileMenuOpen?' menu-open':''}`}>
      <div className="sidebar-top">
        <a className="mobile-brand" href="#overview" onClick={event=>{event.preventDefault();openPage('overview')}}><img src={logoUrl} alt=""/>IERCS</a>
        <Button className="icon-button" aria-label={mobileMenuOpen?'Close navigation':'Open navigation'} aria-expanded={mobileMenuOpen} onClick={()=>setMobileMenuOpen(value=>!value)}>{mobileMenuOpen?'×':'☰'}</Button>
      </div>
      <a className="brand" href="#overview" onClick={event=>{event.preventDefault();openPage('overview')}}><img src={logoUrl} alt=""/><span><b>IERCS</b><small>Emergency coordination</small></span></a>
      <div className="workspace-chip"><span className="workspace-icon" aria-hidden="true">EC</span><span>Emergency operations<small>Coordination workspace</small></span></div>
      <nav aria-label="Operations pages"><span className="nav-caption">Operations</span>{visible.map(item=><Fragment key={item}>{item==='users'&&<span className="nav-caption">Administration</span>}<button className={page===item?'nav-item active':'nav-item'} aria-current={page===item?'page':undefined} onClick={()=>openPage(item)}><span className="nav-icon"><NavIcon page={item}/></span>{labels[item]}</button></Fragment>)}</nav>
      <div className="sidebar-foot"><span className="avatar">{session.account.display_name.split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase()}</span><span><b>{session.account.display_name}</b><small>{session.account.role==='super_admin'?'Super Admin':'Co-Admin'}</small></span><Button className="icon-button" aria-label="Sign out" onClick={()=>void logout()}>↗</Button></div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div className="topbar-start"><p className="eyebrow">EMERGENCY COORDINATION / OPERATIONS</p><h1>{labels[page]}</h1><p className="muted">{page==='historical'?'Historical earthquake and disaster-declaration records · not current incidents or dispatch activity.':overviewData?.dashboard?.synthetic_demo_records?`Synthetic demonstration data · ${overviewData.dashboard.synthetic_demo_records} records · not live emergencies.`:'Current coordination records from your service.'}</p></div>
        <div className="topbar-tools">
          {can('view_incidents')&&<label className="topbar-search" aria-label="Search incidents"><input type="search" value={globalQuery} onChange={event=>setGlobalQuery(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();submitGlobalSearch()}}} placeholder="Search incidents…" autoComplete="off"/></label>}
          <Button className="notification-shortcut" aria-label={`Notifications, ${overviewData?.notifications.filter(item=>!item.read).length||0} unread`} onClick={()=>openPage('notifications')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12h4"/></svg>{Boolean(overviewData?.notifications.some(item=>!item.read))&&<span className="notification-count">{overviewData?.notifications.filter(item=>!item.read).length}</span>}</Button>
          {lastUpdated&&<span className="last-updated">Updated {lastUpdated}</span>}
          <Button className="secondary icon-button refresh-button" aria-label="Refresh current page" onClick={()=>void run()}>↻</Button>
          {can('view_incidents')&&<Button className="primary header-incident-action" onClick={()=>openPage('incidents')}>Incident queue <span aria-hidden="true">→</span></Button>}
          <div className="profile-chip"><span className="profile-avatar" aria-hidden="true">{session.account.display_name.split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase()}</span><span className="profile-copy"><span>{session.account.display_name}</span><small>{session.account.role==='super_admin'?'Super Admin':'Co-Admin'}</small></span></div>
        </div>
      </header>
      {noticeBar}{invitationNotice}{errorBar}{renderBody()}
    </main>
    {dialog&&<div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setDialog(null)}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><div><p className="eyebrow">OPERATIONS</p><h2 id="modal-title">{dialog.title}</h2></div><Button className="icon-button" aria-label="Close dialog" onClick={()=>setDialog(null)}>×</Button></header>
      {dialog.kind==='details'?<div className="incident-details"><div className="detail-grid">{[['Status',dialog.row.status],['Priority',`${dialog.row.priority||'—'} · ${dialog.row.priority_reason||'No reason recorded'}`],['Location',dialog.row.location_label],['Location source',`${dialog.row.location_source||'Not provided'}${dialog.row.accuracy_m?` · ${dialog.row.accuracy_m} m accuracy`:''}`],['Responder',`${dialog.row.responder_name||'Unassigned'}${dialog.row.assignment_source?` · ${dialog.row.assignment_source==='automatic'?'Automatically assigned':'Manually assigned'}`:''}`],['Resource',dialog.row.resource_name||'None'],['Reported',stamp(dialog.row.created_at)],['Severity / urgency',`${dialog.row.severity} / ${dialog.row.urgency}`]].map(([k,v])=><div key={String(k)}><small>{k}</small><b>{v||'—'}</b></div>)}</div><div><h3>Original report</h3><p>{dialog.row.description}</p></div>{Object.keys(dialog.row.intake_data||{}).length>0&&<div><h3>Follow-up answers · user-reported</h3>{Object.entries(dialog.row.intake_data).map(([key,value])=><p key={key}><b>{key.replaceAll('_',' ')}:</b> {String(value||'Unknown / skipped')} <span className="muted">· user-reported</span></p>)}</div>}{dialog.row.analysis&&<div className="callout"><b>Decision support · human review required</b><p>{dialog.row.analysis.result?.summary||dialog.row.analysis.status}</p>{dialog.row.analysis.result?.explanation&&<p>{dialog.row.analysis.result.explanation}</p>}{dialog.row.analysis.result?.factual_details?.length>0&&<p><b>Quoted details:</b> {dialog.row.analysis.result.factual_details.map((x:Row)=>x.statement).join(' · ')}</p>}{dialog.row.analysis.result?.hazards_to_verify?.length>0&&<p><b>Hazards to verify:</b> {dialog.row.analysis.result.hazards_to_verify.map((x:Row)=>x.statement).join(' · ')}</p>}{dialog.row.analysis.result?.missing_information?.length>0&&<p><b>Missing details:</b> {dialog.row.analysis.result.missing_information.join(' · ')}</p>}<p className="muted">{dialog.row.analysis.provider||'Rules-based analysis'}{dialog.row.analysis.model?` · ${dialog.row.analysis.model}`:''} · attempts {dialog.row.analysis.attempt_count??0}</p>{['admin','super_admin'].includes(session.account.role)&&(dialog.row.analysis.last_error_type||dialog.row.analysis.status==='unavailable')&&<Button className="secondary" onClick={()=>void act(`/admin/incidents/${dialog.row.id}/analysis/retry`,{method:'POST'},'Analysis retry queued.')}>Retry analysis</Button>}</div>}{dialog.row.report&&<div><h3>Resolution report · {dialog.row.report.status}</h3><p><b>Outcome:</b> {dialog.row.report.content?.outcome}</p><p><b>Cause:</b> {dialog.row.report.content?.cause}</p><p><b>Limitations:</b> {(dialog.row.report.content?.evidence_and_limitations?.limitations||[]).join(' ')}</p><p className="muted">Sources: {dialog.row.report.source_records?.length||0} persisted records. This summary is not an independent investigation.</p>{dialog.row.report.status!=='reviewed'&&can('update_incidents')&&<Button className="secondary" onClick={()=>open('Review resolution report','review',dialog.row)}>Mark reviewed with note</Button>}</div>}<div><h3>Response history</h3>{dialog.row.updates?.length?dialog.row.updates.map((u:Row)=><article className="history-row" key={u.id}><b>{u.kind}{u.ai_assisted?' · AI-assisted, responder accepted':''}</b><p>{u.message}</p>{u.original_message&&<p className="muted">Original responder note: {u.original_message}</p>}<small>{stamp(u.created_at)}</small></article>):<Empty>No response updates.</Empty>}</div><footer className="modal-actions"><Button className="secondary" onClick={()=>setDialog(null)}>Close</Button></footer></div>:
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

function Overview({ model, canViewIncidents, canViewReports, canViewAudit, canManageAutomation, canAssign, onPage, onFilter, onIncident, onAssign }:{ model:OverviewModel; canViewIncidents:boolean; canViewReports:boolean; canViewAudit:boolean; canManageAutomation:boolean; canAssign:boolean; onPage:(page:Page)=>void; onFilter:(filter:string,value:string)=>void; onIncident:(row:Row)=>void; onAssign:(row:Row)=>void }) {
  const { dashboard, notifications, activity } = model;
  const incidents = model.incidents || [];
  const responders = model.responders || [];
  const analytics = model.analytics || {};
  const active = incidents.filter(activeIncident).sort((a,b)=>{
    const priority:Record<string,number>={Critical:0,High:1,Medium:2,Low:3};
    return (priority[a.priority]??4)-(priority[b.priority]??4)||Date.parse(b.created_at||'')-Date.parse(a.created_at||'');
  });
  const critical = active.filter(item=>['Critical','High'].includes(item.priority));
  const unassigned = active.filter(item=>item.status==='Unassigned'||!item.responder_id);
  const analysisRows = incidents.filter(item=>item.analysis);
  const analysisReady = analysisRows.filter(item=>item.analysis.status==='ready'&&!item.analysis.last_error_type).length;
  const analysisPending = analysisRows.filter(item=>['pending','processing'].includes(item.analysis.status)).length;
  const analysisFailedRows = analysisRows.filter(item=>item.analysis.status==='unavailable'||Boolean(item.analysis.last_error_type));
  const statuses = ['Unassigned','Assigned','Accepted','En Route','On Scene','Resolved','Cancelled'];
  const statusCounts:Record<string,number> = analytics.status_counts || incidents.reduce((counts:Record<string,number>,item)=>{counts[item.status]=(counts[item.status]||0)+1;return counts;},{});
  const maxStatus = Math.max(1,...statuses.map(status=>Number(statusCounts[status])||0));
  const available = responders.filter(item=>item.active&&item.available&&!item.active_incident_id).length;
  const busy = responders.filter(item=>item.active_incident_id).length;
  const unavailable = responders.filter(item=>!item.active||!item.available&&!item.active_incident_id).length;
  const responderTotal = available+busy+unavailable;
  const workload = Object.entries(analytics.assignments_per_responder||{}).map(([id,count])=>({id,name:responders.find(item=>item.id===id)?.display_name||'Responder record',count:Number(count)||0})).filter(item=>item.count>0).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name)).slice(0,5);
  const workloadMax = Math.max(1,...workload.map(item=>item.count));
  const unread = notifications.filter(item=>!item.read).length;
  return <>
    <div className="metric-grid metrics-primary">
      <button className="metric metric-action metric-yellow" onClick={()=>onPage('incidents')}><span>Active incidents</span><strong>{dashboard.active_incidents??'—'}</strong><small>{critical.length} high or critical open</small><i aria-hidden="true">→</i></button>
      <button className="metric metric-action" onClick={()=>onFilter('status','Unassigned')}><span>Unassigned</span><strong>{dashboard.unassigned??'—'}</strong><small>Open incidents awaiting a responder</small><i aria-hidden="true">→</i></button>
      <button className="metric metric-action" onClick={()=>onPage('responders')}><span>Responders available</span><strong>{dashboard.responders_available??'—'}</strong><small>Current service availability</small><i aria-hidden="true">→</i></button>
      <button className="metric metric-action" onClick={()=>onPage('notifications')}><span>Unread notifications</span><strong>{unread}</strong><small>In-app records for this admin account</small><i aria-hidden="true">→</i></button>
    </div>
    {canViewIncidents&&<Panel title="Incident status pipeline" subtitle="Current status counts returned by service analytics. Select a stage to filter the incident queue.">
      <div className="lifecycle-stages">{statuses.map(status=><button key={status} className={`lifecycle-stage ${status==='Unassigned'?'stage-attention':status==='Resolved'?'stage-complete':status==='Cancelled'?'stage-neutral':'stage-progress'}`} aria-label={`Filter incidents with status ${status}: ${Number(statusCounts[status])||0}`} onClick={()=>onFilter('status',status)}><span className="lifecycle-label">{status}</span><i className="lifecycle-track"><em style={{width:`${100*(Number(statusCounts[status])||0)/maxStatus}%`}}/></i><b>{Number(statusCounts[status])||0}</b></button>)}</div>
    </Panel>}
    <div className="dashboard-grid dashboard-redesign">
      {canViewIncidents&&<Panel title="Priority incidents" subtitle="Open incidents ordered by priority and report time." action={<Button className="quiet small" onClick={()=>onPage('incidents')}>All incidents →</Button>}>
        {active.length?<div className="compact-incident-list">{active.slice(0,5).map(item=><article className="compact-incident" key={item.id}><button className="compact-incident-main" onClick={()=>onIncident(item)}><span className="compact-incident-top"><b>{item.reference}</b><span className={`priority ${String(item.priority||'Normal').toLowerCase()}`}>{item.priority||'Normal'}</span><span className="compact-status">{item.status}</span></span><span className="compact-incident-category">{item.emergency_type}{item.severity?` · Severity ${item.severity}`:''}</span><small>{item.responder_name?`Responder: ${item.responder_name}`:'Awaiting responder'} · {stamp(item.created_at)}</small></button>{canAssign&&<Button className="compact-assign" onClick={()=>onAssign(item)}>{item.responder_id?'Reassign':'Assign'}</Button>}</article>)}</div>:<Empty>No active incidents.</Empty>}
      </Panel>}
      {canViewIncidents&&<Panel title="AI analysis activity" subtitle="Persisted analysis records; AI suggestions never dispatch responders." action={canManageAutomation&&<Button className="quiet small" onClick={()=>onPage('automation')}>Policy →</Button>}>
        <div className="ai-counts"><button onClick={()=>onPage('incidents')}><b>{analysisReady}</b><span>Analysis ready</span></button><button onClick={()=>onPage('incidents')}><b>{analysisPending}</b><span>Pending / processing</span></button><button className={analysisFailedRows.length?'ai-failure':''} onClick={()=>onPage('incidents')}><b>{analysisFailedRows.length}</b><span>Unavailable</span></button></div>
        {analysisFailedRows.length?<div className="ai-exceptions">{analysisFailedRows.slice(0,3).map(item=><button key={item.id} onClick={()=>onIncident(item)}><span><b>{item.reference}</b><small>{item.analysis.last_error_type||item.analysis.validation_outcome||item.analysis.status}</small></span><span aria-hidden="true">→</span></button>)}</div>:<p className="metric-footnote">No persisted analysis failures are currently recorded.</p>}
        <div className="responder-mini"><div className="responder-mini-head"><b>Responder availability</b><span>{available} available · {busy} busy</span></div><div className="availability-bar" role="img" aria-label={`${available} available, ${busy} busy, ${unavailable} unavailable`}><i className="available-segment" style={{width:`${responderTotal?100*available/responderTotal:0}%`}}/><i className="busy-segment" style={{width:`${responderTotal?100*busy/responderTotal:0}%`}}/><i className="unavailable-segment" style={{width:`${responderTotal?100*unavailable/responderTotal:0}%`}}/></div>
          {canViewReports?(workload.length?<div className="workload-list">{workload.map(item=><div className="workload-row" key={item.id}><span>{item.name}</span><i><b style={{width:`${100*item.count/workloadMax}%`}}/></i><strong>{item.count}</strong></div>)}</div>:<p className="metric-footnote">No assignment records in this period.</p>):<p className="metric-footnote">Assignment history is outside your report permissions.</p>}
        </div>
      </Panel>}
      {canViewIncidents&&<Panel title="Coordinator attention" subtitle="Priority and assignment exceptions from current service records.">
        <div className="attention-summary"><button onClick={()=>onFilter('status','Unassigned')}><span><i className="attention-indicator yellow-indicator"/><b>Unassigned</b></span><strong>{dashboard.unassigned??0}</strong><small>Open incidents awaiting a responder</small></button><button onClick={()=>onFilter('priority','Critical')}><span><i className="attention-indicator red-indicator"/><b>High priority</b></span><strong>{critical.length}</strong><small>Active high or critical incidents</small></button><button onClick={()=>onPage('incidents')}><span><i className={`attention-indicator ${analysisFailedRows.length?'red-indicator':'neutral-indicator'}`}/><b>Analysis unavailable</b></span><strong>{analysisFailedRows.length}</strong><small>Persisted records that need review</small></button></div>
        {unassigned.length?<div className="attention-list">{unassigned.slice(0,4).map(item=><button className="attention-row" key={item.id} onClick={()=>onIncident(item)}><i className={`attention-priority priority-${String(item.priority||'').toLowerCase()}`}/><span className="attention-copy"><b>{item.reference} · {item.emergency_type}</b><small>{item.status}{item.responder_name?` · ${item.responder_name}`:' · Unassigned'}</small></span><span className="attention-tag">{item.priority||'Normal'}</span></button>)}</div>:<p className="metric-footnote">No open assignment exceptions.</p>}
      </Panel>}
      {canViewAudit&&<Panel title="Recent administrative activity" subtitle="Latest records from the service audit log." action={<Button className="quiet small" onClick={()=>onPage('audit')}>Audit history →</Button>}>
        {activity.length?<div className="activity-list">{activity.map(item=><article className="activity-item" key={item.id}><i className="activity-dot"/><div><div className="activity-main">{String(item.action||'').replaceAll('_',' ')} <span className="muted">· {item.entity_type}</span></div><div className="activity-meta">{stamp(item.created_at)} · {String(item.actor_id||'').slice(0,8)}</div></div></article>)}</div>:<Empty>No activity has been recorded yet.</Empty>}
      </Panel>}
    </div>
  </>;
}

function PermissionChoices({initial=[]}:{initial?:string[]}) { return <fieldset><legend>Permissions</legend><div className="permission-grid">{permissions.map(([key,label])=><label key={key} className="check"><input type="checkbox" name="permissions" value={key} defaultChecked={initial.includes(key)}/>{label}</label>)}</div></fieldset>; }
function AssignmentFields({api,incident}:{api:<T,>(path:string, options?:any)=>Promise<T>;incident:Row}) {
  const [choices,setChoices]=useState<Row[]>([]); const [resources,setResources]=useState<Row[]>([]); const [error,setError]=useState('');
  useEffect(()=>{api<Row>(`/admin/incidents/${incident.id}/recommendations`).then(result=>{setChoices(result.eligible_responders||[]);setResources(result.compatible_resources||[]);}).catch(e=>setError(failText(e)));},[api,incident.id]);
  return <>{error&&<p className="error" role="alert">{error}</p>}<p className="muted">Recommendations are supplied by the API; assignment eligibility is checked again by the backend.</p><label>Responder<select name="responder_id" required defaultValue=""><option value="" disabled>Select responder</option>{choices.map((x:Row)=><option key={x.responder_id} value={x.responder_id}>{x.display_name} · score {x.score}</option>)}</select></label><label>Resource<select name="resource_id" defaultValue=""><option value="">No resource</option>{resources.map((r:Row)=><option key={r.id} value={r.id}>{r.name} · {r.available} available</option>)}</select></label></>;
}
function Reports({api,canExport,canDrill,onFilter}:{api:<T,>(path:string,options?:any)=>Promise<T>;canExport:boolean;canDrill:boolean;onFilter:(filter:string,value:string)=>void}) {
  const [days,setDays]=useState(30);const [report,setReport]=useState<Row|null>(null);const [error,setError]=useState('');
  useEffect(()=>{api<Row>(`/admin/analytics?days=${days}`).then(setReport).catch(e=>setError(failText(e)));},[api,days]);
  const exportData=()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`operations-summary-${days}days.json`;a.click();URL.revokeObjectURL(url);};
  const series=Array.from({length:days},(_,index)=>{const date=new Date();date.setUTCHours(0,0,0,0);date.setUTCDate(date.getUTCDate()-days+index+1);const key=date.toISOString().slice(0,10);return {date:key,count:Number(report?.daily_incident_counts?.[key])||0};});
  const values=series.map(point=>point.count), max=Math.max(1,...values), points=values.map((value,index)=>`${18+index*604/Math.max(1,values.length-1)},${162-(value/max)*144}`).join(' ');
  const categoryRows=Object.entries(report?.category_counts||{}).filter(([,value])=>Number(value)>0).sort((a,b)=>Number(b[1])-Number(a[1]));
  const totalCategories=categoryRows.reduce((sum,[,value])=>sum+Number(value),0);let offset=0;
  const donut=categoryRows.map(([name,value],index)=>{const fraction=Number(value)/Math.max(1,totalCategories),dash=fraction*2*Math.PI*40,current=offset;offset+=dash;return <circle key={name} className={`donut-segment swatch-${index%6}`} cx="50" cy="50" r="40" fill="none" strokeWidth="14" strokeDasharray={`${dash} ${2*Math.PI*40-dash}`} strokeDashoffset={-current} transform="rotate(-90 50 50)"/>;});
  const statusRows=Object.entries(report?.status_counts||{}).sort((a,b)=>Number(b[1])-Number(a[1]));
  return <Panel title="Operational reports" subtitle={report?.data_note||'Descriptive aggregates from persisted service records.'} action={<div className="actions"><label className="compact-label">Period<select aria-label="Report period" value={days} onChange={e=>setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select></label>{canExport&&<Button className="secondary" onClick={exportData}>Export JSON</Button>}</div>}>{error&&<p className="error" role="alert">{error}</p>}{report&&<><div className="metric-grid">{[['Incidents',report.incident_count],['Assignments',report.assignment_count],['Completed assignments',report.completed_assignment_count],['Resources allocated',report.resource_units_allocated]].map(([k,v])=><article className="metric" key={String(k)}><span>{k}</span><strong>{v??'—'}</strong><small>{k==='Resources allocated'?'Current snapshot':`Last ${days} days`}</small></article>)}</div><section className="report-trend"><div className="panel-head"><div><h3>Daily submissions</h3><p className="muted">Incident creation date · UTC</p></div><b>{report.incident_count} <small>incidents</small></b></div>{values.some(Boolean)?<div className="trend-chart"><svg viewBox="0 0 640 180" role="img" aria-label={`Daily incident submissions for the last ${days} days: ${series.map(point=>`${point.date}: ${point.count}`).join('; ')}`} preserveAspectRatio="none"><polyline points={points} fill="none" stroke="#2878d0" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg><div className="chart-labels"><span>{series[0]?.date}</span><span>{series[Math.floor((days-1)/2)]?.date}</span><span>{series[days-1]?.date}</span></div></div>:<Empty>No incident submissions in this period.</Empty>}</section><div className="report-grid"><section><h3>Incidents by status</h3>{statusRows.length?statusRows.map(([name,value])=>{const row=<><span>{name}</span><i><b style={{width:`${100*Number(value)/Math.max(1,...statusRows.map(([,v])=>Number(v)))}%`}}/></i><strong>{String(value)}</strong></>;return canDrill?<button className="report-filter-row" key={name} onClick={()=>onFilter('status',name)}>{row}</button>:<div className="report-filter-row" key={name}>{row}</div>}):<Empty>No incident status data in this period.</Empty>}</section><section><h3>Incident categories</h3>{categoryRows.length?<div className="category-visual"><svg className="donut-chart" viewBox="0 0 100 100" role="img" aria-label={`Incident categories: ${categoryRows.map(([name,value])=>`${name}, ${value}`).join('; ')}`}>{donut}<text x="50" y="47" textAnchor="middle" className="donut-total">{totalCategories}</text><text x="50" y="59" textAnchor="middle" className="donut-caption">incidents</text></svg><ul className="category-list">{categoryRows.map(([name,value],index)=><li key={name}>{canDrill?<button className="category-filter" onClick={()=>onFilter('category',name)}><i className={`category-swatch swatch-${index%6}`}/><span>{name}</span><b>{String(value)}</b><small>{Math.round(Number(value)*100/totalCategories)}%</small></button>:<div className="category-filter"><i className={`category-swatch swatch-${index%6}`}/><span>{name}</span><b>{String(value)}</b><small>{Math.round(Number(value)*100/totalCategories)}%</small></div>}</li>)}</ul></div>:<Empty>No category data for this period.</Empty>}</section></div><div className="metric-grid"><article className="metric"><span>Average assignment delay</span><strong>{report.average_assignment_delay_minutes??'—'} min</strong><small>Incident creation to each recorded assignment</small></article><article className="metric"><span>Assignment to completion</span><strong>{report.average_assignment_to_completion_minutes??'—'} min</strong><small>Assignment to completion; not travel or arrival time</small></article></div><p className="muted">No forecasts or dispatch recommendations are shown. Resource allocation is a current snapshot.</p></>}</Panel>;
}

function HistoricalPublicData({model,api,canImport,onImported}:{model:Row;api:<T,>(path:string,options?:any)=>Promise<T>;canImport:boolean;onImported:(model:Row)=>void}) {
  const [dataset,setDataset]=useState<'earthquakes'|'fema'>('earthquakes');
  const [start,setStart]=useState(()=>String(model.selected_range?.start||'').slice(0,10));
  const [end,setEnd]=useState(()=>String(model.selected_range?.end||'').slice(0,10));
  const [category,setCategory]=useState('');
  const [locationQuery,setLocationQuery]=useState('');
  const [uploading,setUploading]=useState(false);
  const [uploadError,setUploadError]=useState('');
  const [uploadResult,setUploadResult]=useState<Row|null>(null);
  useEffect(()=>{
    const refreshedStart=String(model.selected_range?.start||'').slice(0,10);
    const refreshedEnd=String(model.selected_range?.end||'').slice(0,10);
    if(refreshedStart)setStart(refreshedStart);
    if(refreshedEnd)setEnd(refreshedEnd);
  },[model.selected_range?.start,model.selected_range?.end]);
  const earthquakes:Row[]=model.earthquakes?.records||[];
  const declarations:Row[]=model.fema?.records||[];
  const inRange=(value:string)=>{const day=String(value||'').slice(0,10);return (!start||day>=start)&&(!end||day<=end);};
  const magnitudeCategory=(value:number)=>value<4?'<4.0':value<5?'4.0–4.9':value<6?'5.0–5.9':'6.0+';
  const quakeRangeRows=earthquakes.filter(row=>inRange(row.event_time));
  const locatedQuakes=quakeRangeRows.filter(row=>!locationQuery||`${row.place||''} ${row.location||''} ${row.country||''} ${row.continent||''}`.toLowerCase().includes(locationQuery.toLowerCase()));
  const filteredQuakes=locatedQuakes.filter(row=>!category||magnitudeCategory(Number(row.magnitude))===category);
  const femaRangeRows=declarations.filter(row=>inRange(row.declaration_date));
  const femaRows=femaRangeRows.filter(row=>!category||row.incident_type===category);
  const quakeMonths=Object.entries(locatedQuakes.reduce((counts:Record<string,number>,row)=>{const month=String(row.event_time).slice(0,7);counts[month]=(counts[month]||0)+1;return counts;},{})).sort(([a],[b])=>a.localeCompare(b));
  const femaTypes=Object.entries(femaRangeRows.reduce((counts:Record<string,number>,row)=>{const type=row.incident_type||'Unspecified';counts[type]=(counts[type]||0)+1;return counts;},{})).sort((a,b)=>Number(b[1])-Number(a[1]));
  const magnitudeRows=Object.entries(quakeRangeRows.reduce((counts:Record<string,number>,row)=>{const key=magnitudeCategory(Number(row.magnitude));counts[key]=(counts[key]||0)+1;return counts;},{'<4.0':0,'4.0–4.9':0,'5.0–5.9':0,'6.0+':0}));
  const maxMonth=Math.max(1,...quakeMonths.map(([,count])=>Number(count)));
  const maxType=Math.max(1,...femaTypes.map(([,count])=>Number(count)));
  const sourceRows:Row[]=model.sources||[];
  const stale=(value:string|null)=>!value||Date.now()-new Date(value).getTime()>48*60*60*1000;
  const typeOptions=dataset==='earthquakes'?['<4.0','4.0–4.9','5.0–5.9','6.0+']:Object.keys(femaRangeRows.reduce((items:Record<string,boolean>,row)=>{if(row.incident_type)items[row.incident_type]=true;return items;},{}));
  const femaYears=Object.entries(femaRangeRows.reduce((counts:Record<string,number>,row)=>{const year=String(row.declaration_date).slice(0,4);counts[year]=(counts[year]||0)+1;return counts;},{})).sort(([a],[b])=>a.localeCompare(b));
  const femaIncidentYears=Object.entries(femaRangeRows.reduce((counts:Record<string,number>,row)=>{if(row.incident_begin_date){const year=String(row.incident_begin_date).slice(0,4);counts[year]=(counts[year]||0)+1;}return counts;},{})).sort(([a],[b])=>a.localeCompare(b));
  const femaYearState=Object.entries(femaRangeRows.reduce((counts:Record<string,number>,row)=>{const key=`${String(row.declaration_date).slice(0,4)} · ${row.state||'Unknown state'}`;counts[key]=(counts[key]||0)+1;return counts;},{})).sort((a,b)=>Number(b[1])-Number(a[1]));
  const femaAreas=Object.entries(femaRangeRows.reduce((counts:Record<string,number>,row)=>{const area=`${row.state||'Unknown state'} · ${row.designated_area||'Area not supplied'}`;counts[area]=(counts[area]||0)+1;return counts;},{})).sort((a,b)=>Number(b[1])-Number(a[1]));
  const femaTypesByDeclaration=femaRangeRows.reduce((counts:Record<string,number>,row)=>{counts[row.declaration_type]=(counts[row.declaration_type]||0)+1;return counts;},{});
  const femaStates=femaRangeRows.reduce((counts:Record<string,number>,row)=>{counts[row.state]=(counts[row.state]||0)+1;return counts;},{});
  const points=filteredQuakes.filter(row=>Number.isFinite(Number(row.longitude))&&Number.isFinite(Number(row.latitude)));
  const tsunamiCount=locatedQuakes.filter(row=>row.tsunami===true).length;
  const depths=locatedQuakes.filter(row=>Number.isFinite(Number(row.depth_km)));
  const maxDepth=Math.max(1,...depths.map(row=>Number(row.depth_km)));
  const uploadFiles=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setUploadError('');setUploadResult(null);
    const form=new FormData(event.currentTarget);
    const selectedFile=(value:FormDataEntryValue|null):value is File=>typeof value==='object'&&value!==null&&'name' in value&&'size' in value;
    if(!selectedFile(form.get('fema_file'))||!selectedFile(form.get('earthquake_file'))){setUploadError('Select both dataset files before importing.');return;}
    setUploading(true);
    try{const result=await api<Row>('/admin/public-disaster-data/import',{method:'POST',body:form});const refreshed=await api<Row>('/admin/public-disaster-data');setUploadResult(result);onImported(refreshed);}
    catch(error){setUploadError(failText(error));}finally{setUploading(false);}
  };
  return <div className="historical-page">
    <Panel title="Historical/Public Disaster Data" subtitle="Separate historical earthquake and disaster-declaration records. These records are not active incidents, dispatches, or emergency alerts." action={<span className="historical-scope">Global earthquake records · U.S. declaration rows</span>}>
      <div className="source-grid">{sourceRows.map(source=><article className="source-card" key={source.id}><div><b>{source.name}</b><span className={source.last_error||(!source.source_filename&&stale(source.last_success_at))?'sync-state stale':'sync-state'}>{source.last_error?'Import needs attention':source.source_filename?'User-provided file':source.last_success_at?stale(source.last_success_at)?'Data may be stale':'Recently synchronized':'Not synchronized'}</span></div><p>{source.scope} · {Number(source.record_count||0).toLocaleString()} stored for this view</p><small>Imported window: {source.range_start?String(source.range_start).slice(0,10):'—'} to {source.range_end?String(source.range_end).slice(0,10):'—'}</small><small>Last successful import: {source.last_success_at?stamp(source.last_success_at):'Not available'}{source.last_error?' · Latest attempt failed':''}</small>{source.source_filename&&<small>File: {source.source_filename}</small>}{source.was_limited&&<small className="sync-state stale">Configured result limit reached; data may be incomplete.</small>}{source.url?<a href={source.url} target="_blank" rel="noreferrer">Official source ↗</a>:<small>Source provided in uploaded file</small>}<small>{source.attribution}</small></article>)}</div>
      {canImport&&<Panel title="Import owner-provided datasets" subtitle="Imports are kept in historical tables, separate from operational incidents and dispatch."><form onSubmit={event=>void uploadFiles(event)}><label>Disaster declarations ZIP<input name="fema_file" type="file" accept=".zip,application/zip" required/></label><label>Earthquake CSV<input name="earthquake_file" type="file" accept=".csv,text/csv" required/></label><Button className="primary" disabled={uploading}>{uploading?'Validating and importing…':'Import both datasets'}</Button></form>{uploadError&&<p className="error" role="alert">{uploadError}</p>}{uploadResult&&<p className="success" role="status">Import complete. Inserted, updated, skipped, and rejected row counts are available below.</p>}{uploadResult&&<pre className="import-result">{JSON.stringify(uploadResult.results,null,2)}</pre>}</Panel>}
      <div className="historical-filter"><label>From<input aria-label="Historical start date" type="date" value={start} onChange={event=>setStart(event.target.value)}/></label><label>To<input aria-label="Historical end date" type="date" value={end} onChange={event=>setEnd(event.target.value)}/></label><label>Dataset<select aria-label="Historical dataset" value={dataset} onChange={event=>{setDataset(event.target.value as 'earthquakes'|'fema');setCategory('');}}><option value="earthquakes">Earthquakes</option><option value="fema">Disaster declarations</option></select></label><label>Magnitude / type<select aria-label="Historical category" value={category} onChange={event=>setCategory(event.target.value)}><option value="">All categories</option>{typeOptions.map(value=><option key={value}>{value}</option>)}</select></label>{dataset==='earthquakes'&&<label>Location<input aria-label="Earthquake location filter" value={locationQuery} onChange={event=>setLocationQuery(event.target.value)} placeholder="Country, place, or region"/></label>}</div>
      <p className="historical-note" role="note">{model.data_note||'Historical public records only. Not operational emergency activity.'} {model.records_limited&&'The current response is capped; counts and rows may be incomplete.'}</p>
    </Panel>
    {dataset==='earthquakes'?<>
      <div className="metric-grid historical-metrics"><article className="metric"><span>Earthquakes in selected range</span><strong>{filteredQuakes.length.toLocaleString()}</strong><small>Imported historical records · filtered</small></article><article className="metric"><span>Magnitude 4+</span><strong>{locatedQuakes.filter(row=>Number(row.magnitude)>=4).length.toLocaleString()}</strong><small>Events in selected dates and location</small></article><article className="metric"><span>Tsunami flags</span><strong>{tsunamiCount.toLocaleString()}</strong><small>Source-record flags; not proof of tsunami impact</small></article></div>
      <div className="report-grid historical-charts"><section><h3>Monthly earthquake counts</h3>{quakeMonths.length?<div className="historical-bars" role="img" aria-label="Earthquake event counts by month">{quakeMonths.map(([month,count])=><div className="historical-bar" key={month} title={`${month}: ${count}`}><i style={{height:`${Math.max(3,100*Number(count)/maxMonth)}%`}}/><small>{month.slice(2)}</small></div>)}</div>:<Empty>No imported earthquake data for this range.</Empty>}</section><section><h3>Distribution by magnitude</h3>{magnitudeRows.some(([,value])=>Number(value)>0)?magnitudeRows.map(([name,value])=><div className="historical-count-row" key={name}><span>{name}</span><i><b style={{width:`${100*Number(value)/Math.max(1,...magnitudeRows.map(([,n])=>Number(n)))}%`}}/></i><strong>{Number(value).toLocaleString()}</strong></div>):<Empty>No magnitude records for this range.</Empty>}</section></div>
      <Panel title="Global event coordinates" subtitle="Equirectangular longitude/latitude plot; each dot is an imported USGS event, not an operational location.">{points.length?<svg className="earthquake-plot" viewBox="0 0 360 180" role="img" aria-label={`${points.length} earthquake event coordinates plotted globally`}><path className="plot-grid" d="M0 45H360M0 90H360M0 135H360M90 0V180M180 0V180M270 0V180"/>{points.map(row=><circle key={row.id} cx={(Number(row.longitude)+180)} cy={(90-Number(row.latitude))} r={Math.max(1.5,Math.min(5,Number(row.magnitude)))} className={Number(row.magnitude)>=6?'quake-dot major':'quake-dot'}><title>{`${row.place||'Earthquake'} · magnitude ${row.magnitude}`}</title></circle>)}</svg>:<Empty>No plotted events in the selected range.</Empty>}</Panel>
      <Panel title="Magnitude versus depth" subtitle="Each point is an imported historical earthquake; depth and magnitude use the source file values.">{depths.length?<svg className="earthquake-plot" viewBox="0 0 360 180" role="img" aria-label={`${depths.length} earthquake magnitude versus depth points`}>{[0,1,2,3].map(i=><path key={i} className="plot-grid" d={`M0 ${i*60}H360`}/>)}{depths.map(row=><circle key={row.id} cx={Math.min(350,Number(row.magnitude)*35)} cy={175-Number(row.depth_km)/maxDepth*165} r="2.5" className="quake-dot"><title>{`Magnitude ${row.magnitude}; depth ${row.depth_km} km`}</title></circle>)}</svg>:<Empty>No depth values in this date and location range.</Empty>}</Panel>
      <Panel title="Earthquake events" subtitle={`${filteredQuakes.length.toLocaleString()} imported rows in the selected range; showing up to 50.`}><Table headers={['Magnitude','Place','Event time','Depth','Coordinates','Tsunami flag','Source']}>{filteredQuakes.slice(0,50).map(row=><tr key={row.id}><td><b>{Number(row.magnitude).toFixed(1)}</b></td><td>{row.place||'Place not supplied'}</td><td>{stamp(row.event_time)}</td><td>{row.depth_km==null?'—':`${row.depth_km} km`}</td><td>{Number(row.latitude).toFixed(3)}, {Number(row.longitude).toFixed(3)}</td><td>{row.tsunami===true?'Flagged':row.tsunami===false?'No flag':'Not supplied'}</td><td>{row.event_url?<a href={row.event_url} target="_blank" rel="noreferrer">USGS event ↗</a>:'Uploaded file'}</td></tr>)}</Table>{!filteredQuakes.length&&<Empty>No earthquake records match these filters.</Empty>}</Panel>
    </>:<>
      <div className="metric-grid historical-metrics"><article className="metric"><span>Declaration-area rows</span><strong>{femaRows.length.toLocaleString()}</strong><small>One row per state/county area in the source</small></article><article className="metric"><span>Unique declaration numbers</span><strong>{new Set(femaRows.map(row=>row.disaster_number)).size.toLocaleString()}</strong><small>A declaration may include several designated areas</small></article><article className="metric"><span>Disaster types</span><strong>{femaTypes.length}</strong><small>Across the selected date range</small></article></div>
      <div className="report-grid historical-charts"><section><h3>Declarations by year</h3>{femaYears.length?<div className="historical-bars" role="img" aria-label="FEMA declaration rows by year">{femaYears.map(([year,count])=><div className="historical-bar" key={year} title={`${year}: ${count}`}><i style={{height:`${Math.max(3,100*Number(count)/Math.max(1,...femaYears.map(([,n])=>Number(n))))}%`}}/><small>{year}</small></div>)}</div>:<Empty>No imported FEMA data for this range.</Empty>}</section><section><h3>Declarations by incident type</h3>{femaTypes.length?femaTypes.slice(0,12).map(([name,value])=><div className="historical-count-row" key={name}><span>{name}</span><i><b style={{width:`${100*Number(value)/maxType}%`}}/></i><strong>{Number(value).toLocaleString()}</strong></div>):<Empty>No FEMA declaration types for this range.</Empty>}</section></div>
      <div className="report-grid historical-charts"><section><h3>Incidents by start year</h3>{femaIncidentYears.length?<div className="historical-bars" role="img" aria-label="Disaster declaration area records by incident start year">{femaIncidentYears.map(([year,count])=><div className="historical-bar" key={year} title={`${year}: ${count}`}><i style={{height:`${Math.max(3,100*Number(count)/Math.max(1,...femaIncidentYears.map(([,n])=>Number(n))))}%`}}/><small>{year}</small></div>)}</div>:<Empty>No supplied incident start dates in this range.</Empty>}</section><section><h3>Most represented designated areas</h3>{femaAreas.length?femaAreas.slice(0,12).map(([name,value])=><div className="historical-count-row" key={name}><span>{name}</span><i/><strong>{Number(value).toLocaleString()}</strong></div>):<Empty>No geographic-area values in this range.</Empty>}</section></div>
      <section className="report-grid"><section><h3>By declaration type</h3>{Object.entries(femaTypesByDeclaration).map(([name,value])=><div className="historical-count-row" key={name}><span>{name}</span><i/><strong>{Number(value).toLocaleString()}</strong></div>)}</section><section><h3>Most represented states</h3>{Object.entries(femaStates).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,12).map(([name,value])=><div className="historical-count-row" key={name}><span>{name}</span><i/><strong>{Number(value).toLocaleString()}</strong></div>)}</section></section>
      <Panel title="Assistance programs" subtitle="Counts reflect Yes flags in the uploaded declaration-area rows; a declaration number can cover multiple areas."><div className="report-grid">{[['Individual Assistance','individual_assistance'],['Individuals & Households','individuals_households_program'],['Public Assistance','public_assistance'],['Hazard Mitigation','hazard_mitigation']].map(([label,key])=><div className="historical-count-row" key={key}><span>{label}</span><i/><strong>{femaRangeRows.filter(row=>row[key]===true).length.toLocaleString()}</strong></div>)}</div></Panel>
      <Panel title="Declaration counts by year and state" subtitle="Counts are declaration-area rows, grouped from the imported source records."><Table headers={['Year · state','Area rows']}>{femaYearState.slice(0,50).map(([name,count])=><tr key={name}><td>{name}</td><td>{Number(count).toLocaleString()}</td></tr>)}</Table>{!femaYearState.length&&<Empty>No state/year records in this range.</Empty>}</Panel>
      <Panel title="Disaster declaration-area records" subtitle={`${femaRows.length.toLocaleString()} rows; repeated disaster numbers represent designated county/area rows.`}><Table headers={['Declaration number','Declaration','Type','State / county','Disaster type','Incident dates','Declared','Closed','Source']}>{femaRows.slice(0,50).map(row=><tr key={row.id}><td>{row.disaster_number}</td><td><b>{row.declaration_string||row.title||'—'}</b></td><td>{row.declaration_type}</td><td>{row.state}{row.designated_area?` · ${row.designated_area}`:''}</td><td>{row.incident_type||'—'}</td><td>{row.incident_begin_date?stamp(row.incident_begin_date).split(',')[0]:'—'} – {row.incident_end_date?stamp(row.incident_end_date).split(',')[0]:'Not supplied'}</td><td>{stamp(row.declaration_date)}</td><td>{row.close_date?stamp(row.close_date).split(',')[0]:'—'}</td><td>{row.dataset_source==='uploaded_fema_declarations'?'Uploaded file':<a href={sourceRows.find(source=>source.id===row.dataset_source)?.url} target="_blank" rel="noreferrer">FEMA data ↗</a>}</td></tr>)}</Table>{!femaRows.length&&<Empty>No disaster declarations match these filters.</Empty>}</Panel>
    </>}
  </div>;
}
