from __future__ import annotations
from collections import deque

def edge_pairs(map_data):
    return {frozenset((e['from_zone_id'],e['to_zone_id'])):e for e in map_data['topology_edges'] if e['active_by_default']}

def zone_index(map_data): return {z['zone_id']:z for z in map_data['zones']}
def site_zone_ids(map_data): return {s['site_id']:set(s['zone_ids']) for s in map_data['sites']}

def valid_transition(map_data,a,b):
    if a==b: return True
    return frozenset((a,b)) in edge_pairs(map_data)

def valid_path(map_data, seq):
    return all(valid_transition(map_data,a,b) for a,b in zip(seq,seq[1:]))

def detect_rotation(map_data, stable_zone_sequence):
    zi=zone_index(map_data)
    seq=[x for i,x in enumerate(stable_zone_sequence) if i==0 or x!=stable_zone_sequence[i-1]]
    if len(seq)<2 or any(x not in zi for x in seq): return None
    if not valid_path(map_data,seq): return None
    origin=zi[seq[0]]; dest=zi[seq[-1]]
    S=set(origin['site_affinity']); D=set(dest['site_affinity'])
    if not S or not D or not S.isdisjoint(D): return None
    return {'from':seq[0],'to':seq[-1],'origin_affinity':sorted(S),'destination_affinity':sorted(D),'path':seq}

def detect_team_entry(map_data, from_zone, to_zone, dwell_sec, threshold):
    site_map=site_zone_ids(map_data)
    if from_zone==to_zone: return None
    target_site=next((sid for sid,zids in site_map.items() if to_zone in zids),None)
    if not target_site: return None
    # crossing must originate outside the target site's site-zone set
    if from_zone in site_map[target_site]: return None
    return {'site_id':target_site,'entry_start':True,'entered':dwell_sec>=threshold}

def fuse(label_zone,label_conf,poly_zone,poly_conf,accept=.85,support=.70,previous_zone=None,boundary_ambiguous=False):
    diag=[]
    if label_zone and poly_zone and label_zone==poly_zone and label_conf>=support and poly_conf>=support:
        return label_zone,max(label_conf,poly_conf),'fused_label_polygon',diag
    if label_conf>=accept and (not poly_zone or poly_conf<support): return label_zone,label_conf,'location_label',diag
    if poly_conf>=accept and (not label_zone or label_conf<support): return poly_zone,poly_conf,'polygon',diag
    if label_zone and poly_zone and label_zone!=poly_zone:
        if label_conf>=accept and poly_conf>=accept:
            diag.append('zone_conflict_high_confidence')
            if boundary_ambiguous and previous_zone in {label_zone,poly_zone}:
                return previous_zone,max(0.0,min(label_conf,poly_conf)-0.1),'held_previous_boundary',diag
            return None,0.0,'unknown',diag
        if label_conf>=accept and poly_conf>=support:
            diag.append('source_disagreement_secondary'); return label_zone,label_conf,'location_label',diag
        if poly_conf>=accept and label_conf>=support:
            diag.append('source_disagreement_secondary'); return poly_zone,poly_conf,'polygon',diag
    if label_zone and poly_zone and label_zone==poly_zone and label_conf>=support and poly_conf>=support:
        return label_zone,min(label_conf,poly_conf),'fused_label_polygon',diag
    return None,0.0,'unknown',diag
