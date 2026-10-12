"""Read-only walkable road routing. Never fabricate gaps or continuous GPS tracks."""
import copy
import heapq
import json
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from shapely.geometry import LineString, Point, shape
from shapely.ops import transform, unary_union

ORIGIN = (114.42966, 30.42023)
FX = 111320 * math.cos(math.radians(ORIGIN[1]))
FY = 111320


def project(x, y, z=None):
    return (x - ORIGIN[0]) * FX, (y - ORIGIN[1]) * FY


def inverse(p):
    return [p[0] / FX + ORIGIN[0], p[1] / FY + ORIGIN[1]]


def lines(g):
    if g.geom_type == 'LineString':
        yield g
    elif hasattr(g, 'geoms'):
        for part in g.geoms:
            yield from lines(part)


class WalkNetwork:
    def __init__(self, roads, buildings, landscape, boundary):
        self.boundary = unary_union([transform(project, shape(f['geometry'])) for f in boundary['features']])
        self.buildings = {f['properties']['building_id']: transform(project, shape(f['geometry'])) for f in buildings['features']}
        self.obstacles = unary_union(list(self.buildings.values()))
        self.water = unary_union([transform(project, shape(f['geometry'])) for f in landscape['features'] if f['properties'].get('landscape_type') == 'water'])
        groups = {}
        self.excluded = 0
        self.graph = {}
        self.edges = []
        self.route_cache = {}
        allowed = {'footway', 'path', 'pedestrian', 'steps', 'residential', 'service', 'unclassified', 'living_street', 'tertiary'}
        for f in roads['features']:
            p = f['properties']; tags = p.get('tags', {})
            if p.get('highway') not in allowed or tags.get('foot') in ('no', 'private') or tags.get('access') in ('no', 'private'):
                self.excluded += 1
                continue
            level = str(tags.get('layer', '0'))
            bridge = tags.get('bridge') not in (None, 'no', 'false')
            tunnel = tags.get('tunnel') not in (None, 'no', 'false')
            group = (level, bridge, tunnel)
            g = transform(project, shape(f['geometry']))
            for line in lines(g):
                # Existing bridge tags permit water crossings, but not buildings.
                if line.intersection(self.obstacles).length > .01 or (not bridge and line.intersection(self.water).length > .01):
                    self.excluded += 1
                    line = line.difference(self.obstacles if bridge else unary_union([self.obstacles, self.water]))
                groups.setdefault(group, []).extend(lines(line.intersection(self.boundary)))
        endpoints = {}
        for group, gs in groups.items():
            for line in lines(unary_union(gs)):
                cs = list(line.coords)
                for a, b in zip(cs, cs[1:]):
                    a, b = tuple(a), tuple(b)
                    length = math.dist(a, b)
                    if length < .001:
                        continue
                    ka, kb = self.key(a, group), self.key(b, group)
                    self.graph.setdefault(ka, {})[kb] = length
                    self.graph.setdefault(kb, {})[ka] = length
                    self.edges.append((ka, kb, LineString([a, b]), group))
                # Only explicit segment endpoints connect different layers, never interior crossings.
                for c in (cs[0], cs[-1]):
                    endpoints.setdefault((round(c[0], 3), round(c[1], 3)), []).append(self.key(c, group))
        for keys in endpoints.values():
            for a in keys:
                for b in keys:
                    if a != b:
                        self.graph.setdefault(a, {})[b] = 0

    @staticmethod
    def key(p, group):
        return (round(p[0], 3), round(p[1], 3), group)

    def access(self, node):
        lon, lat = node.get('longitude'), node.get('latitude')
        if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (lon, lat)):
            return None
        point = Point(project(lon, lat))
        own = self.buildings.get(node.get('building_id'))
        # OSM may retain both a named wing and its enclosing building complex.
        # Treat a fully enclosing footprint as the same physical anchor building
        # only for access validation. Neither road obstacles nor source polygons
        # are removed; the interior access connector is never rendered.
        anchor = own
        if own is not None and own.covers(point):
            envelopes = [g for g in self.buildings.values()
                         if g.covers(point) and g.intersection(own).area >= own.area * .999]
            anchor = unary_union(envelopes)
        candidates = sorted(self.edges, key=lambda e: point.distance(e[2]))
        for edge in candidates[:60]:
            distance = point.distance(edge[2])
            if distance > 120:
                break
            snap = edge[2].interpolate(edge[2].project(point))
            connector = LineString([point.coords[0], snap.coords[0]])
            # A camera anchor may be inside its own demonstration building. We do not draw
            # that interior segment and still check every other obstacle on the access line.
            exterior = connector.difference(anchor) if anchor is not None else connector
            if exterior.intersection(self.obstacles).length > .01 or exterior.intersection(self.water).length > .01:
                continue
            if not self.boundary.buffer(.01).covers(connector):
                continue
            return {'edge': edge, 'point': tuple(snap.coords[0]), 'distance': distance}
        return None

    def route(self, start, end):
        sa, ea = self.access(start), self.access(end)
        if not sa or not ea:
            return {'status': 'ACCESS_UNCONFIRMED', 'message': '道路接入待确认：距离过远或接入线存在建筑/水面阻挡'}
        cache_key = (sa['edge'][:2], sa['point'], ea['edge'][:2], ea['point'])
        if cache_key in self.route_cache:
            return copy.deepcopy(self.route_cache[cache_key])
        graph = {k: dict(v) for k, v in self.graph.items()}
        keys = []
        for access in (sa, ea):
            a, b, line, group = access['edge']; p = access['point']; key = self.key(p, group)
            keys.append(key); graph.setdefault(key, {})
            for target in (a, b):
                if target == key:
                    continue
                length = math.dist(p, target[:2]); graph[key][target] = length; graph.setdefault(target, {})[key] = length
        if sa['edge'][:2] == ea['edge'][:2] and keys[0] != keys[1]:
            length = math.dist(sa['point'], ea['point']); graph[keys[0]][keys[1]] = length; graph[keys[1]][keys[0]] = length
        distances = {keys[0]: 0}; previous = {}; queue = [(0, keys[0])]
        while queue:
            distance, key = heapq.heappop(queue)
            if distance != distances[key]:
                continue
            if key == keys[1]:
                break
            for neighbor, weight in graph[key].items():
                candidate = distance + weight
                if candidate < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate; previous[neighbor] = key; heapq.heappush(queue, (candidate, neighbor))
        if keys[1] not in distances:
            result = {'status': 'DISCONNECTED', 'message': '道路不连通，无法推算道路路径'}
        else:
            order = [keys[1]]
            while order[-1] != keys[0]:
                order.append(previous[order[-1]])
            coordinates = [inverse(p) for p in reversed(order)]
            coordinates = [c for i, c in enumerate(coordinates) if i == 0 or c != coordinates[i-1]]
            result = {'status': 'ROUTED', 'coordinates': coordinates, 'distance_m': round(distances[keys[1]], 1),
                      'access_status': 'INFERRED_REQUIRES_REVIEW',
                      'start_access': {'coordinates': inverse(sa['point']), 'offset_m': round(sa['distance'], 1)},
                      'end_access': {'coordinates': inverse(ea['point']), 'offset_m': round(ea['distance'], 1)},
                      'message': '按道路推测；接入点为几何推算，非已核实真实入口。连线不包含建筑内锚点至道路的接入段。'}
        if len(self.route_cache) >= 512:
            self.route_cache.clear()
        self.route_cache[cache_key] = result
        return copy.deepcopy(result)


