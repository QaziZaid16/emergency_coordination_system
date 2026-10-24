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
  window.ECSAnalytics = { normalizeDailyCounts, filterIncidents, chartPoints, categorySegments };

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
    const requests = [api('/admin/dashboard'), api('/incidents'), api('/admin/responders'), api('/admin/analytics?days=7')];
    requests.push(permissions('view_audit_logs') ? api('/admin/audit?limit=6') : Promise.resolve([]));
    const [dashboard, rows, responderRows, analytics, audit] = await Promise.all(requests);
    incidents = rows; responders = responderRows;
    const active = rows.filter(activeIncident).sort((a, b) => {
      const rank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
      return (rank[a.priority] ?? 4) - (rank[b.priority] ?? 4) || new Date(b.created_at) - new Date(a.created_at);
    });
    const critical = active.filter(item => ['Critical', 'High'].includes(item.priority));
    const unassigned = active.filter(item => !item.responder_id);
    const attention = [...new Map([...critical, ...unassigned].map(item => [item.id, item])).values()]
      .sort((a, b) => (a.responder_id ? 1 : 0) - (b.responder_id ? 1 : 0) || new Date(b.created_at) - new Date(a.created_at)).slice(0, 6);
    const series = normalizeDailyCounts(analytics.daily_incident_counts, 7);
    const categories = categoryRows(analytics.category_counts);
    const available = Number(dashboard.responders_available) || 0;
    const busy = Number(dashboard.responders_busy) || 0;
    const unavailable = Number(dashboard.responders_unavailable) || 0;
    const responderTotal = available + busy + unavailable;
    view.innerHTML = `<div class="metrics metrics-primary">
      ${metric('Active incidents', dashboard.active_incidents, '', `${critical.length} high or critical open`)}
      ${metric('Unassigned', dashboard.unassigned, '', 'Open incidents awaiting a responder')}
      ${metric('Responders available', available, '', 'Current service availability')}
      ${metric('Open high priority', critical.length, '', 'High and critical incidents')}
    </div>
    <div class="dashboard-grid dashboard-redesign">
      <section class="panel chart-panel trend-panel"><div class="panel-head"><div><p class="eyebrow">INCIDENT VOLUME</p><h2>Reports over time</h2><p class="panel-kicker">Daily incident submissions · last 7 days · UTC</p></div><button class="quiet small" onclick="go('reports')">View reports <span aria-hidden="true">→</span></button></div>${svgTrend(series, 'Daily incident submissions for the last 7 days')}</section>
      <section class="panel chart-panel"><div class="panel-head"><div><p class="eyebrow">RESPONDER CAPACITY</p><h2>Current availability</h2><p class="panel-kicker">${responderTotal} responder records</p></div></div><div class="availability-bar" role="img" aria-label="${available} available, ${busy} busy, ${unavailable} unavailable">${responderTotal ? `<i class="available-segment" style="width:${100 * available / responderTotal}%"></i><i class="busy-segment" style="width:${100 * busy / responderTotal}%"></i><i class="unavailable-segment" style="width:${100 * unavailable / responderTotal}%"></i>` : ''}</div><div class="availability-legend"><span><i class="available-dot"></i>Available <b>${available}</b></span><span><i class="busy-dot"></i>Busy <b>${busy}</b></span><span><i class="unavailable-dot"></i>Unavailable <b>${unavailable}</b></span></div><p class="metric-footnote">Current snapshot from responder records. Availability does not guarantee incident eligibility.</p></section>
      <section class="panel chart-panel"><div class="panel-head"><div><p class="eyebrow">INCIDENT MIX</p><h2>Categories</h2><p class="panel-kicker">Recorded incidents in selected service data</p></div><span class="panel-total">${rows.length}<small>total</small></span></div>${categoryList(categoryRows(analytics.category_counts), Object.values(analytics.category_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0))}</section>
      <section class="panel attention-panel"><div class="panel-head"><div><p class="eyebrow">NEEDS ATTENTION</p><h2>Review queue</h2><p class="panel-kicker">Open high-priority and unassigned incidents</p></div><button class="secondary small" onclick="go('incidents')">Open queue</button></div>${attention.length ? `<div class="attention-list">${attention.map(item => `<button type="button" class="attention-row" onclick="openIncident('${esc(item.id)}')"><span class="attention-priority priority-${String(item.priority || '').toLowerCase()}"></span><span class="attention-copy"><b>${esc(item.reference)} · ${esc(item.emergency_type)}</b><small>${esc(item.status)}${item.responder_name ? ` · ${esc(item.responder_name)}` : ' · Unassigned'} · ${new Date(item.created_at).toLocaleString()}</small></span><span class="attention-tag">${esc(item.priority || 'Normal')}</span></button>`).join('')}</div>` : '<p class="chart-empty">No open incidents meet these review conditions.</p>'}</section>
      <section class="panel queue-panel"><div class="panel-head"><div><p class="eyebrow">ACTIVE WORK</p><h2>Incident queue</h2><p class="panel-kicker">Open reports sorted by priority and submission time</p></div><button class="quiet small" onclick="go('incidents')">All incidents →</button></div>${active.length ? tableIncidents(active.slice(0, 5)) : '<p class="chart-empty">No active incidents.</p>'}</section>
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
