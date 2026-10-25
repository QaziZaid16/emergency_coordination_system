import { describe, expect, it } from 'vitest';
import { filterIncidents } from './filter';
const rows=[{reference:'ECS-1',emergency_type:'Fire',description:'Smoke visible',location_label:'North',status:'Unassigned',priority:'High'},{reference:'ECS-2',emergency_type:'Medical',description:'Injury',location_label:'South',status:'Assigned',priority:'Critical'}];
describe('incident filters',()=>{it('combines query, status, priority and category',()=>expect(filterIncidents(rows,{query:'smoke',status:'Unassigned',priority:'High',category:'Fire'})).toEqual([rows[0]]));it('returns no records for unmatched search',()=>expect(filterIncidents(rows,{query:'missing'})).toEqual([]));});