@lru_cache(maxsize=2)
def network(directory, versions):
    root = Path(directory)
    def read(name):
        return json.loads((root / name).read_text(encoding='utf-8-sig'))
    return WalkNetwork(read('hbue_roads.geojson'), read('hbue_buildings.geojson'), read('hbue_landscape.geojson'), read('hbue_campus_boundary.geojson'))


def adapt_routes(raw, directory):
    result = copy.deepcopy(raw)
    names = ['hbue_roads.geojson', 'hbue_buildings.geojson', 'hbue_landscape.geojson', 'hbue_campus_boundary.geojson']
    root = Path(directory)
    try:
        net = network(str(root), tuple((root/n).stat().st_mtime_ns for n in names))
    except (OSError, ValueError, KeyError):
        net = None
    for path in result.get('paths', []):
        path['upstream_segments'] = copy.deepcopy(path.get('segments', []))
        path['segments'] = []
        path['route_legs'] = []
        path['path_nature'] = 'ROAD_INFERRED'
        nodes = path.get('nodes', [])
        for start, end in zip(nodes, nodes[1:]):
            leg = net.route(start, end) if net else {'status': 'NETWORK_UNAVAILABLE', 'message': '校园路网暂不可用'}
            leg.update(from_camera_id=start.get('camera_id'), to_camera_id=end.get('camera_id'))
            if leg['status'] == 'ROUTED':
                try:
                    begin = datetime.fromisoformat(start.get('end_timestamp') or start['timestamp'])
                    finish = datetime.fromisoformat(end['timestamp'])
                    interval = (finish-begin).total_seconds()
                    leg['interval_seconds'] = interval
                    leg['time_consistency_notice'] = '时空一致性待核验：时间不足以支持此步行路线' if interval <= 0 or leg['distance_m']/interval > 2.5 else None
                except (KeyError, ValueError, TypeError):
                    leg['time_consistency_notice'] = '时间信息不足，无法核验步行耗时'
                if len(leg['coordinates']) > 1:
                    path['segments'].append({'coordinates': leg['coordinates'], 'path_nature': 'ROAD_INFERRED', 'from_camera_id': start.get('camera_id'), 'to_camera_id': end.get('camera_id')})
            else:
                result.setdefault('warnings', []).append(f"{path.get('global_id')}：{leg['from_camera_id']} → {leg['to_camera_id']}；{leg['message']}")
            path['route_legs'].append(leg)
        path['route_distance_m'] = round(sum(l.get('distance_m', 0) for l in path['route_legs']), 1)
        path['route_status'] = 'ROUTED' if path['route_legs'] and all(l['status']=='ROUTED' for l in path['route_legs']) else 'PARTIAL' if path['segments'] else 'NODES_ONLY'
    result['routing_notice'] = '道路推测路径，非真实连续GPS轨迹；摄像头节点保持原始配置位置，道路接入点需人工复核。'
    result['road_network'] = {'edge_count': len(net.edges), 'excluded_count': net.excluded} if net else None
    return result
