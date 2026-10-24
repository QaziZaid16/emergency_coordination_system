/* Website-only dashboard presentation and analytics helpers. The API remains the source of truth. */
(() => {
  const dateKey = date => date.toISOString().slice(0, 10);
  const normalizeDailyCounts = (source, days, today = new Date()) => {
    const data = source || {};
    return Array.from({ length: days }, (_, index) => {
      const date = new Date(today);
      date.setUTCHours(0, 0, 0, 0);
      date.setUTCDate(date.getUTCDate() - days + index + 1);
      const key = dateKey(date);
      return { date: key, count: Math.max(0, Number(data[key]) || 0) };
    });
  };
  const filterIncidents = (rows, filters = {}) => rows.filter(item => {
    const query = String(filters.query || '').trim().toLowerCase();
    const haystack = [item.reference, item.emergency_type, item.description, item.location_label,
      item.responder_name, item.status, item.priority].join(' ').toLowerCase();
    return (!query || haystack.includes(query)) && (!filters.status || item.status === filters.status) &&
      (!filters.priority || item.priority === filters.priority) &&
      (!filters.category || item.emergency_type === filters.category);
  });
  const chartPoints = (values, width = 640, height = 180, pad = 18) => {
    if (!values.length) return '';
    const max = Math.max(1, ...values);
    return values.map((value, index) => `${pad + index * (width - pad * 2) / Math.max(1, values.length - 1)},${height - pad - (value / max) * (height - pad * 2)}`).join(' ');
  };
  const categorySegments = (rows, total) => {
    const circumference = 2 * Math.PI * 40;
    let offset = 0;
    return rows.map(([name, value]) => {
      const fraction = total > 0 ? Math.max(0, Number(value) || 0) / total : 0;
      const segment = { name, value: Number(value) || 0, percentage: total > 0 ? Math.round(fraction * 100) : 0,
        dash: fraction * circumference, offset: offset === 0 ? 0 : -offset };
      offset += segment.dash;
      return segment;
    });
  };
  const summarizeAnalysis = rows => {
    const records = rows.filter(item => item.analysis);
    return {
      ready: records.filter(item => item.analysis.status === 'ready' && !item.analysis.last_error_type).length,
      pending: records.filter(item => ['pending', 'processing'].includes(item.analysis.status)).length,
      failed: records.filter(item => item.analysis.status === 'unavailable' || Boolean(item.analysis.last_error_type)).length,
    };
  };
  const countRecentStatuses = (rows, days = 7, now = Date.now()) => rows.reduce((counts, item) => {
    const created = new Date(item.created_at).getTime();
    if (Number.isFinite(created) && created >= now - days * 86400000) counts[item.status] = (counts[item.status] || 0) + 1;
    return counts;
  }, {});
  window.ECSAnalytics = { normalizeDailyCounts, filterIncidents, chartPoints, categorySegments, summarizeAnalysis, countRecentStatuses };

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const activeIncident = item => !['Resolved', 'Cancelled'].includes(item.status);
  const svgTrend = (series, label) => {
    const values = series.map(point => point.count);
    if (!values.some(Boolean)) return '<div class="chart-empty">No incident submissions in this period.</div>';
    const points = chartPoints(values);
    const coords = points.split(' ').map(point => point.split(',').map(Number));
    const area = `18,162 ${points} 622,162`;
    const labels = [series[0], series[Math.floor((series.length - 1) / 2)], series[series.length - 1]];
    return `<div class="trend-chart"><svg viewBox="0 0 640 180" role="img" aria-label="${esc(label)}. ${series.map(point => `${point.date}: ${point.count}`).join('; ')}" preserveAspectRatio="none"><title>${esc(label)}</title><defs><linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#2878d0" stop-opacity=".22"/><stop offset="1" stop-color="#2878d0" stop-opacity="0"/></linearGradient></defs><path d="M${area.replaceAll(' ', ' L')} Z" fill="url(#trend-fill)"/><path d="M${points.replaceAll(' ', ' L')}" fill="none" stroke="#2878d0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${coords.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.8" fill="#fff" stroke="#2878d0" stroke-width="2"/>`).join('')}</svg><div class="chart-labels">${labels.map(point => `<span>${new Date(`${point.date}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })}</span>`).join('')}</div></div>`;
  };
  const categoryRows = counts => Object.entries(counts || {}).filter(([, value]) => Number(value) > 0).sort((a, b) => b[1] - a[1]);
  const workloadRows = (assignments, responders) => Object.entries(assignments || {})
    .map(([id, count]) => ({ id, count: Number(count) || 0, name: responders.find(item => item.id === id)?.display_name || 'Responder record' }))
    .filter(item => item.count > 0).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)).slice(0, 5);
  const workloadList = rows => {
    if (!rows.length) return '<p class="chart-empty">No assignment records in this period.</p>';
    const max = Math.max(...rows.map(item => item.count));
    return `<div class="workload-list">${rows.map(item => `<div class="workload-row"><span>${esc(item.name)}</span><i><b style="width:${100 * item.count / max}%"></b></i><strong>${item.count}</strong></div>`).join('')}</div>`;
  };
  const metricAction = (label, value, hint, action, accent = '') => action
    ? `<button type="button" class="metric metric-action ${accent}" onclick="${action}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(hint)}</small><i aria-hidden="true">→</i></button>`
    : `<div class="metric metric-action ${accent}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(hint)}</small></div>`;
  const incidentPipeline = counts => {
    const stages = [
      ['Unassigned', 'Awaiting assignment', 'stage-attention'],
      ['Assigned', 'Assigned', 'stage-assigned'],
      ['Accepted', 'Accepted', 'stage-progress'],
      ['En Route', 'En route', 'stage-progress'],
      ['On Scene', 'On scene', 'stage-progress'],
      ['Resolved', 'Resolved', 'stage-complete'],
      ['Cancelled', 'Cancelled', 'stage-neutral'],
    ];
    const values = stages.map(([key]) => Number(counts?.[key]) || 0);
    const max = Math.max(1, ...values);
    return `<div class="lifecycle-stages">${stages.map(([key, label, tone], index) => `<button type="button" class="lifecycle-stage ${tone}" aria-label="Filter incidents with status ${esc(key)}: ${values[index]}" title="${values[index]} incidents with status ${esc(key)}" onclick="drillStatus('${key}')"><span class="lifecycle-label">${esc(label)}</span><i class="lifecycle-track" aria-hidden="true"><em style="width:${100 * values[index] / max}%"></em></i><b>${values[index]}</b></button>`).join('')}</div>`;
  };
  const compactIncidentList = rows => rows.length ? `<div class="compact-incident-list">${rows.map(item => `<article class="compact-incident"><button type="button" class="compact-incident-main" onclick="openIncident('${esc(item.id)}')"><span class="compact-incident-top"><b>${esc(item.reference)}</b>${priority(item)}<span class="compact-status">${esc(item.status)}</span></span><span class="compact-incident-category">${esc(item.emergency_type)}${item.severity ? ` · Severity ${esc(item.severity)}` : ''}</span><small>${item.responder_name ? `Responder: ${esc(item.responder_name)}` : 'Awaiting responder'} · ${new Date(item.created_at).toLocaleString()}</small></button>${allowed('assign_responders') && activeIncident(item) ? `<button type="button" class="compact-assign" onclick="assign('${esc(item.id)}',${Boolean(item.responder_id)})">${item.responder_id ? 'Reassign' : 'Assign'}</button>` : ''}</article>`).join('')}</div>` : '<p class="chart-empty">No active incidents.</p>';
  const updateNotificationBadge = rowsOrCount => {
    const button = document.querySelector('#notification-shortcut');
    const badge = document.querySelector('#notification-count');
    if (!button || !badge) return;
    const unread = Array.isArray(rowsOrCount) ? rowsOrCount.filter(item => !item.read).length : Math.max(0, Number(rowsOrCount) || 0);
    button.classList.remove('hidden');
    button.setAttribute('aria-label', `Notifications, ${unread} unread`);
    badge.textContent = unread > 99 ? '99+' : String(unread);
    badge.classList.toggle('hidden', unread === 0);
  };
  window.updateNotificationBadge = updateNotificationBadge;
  const categoryList = (rows, total) => {
    if (!rows.length) return '<p class="chart-empty">No category data for this period.</p>';
    const segments = categorySegments(rows, total);
    const circles = segments.map((segment, index) => `<circle class="donut-segment swatch-${index % 6}" cx="50" cy="50" r="40" fill="none" stroke-width="14" stroke-dasharray="${segment.dash} ${2 * Math.PI * 40 - segment.dash}" stroke-dashoffset="${segment.offset}" transform="rotate(-90 50 50)" tabindex="0" role="button" aria-label="Filter incidents by ${esc(segment.name)}: ${segment.value}, ${segment.percentage}%" onclick="drillCategory('${esc(segment.name)}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();drillCategory('${esc(segment.name)}')}"></circle>`).join('');
    return `<div class="category-visual"><svg class="donut-chart" viewBox="0 0 100 100" role="group" aria-label="Incident categories; choose a segment or legend item to filter incidents">${circles}<text x="50" y="47" text-anchor="middle" class="donut-total">${total}</text><text x="50" y="59" text-anchor="middle" class="donut-caption">incidents</text></svg><ul class="category-list">${segments.map((segment, index) => `<li><button type="button" class="category-filter" onclick="window.drillCategory('${esc(segment.name)}')"><i class="category-swatch swatch-${index % 6}"></i><span>${esc(segment.name)}</span><b>${segment.value}</b><small>${segment.percentage}%</small></button></li>`).join('')}</ul></div>`;
  };

  const navigateWithFilter = async (selector, value) => {
    await window.go('incidents');
    const control = document.querySelector(selector);
    if (control) { control.value = value; control.dispatchEvent(new Event('change')); }
  };
  window.drillCategory = value => navigateWithFilter('#category-filter', value);
  window.drillStatus = value => navigateWithFilter('#status-filter', value);
  window.drillPriority = value => navigateWithFilter('#priority-filter', value);
  window.go = page => {
    current = page;
    document.querySelectorAll('.nav').forEach(button => button.classList.toggle('active', button.dataset.view === page));
    return render();
  };

  window.overview = async function () {
    const permissions = typeof allowed === 'function' ? allowed : () => false;
    const canViewIncidents = permissions('view_incidents');
    const canViewReports = permissions('view_reports');
    const requests = [api('/admin/dashboard'), canViewIncidents ? api('/incidents') : Promise.resolve([]), api('/admin/responders'), canViewReports ? api('/admin/analytics?days=7') : Promise.resolve(null), api('/notifications')];
    requests.push(permissions('view_audit_logs') ? api('/admin/audit?limit=6') : Promise.resolve([]));
    const [dashboard, rows, responderRows, reportData, notifications, audit] = await Promise.all(requests);
    const analytics = reportData || { status_counts: {}, assignments_per_responder: {} };
    updateNotificationBadge(notifications);
    incidents = rows; responders = responderRows;
    const active = rows.filter(activeIncident).sort((a, b) => {
      const rank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
      return (rank[a.priority] ?? 4) - (rank[b.priority] ?? 4) || new Date(b.created_at) - new Date(a.created_at);
    });
    const critical = active.filter(item => ['Critical', 'High'].includes(item.priority));
    const unassigned = active.filter(item => item.status === 'Unassigned' || !item.responder_id);
    const attention = [...new Map([...critical, ...unassigned].map(item => [item.id, item])).values()]
      .sort((a, b) => (a.responder_id ? 1 : 0) - (b.responder_id ? 1 : 0) || new Date(b.created_at) - new Date(a.created_at)).slice(0, 6);
    const analysisSummary = canViewIncidents ? summarizeAnalysis(rows) : null;
    const sidebarSummary = document.querySelector('#ai-sidebar-summary');
    if (sidebarSummary) sidebarSummary.classList.toggle('hidden', !canViewIncidents);
    const sidebarReady = document.querySelector('#ai-sidebar-ready');
    const sidebarFailed = document.querySelector('#ai-sidebar-failed');
    if (sidebarReady && analysisSummary) sidebarReady.textContent = String(analysisSummary.ready);
    if (sidebarFailed && analysisSummary) sidebarFailed.textContent = String(analysisSummary.failed);
    const aiFailed = canViewIncidents ? rows.filter(item => item.analysis && (item.analysis.status === 'unavailable' || item.analysis.last_error_type)) : [];
    const respondersByWorkload = canViewReports ? workloadRows(analytics.assignments_per_responder, responderRows) : null;
    const available = Number(dashboard.responders_available) || 0;
    const busy = Number(dashboard.responders_busy) || 0;
    const unavailable = Number(dashboard.responders_unavailable) || 0;
    const responderTotal = available + busy + unavailable;
    const isDemo = String(account?.email || '').startsWith('demo.');
    const headerAction = document.querySelector('#header-incident-action');
    if (headerAction) headerAction.classList.toggle('hidden', !permissions('view_incidents'));
    const statusCounts = reportData?.status_counts || (canViewIncidents ? countRecentStatuses(rows) : null);
    const activePanel = `<section class="panel active-panel"><div class="panel-head"><div><p class="eyebrow">ACTIVE RESPONSE</p><h2>Priority incidents</h2><p class="panel-kicker">Open incidents ordered by priority and time reported</p></div>${canViewIncidents ? '<button class="quiet small" onclick="go(\'incidents\')">All incidents →</button>' : ''}</div>${canViewIncidents ? compactIncidentList(active.slice(0, 5)) : '<p class="chart-empty">Incident detail access is not included in your current role.</p>'}</section>`;
    const aiPanel = `<section class="panel ai-panel"><div class="panel-head"><div><p class="eyebrow">DECISION SUPPORT</p><h2>AI automation activity</h2><p class="panel-kicker">Persisted analysis records · AI suggestions do not dispatch responders</p></div>${allowed('super_admin') ? '<button class="quiet small" onclick="go(\'automation\')">Policy →</button>' : ''}</div>${analysisSummary ? `<div class="ai-counts"><button type="button" onclick="go('incidents')"><b>${analysisSummary.ready}</b><span>Analysis ready</span></button><button type="button" onclick="go('incidents')"><b>${analysisSummary.pending}</b><span>Pending / processing</span></button><button type="button" class="${analysisSummary.failed ? 'ai-failure' : ''}" onclick="go('incidents')"><b>${analysisSummary.failed}</b><span>Unavailable</span></button></div>${aiFailed.length ? `<div class="ai-exceptions">${aiFailed.slice(0, 3).map(item => `<button type="button" onclick="openIncident('${esc(item.id)}')"><span><b>${esc(item.reference)}</b><small>${esc(item.analysis.last_error_type || item.analysis.validation_outcome || item.analysis.status)}</small></span><span aria-hidden="true">→</span></button>`).join('')}</div>` : '<p class="metric-footnote">No persisted analysis failures are currently recorded.</p>'}` : '<p class="chart-empty">Incident detail access is not included in your current role.</p>'}<div class="responder-mini"><div class="responder-mini-head"><b>Responder availability</b><span>${available} available · ${busy} busy</span></div><div class="availability-bar" role="img" aria-label="${available} available, ${busy} busy, ${unavailable} unavailable">${responderTotal ? `<i class="available-segment" style="width:${100 * available / responderTotal}%"></i><i class="busy-segment" style="width:${100 * busy / responderTotal}%"></i><i class="unavailable-segment" style="width:${100 * unavailable / responderTotal}%"></i>` : ''}</div>${canViewReports ? `${workloadList(respondersByWorkload)}<p class="metric-footnote">Workload counts are persisted assignment records from the last 7 days.</p>` : '<p class="metric-footnote">Assignment history is outside your current report permissions.</p>'}</div></section>`;
    const attentionPanel = `<section class="panel attention-panel"><div class="panel-head"><div><p class="eyebrow">COORDINATOR REVIEW</p><h2>Attention required</h2><p class="panel-kicker">Priority and assignment exceptions from current records</p></div></div>${canViewIncidents ? `<div class="attention-summary"><button type="button" onclick="drillStatus('Unassigned')"><span><i class="attention-indicator yellow-indicator"></i><b>Unassigned</b></span><strong>${dashboard.unassigned}</strong><small>Open incidents with no responder assignment</small></button><button type="button" onclick="drillPriority('Critical')"><span><i class="attention-indicator red-indicator"></i><b>High priority</b></span><strong>${critical.length}</strong><small>Active high or critical incidents</small></button><button type="button" onclick="go('incidents')"><span><i class="attention-indicator ${aiFailed.length ? 'red-indicator' : 'neutral-indicator'}"></i><b>AI analysis unavailable</b></span><strong>${analysisSummary.failed}</strong><small>Persisted analysis records requiring review</small></button></div>${attention.length ? `<div class="attention-list">${attention.slice(0, 4).map(item => `<button type="button" class="attention-row" onclick="openIncident('${esc(item.id)}')"><span class="attention-priority priority-${String(item.priority || '').toLowerCase()}"></span><span class="attention-copy"><b>${esc(item.reference)} · ${esc(item.emergency_type)}</b><small>${esc(item.status)}${item.responder_name ? ` · ${esc(item.responder_name)}` : ' · Unassigned'}</small></span><span class="attention-tag">${esc(item.priority || 'Normal')}</span></button>`).join('')}</div>` : '<p class="metric-footnote">No open incident exceptions to show.</p>'}` : '<p class="chart-empty">Incident detail access is not included in your current role.</p>'}</section>`;
    view.innerHTML = `${isDemo ? '<div class="demo-banner"><span class="demo-mark">DEMO</span><span>Local synthetic dataset · sample incidents and responder records are for demonstration only.</span></div>' : ''}<div class="metrics metrics-primary">
      ${metricAction('Active incidents', dashboard.active_incidents, canViewIncidents ? `${critical.length} high or critical open` : 'Current service count', canViewIncidents ? "go('incidents')" : null, 'metric-yellow')}
      ${metricAction('Unassigned', dashboard.unassigned, 'Open incidents awaiting a responder', canViewIncidents ? "drillStatus('Unassigned')" : null)}
      ${metricAction('Responders available', available, 'Current service availability', "go('responders')")}
      ${metricAction('Unread notifications', notifications.filter(item => !item.read).length, 'In-app records for this admin account', "go('notifications')")}
    </div>
    ${statusCounts ? `<section class="panel lifecycle-panel"><div class="panel-head"><div><p class="eyebrow">INCIDENT LIFECYCLE</p><h2>Incident status pipeline</h2><p class="panel-kicker">Current status for incidents reported in the last 7 days · select a stage to filter</p></div>${canViewReports ? '<button class="quiet small" onclick="go(\'reports\')">Analytics →</button>' : ''}</div>${incidentPipeline(statusCounts)}</section>` : ''}
    <div class="dashboard-grid dashboard-redesign">
      ${activePanel}${aiPanel}${attentionPanel}
      ${permissions('view_audit_logs') ? `<section class="panel activity-panel"><div class="panel-head"><div><p class="eyebrow">RECENT CHANGES</p><h2>Audit activity</h2><p class="panel-kicker">Latest records from the service audit log</p></div><button class="quiet small" onclick="go('audit')">Audit history →</button></div>${activityList(audit)}</section>` : ''}
    </div>`;
  };

  window.reportsPage = async function () {
    const days = Number(document.querySelector('#report-days')?.value || 30);
    const data = await api(`/admin/analytics?days=${days}`);
    const series = normalizeDailyCounts(data.daily_incident_counts, days);
    const statusRows = Object.entries(data.status_counts || {}).sort((a, b) => b[1] - a[1]);
    const statusTotal = statusRows.reduce((total, [, count]) => total + Number(count || 0), 0);
    const category = categoryRows(data.category_counts);
    const categoryTotal = category.reduce((total, [, count]) => total + Number(count || 0), 0);
    const bars = statusRows.map(([name, count]) => `<button class="status-bar-row" type="button" onclick="drillStatus('${esc(name)}')"><span>${esc(name)}</span><i><b style="width:${Math.min(100, 100 * count / Math.max(1, ...statusRows.map(row => row[1])))}%"></b></i><strong>${count}</strong></button>`).join('');
    view.innerHTML = `<section class="panel reports-panel"><div class="panel-head"><div><p class="eyebrow">SERVICE ANALYTICS</p><h2>Operational reports</h2><p class="panel-kicker">Aggregates from persisted incidents and assignment records.</p></div><div class="toolbar"><label class="select-label" for="report-days">Period</label><select id="report-days" aria-label="Report period"><option value="7" ${days === 7 ? 'selected' : ''}>7 days</option><option value="30" ${days === 30 ? 'selected' : ''}>30 days</option><option value="90" ${days === 90 ? 'selected' : ''}>90 days</option></select>${allowed('export_reports') ? '<button class="secondary" onclick="exportReport()">Export summary</button>' : ''}</div></div>
    <div class="metrics report-metrics">${metric('Incidents', data.incident_count, '', `In the last ${days} days`)}${metric('Assignments', data.assignment_count, '', 'Assignment records created')}${metric('Completed assignments', data.completed_assignment_count, '', 'Closed assignment records')}${metric('Resources allocated', data.resource_units_allocated, '', 'Current resource snapshot')}</div>
    <section class="report-trend"><div class="panel-head"><div><h3>Daily submissions</h3><p class="panel-kicker">Incident creation date · UTC</p></div><b>${data.incident_count} <small>incidents</small></b></div>${svgTrend(series, `Daily incident submissions for the last ${days} days`)}</section>
    <div class="report-grid"><section class="report-subpanel"><div class="panel-head"><div><h3>Incidents by status</h3><p class="panel-kicker">${statusTotal} status records in period</p></div></div>${bars || '<p class="chart-empty">No incident status data in this period.</p>'}</section><section class="report-subpanel"><div class="panel-head"><div><h3>Incident categories</h3><p class="panel-kicker">Select a category to open its incident list</p></div></div>${categoryList(category, categoryTotal)}</section></div>
    <div class="timing-grid"><article class="timing-card"><span>Average assignment delay</span><b>${data.average_assignment_delay_minutes ?? '—'} <small>min</small></b><p>Time from incident creation to each recorded assignment. Reassignments may add assignment samples.</p></article><article class="timing-card"><span>Average assignment to completion</span><b>${data.average_assignment_to_completion_minutes ?? '—'} <small>min</small></b><p>Time from assignment to completion for closed assignment records. This is not travel or arrival time.</p></article></div><p class="data-note">${esc(data.data_note || 'Metrics are descriptive and depend on records available in the selected period.')} Resources allocated is a current snapshot, not a historical total.</p></section>`;
    document.querySelector('#report-days').onchange = window.reportsPage;
  };

  window.incidentPage = async function () {
    incidents = await api('/incidents');
    view.innerHTML = `<section class="panel incident-list-panel"><div class="panel-head"><div><p class="eyebrow">COORDINATION</p><h2>Incident queue <span class="pill">${incidents.length}</span></h2><p class="panel-kicker">Search, filter and open reports available to your account.</p></div></div><div class="toolbar incident-filters"><label>Search<input id="incident-search" type="search" placeholder="Reference, description, location…" value="${esc(incidentSearch)}"></label><label>Status<select id="status-filter"><option value="">All statuses</option>${['Unassigned', 'Assigned', 'Accepted', 'En Route', 'On Scene', 'Resolved', 'Cancelled'].map(value => `<option>${value}</option>`).join('')}</select></label><label>Priority<select id="priority-filter"><option value="">All priorities</option>${['Critical', 'High', 'Medium', 'Low'].map(value => `<option>${value}</option>`).join('')}</select></label><label>Category<select id="category-filter"><option value="">All categories</option>${[...new Set(incidents.map(item => item.emergency_type).filter(Boolean))].sort().map(value => `<option>${esc(value)}</option>`).join('')}</select></label><button id="clear-incident-filters" class="quiet small" type="button">Clear filters</button></div><p id="filter-result" class="filter-result" aria-live="polite"></p><div id="inc-table"></div></section>`;
    const filter = () => {
      incidentSearch = document.querySelector('#incident-search').value;
      const filtered = filterIncidents(incidents, { query: incidentSearch, status: document.querySelector('#status-filter').value, priority: document.querySelector('#priority-filter').value, category: document.querySelector('#category-filter').value });
      document.querySelector('#filter-result').textContent = `Showing ${filtered.length} of ${incidents.length} incidents`;
      document.querySelector('#inc-table').innerHTML = filtered.length ? tableIncidents(filtered) : '<p class="chart-empty">No incidents match these filters.</p>';
    };
    ['#incident-search'].forEach(selector => document.querySelector(selector).addEventListener('input', filter));
    ['#status-filter', '#priority-filter', '#category-filter'].forEach(selector => document.querySelector(selector).addEventListener('change', filter));
    document.querySelector('#clear-incident-filters').onclick = () => { document.querySelector('#incident-search').value = ''; ['#status-filter', '#priority-filter', '#category-filter'].forEach(selector => { document.querySelector(selector).value = ''; }); filter(); };
    filter();
  };
})();
