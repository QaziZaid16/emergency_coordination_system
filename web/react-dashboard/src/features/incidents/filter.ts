export type IncidentFilter = { query?: string; status?: string; priority?: string; category?: string };
export function filterIncidents<T extends Record<string, any>>(rows: T[], filters: IncidentFilter): T[] {
  const query = (filters.query || '').trim().toLowerCase();
  return rows.filter(row => (!filters.status || row.status === filters.status) && (!filters.priority || row.priority === filters.priority) && (!filters.category || row.emergency_type === filters.category) && (!query || [row.reference, row.emergency_type, row.description, row.location_label, row.responder_name].join(' ').toLowerCase().includes(query)));
}
