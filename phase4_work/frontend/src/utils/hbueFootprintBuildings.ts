import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
export type CampusLandscape = CampusFeature & {
  properties: CampusFeature["properties"] & { landscape_type: string };
};
export type CampusFeature = {
  properties: { building_id?: string; name?: string; building_type?: string };
  geometry: { type: string; coordinates: number[][][] };
};
export const detailedCampusBuildings = new Set([
  "HBUE-B120",
  "HBUE-B119",
  "HBUE-B041",
]);
export const campusOrigin = { longitude: 114.42966, latitude: 30.42023 };
export function projectCampus(point: number[]) {
  return new THREE.Vector2(
    (point[0] - campusOrigin.longitude) *
      111320 *
      Math.cos((campusOrigin.latitude * Math.PI) / 180),
    -(point[1] - campusOrigin.latitude) * 111320,
  );
}
export function footprintCenter(f: CampusFeature) {
  const points = f.geometry.coordinates[0].slice(0, -1).map(projectCampus);
  return points
    .reduce((a, p) => a.add(p), new THREE.Vector2())
    .multiplyScalar(1 / points.length);
}
export function footprintShape(f: CampusFeature, center = new THREE.Vector2()) {
  const rings = f.geometry.coordinates.map((r) =>
    r
      .map(projectCampus)
      .map((p) => new THREE.Vector2(p.x - center.x, -(p.y - center.y))),
  );
  const shape = new THREE.Shape(rings[0]);
  for (const ring of rings.slice(1)) shape.holes.push(new THREE.Path(ring));
  return shape;
}
const material = (color: number) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.65, metalness: 0.08 });
export function campusFootprintBuilding(
  f: CampusFeature,
  height: number,
  floors: number,
  detailed = true,
) {
  const center = footprintCenter(f),
    shape = footprintShape(f, center),
    group = new THREE.Group();
  const lab = f.properties.building_id === "HBUE-B041";
  const wall = material(lab ? 0xd8d9d6 : 0xdedbd4),
    roof = material(0x7b8080),
    glass = new THREE.MeshPhysicalMaterial({
      color: 0x355366,
      roughness: 0.24,
      metalness: 0.3,
      clearcoat: 0.6,
      clearcoatRoughness: 0.15,
    }),
    frame = material(0xd5d7d6);
  wall.color.setHex(0xffffff);
  roof.color.setHex(0xffffff);
  const name = f.properties.name || "",
    type = f.properties.building_type || "";
  const palette = /实验|lab/.test(name + type)
    ? 0xd7e0df
    : /宿舍|公寓|dorm/.test(name + type)
      ? 0xe4ded1
      : 0xe8ece6;
  wall.color.setHex(palette);
  roof.color.setHex(0x586b70);
  function extrusion(depth: number, y: number, mat: THREE.Material) {
    const mesh = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false }),
      mat,
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = y;
    group.add(mesh);
    return mesh;
  }
  extrusion(height, 0, wall);
  extrusion(0.22, height, roof);
  if (!detailed) {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#dbe3df";
    ctx.fillRect(0, 0, 128, 128);
    ctx.fillStyle = "#f0f3eb";
    ctx.fillRect(0, 118, 128, 8);
    ctx.fillStyle = "#f0f3eb";
    ctx.fillRect(14, 19, 100, 93);
    ctx.fillStyle = "#375b6b";
    ctx.fillRect(20, 25, 88, 81);
    ctx.fillStyle = "#b7cacb";
    ctx.fillRect(62, 25, 4, 81);
    ctx.fillRect(20, 64, 88, 4);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(1 / 3.5, 1 / 3.2);
    wall.map = texture;
    const body = group.children[0] as THREE.Mesh;
    body.material = [roof, wall];
    group.userData.model_notice =
      "真实底面；高度和窗带均为示意，未进行精确立面复原";
    return group;
  }
  const ring = f.geometry.coordinates[0]
    .slice(0, -1)
    .map(projectCampus)
    .map((p) => p.sub(center));
  const area = ring.reduce((a, p, i) => {
    const q = ring[(i + 1) % ring.length];
    return a + p.x * q.y - q.x * p.y;
  }, 0);
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i],
      b = ring[(i + 1) % ring.length],
      delta = b.clone().sub(a),
      length = delta.length();
    if (length < 3) continue;
    const tangent = delta.clone().normalize(),
      normal = new THREE.Vector2(tangent.y, -tangent.x).multiplyScalar(
        area > 0 ? 1 : -1,
      ),
      angle = -Math.atan2(tangent.y, tangent.x);
    const bays = Math.max(1, Math.floor(length / 3.4));
    for (let floor = 0; floor < floors; floor++)
      for (let bay = 0; bay < bays; bay++) {
        const p = a
            .clone()
            .addScaledVector(delta, (bay + 0.5) / bays)
            .addScaledVector(normal, 0.06),
          y = ((floor + 0.52) * height) / floors;
        const width = Math.min(2.1, (length / bays) * 0.65),
          h = Math.min(1.75, (height / floors) * 0.6);
        const outer = new THREE.Mesh(
          new THREE.BoxGeometry(width + 0.16, h + 0.16, 0.11),
          frame,
        );
        outer.position.set(p.x, y, p.y);
        outer.rotation.y = angle;
        group.add(outer);
        const pane = new THREE.Mesh(
          new THREE.BoxGeometry(width, h, 0.06),
          glass,
        );
        pane.position.set(p.x + normal.x * 0.08, y, p.y + normal.y * 0.08);
        pane.rotation.y = angle;
        group.add(pane);
      }
    for (let floor = 1; floor < floors; floor++) {
      const band = new THREE.Mesh(
        new THREE.BoxGeometry(length, 0.14, 0.18),
        frame,
      );
      band.position.set(
        (a.x + b.x) / 2,
        (floor * height) / floors,
        (a.y + b.y) / 2,
      );
      band.rotation.y = angle;
      group.add(band);
    }
    const parapet = new THREE.Mesh(
      new THREE.BoxGeometry(length, 0.55, 0.22),
      frame,
    );
    parapet.position.set((a.x + b.x) / 2, height + 0.35, (a.y + b.y) / 2);
    parapet.rotation.y = angle;
    group.add(parapet);
  }
  if (lab) {
    const contour = shape.getPoints(),
      triangles = THREE.ShapeUtils.triangulateShape(contour, []);
    const triangle = triangles.sort(
      (a, b) =>
        Math.abs(THREE.ShapeUtils.area(b.map((i) => contour[i]))) -
        Math.abs(THREE.ShapeUtils.area(a.map((i) => contour[i]))),
    )[0];
    if (triangle) {
      const p = triangle
        .map((i) => contour[i])
        .reduce((a, b) => a.add(b), new THREE.Vector2())
        .multiplyScalar(1 / 3);
      const plant = new THREE.Mesh(
        new THREE.BoxGeometry(5, 1.8, 2.4),
        material(0xb8c4cb),
      );
      plant.position.set(p.x, height + 1.1, -p.y);
      group.add(plant);
      for (let i = -1; i <= 1; i++) {
        const fan = new THREE.Mesh(
          new THREE.CylinderGeometry(0.45, 0.45, 0.12, 12),
          material(0x425965),
        );
        fan.position.set(p.x + i * 1.4, height + 2.05, -p.y);
        group.add(fan);
      }
    }
  }
  // Entrance sits on the longest actual facade, not outside an arbitrary box.
  const edges = ring
    .map((a, i) => ({ a, b: ring[(i + 1) % ring.length] }))
    .sort((u, v) => v.a.distanceTo(v.b) - u.a.distanceTo(u.b));
  const { a, b } = edges[0],
    d = b.clone().sub(a).normalize(),
    out = new THREE.Vector2(d.y, -d.x).multiplyScalar(area > 0 ? 1 : -1),
    entry = a.clone().add(b).multiplyScalar(0.5);
  const door = new THREE.Mesh(new THREE.BoxGeometry(3.4, 2.7, 0.16), glass);
  door.position.set(entry.x + out.x * 0.15, 1.35, entry.y + out.y * 0.15);
  door.rotation.y = -Math.atan2(d.y, d.x);
  group.add(door);
  const canopy = new THREE.Mesh(
    new THREE.BoxGeometry(lab ? 6 : 8, 0.18, 2.3),
    frame,
  );
  canopy.position.set(entry.x + out.x, 3.05, entry.y + out.y);
  canopy.rotation.y = door.rotation.y;
  group.add(canopy);
  group.userData.model_notice =
    "真实建筑底面；层数、高度、立面为校园用途示意，非精确复原";
  group.userData.footprint_id = f.properties.building_id;
  return group;
}
export type CampusRoad = {
  properties: { highway: string; tags?: Record<string, string> };
  geometry: { type: string; coordinates: number[][] };
};
export function campusFootprintGround(
  features: CampusFeature[],
  boundary: CampusFeature,
  roads: CampusRoad[] = [],
  boundIds: Set<string> = new Set(),
  landscape: CampusLandscape[] = [],
) {
  const root = new THREE.Group();
  const ground = new THREE.Mesh(
    new THREE.ShapeGeometry(footprintShape(boundary)),
    material(0xb2cbb2),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.12;
  root.add(ground);
  (ground.material as THREE.MeshStandardMaterial).color.setHex(0x9bb98a);
  // Context buildings retain real footprints but have no business identity,
  // labels, picking, metrics or telemetry. Merge all into one draw call.
  const background: THREE.BufferGeometry[] = [];
  for (const f of features) {
    if (boundIds.has(f.properties.building_id || "")) continue;
    const name = f.properties.name || "",
      type = f.properties.building_type || "";
    const height = /体育|食堂|活动/.test(name)
      ? 8
      : /宿舍|公寓|dorm/.test(name + type)
        ? 17
        : 13;
    const geometry = new THREE.ExtrudeGeometry(footprintShape(f), {
      depth: height,
      bevelEnabled: false,
    });
    geometry.rotateX(-Math.PI / 2);
    const normals = geometry.getAttribute("normal"),
      colors: number[] = [];
    for (let i = 0; i < normals.count; i++) {
      const c = new THREE.Color(
        normals.getY(i) > 0.9
          ? 0x7e8e8c
          : /宿舍|公寓/.test(name)
            ? 0xcbbfac
            : 0xb7c6bd,
      );
      colors.push(c.r, c.g, c.b);
    }
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    geometry.clearGroups();
    background.push(geometry);
  }
  if (background.length) {
    const combined = mergeGeometries(background);
    background.forEach((g) => g.dispose());
    if (combined) {
      const mesh = new THREE.Mesh(
        combined,
        new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 }),
      );
      mesh.userData.presentation_only = true;
      mesh.userData.height_source = "MODEL_DEFAULT";
      mesh.castShadow = mesh.receiveShadow = true;
      root.add(mesh);
    }
  }
  root.userData.background_building_count = background.length;
  const environmentMeshes = new Map<string, THREE.BufferGeometry[]>();
  for (const f of landscape) {
    const kind = f.properties.landscape_type;
    if (!["water", "sport", "green", "paving"].includes(kind)) continue;
    const geometry = new THREE.ShapeGeometry(footprintShape(f));
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, kind === "water" ? 0.035 : 0.06, 0);
    const list = environmentMeshes.get(kind) || [];
    list.push(geometry);
    environmentMeshes.set(kind, list);
  }
  const environmentColors: Record<string, number> = {
    water: 0x69b9c9,
    sport: 0x738e77,
    green: 0x81a877,
    paving: 0xd7d8ca,
  };
  for (const [kind, geometries] of environmentMeshes) {
    const combined = mergeGeometries(geometries);
    geometries.forEach((g) => g.dispose());
    if (combined) {
      const mat = material(environmentColors[kind]);
      mat.side = THREE.DoubleSide;
      if (kind === "water") {
        mat.roughness = 0.28;
        mat.metalness = 0.15;
      }
      const mesh = new THREE.Mesh(combined, mat);
      mesh.userData.presentation_only = true;
      mesh.receiveShadow = true;
      root.add(mesh);
    }
  }
  root.userData.landscape_count = landscape.length;
  const paving = material(0xc6c2b8),
    asphalt = material(0x555f63),
    walk = material(0xc1bba9);
  const roadVertices = new Map<THREE.Material, number[]>();
  for (const m of [paving, asphalt, walk]) {
    m.polygonOffset = true;
    m.polygonOffsetFactor = -1;
    m.polygonOffsetUnits = -2;
  }
  asphalt.color.setHex(0x43535a);
  walk.color.setHex(0xe1e4d8);
  paving.color.setHex(0xc6d1c1);
  // World-aligned paving joints: one shared texture, no mesh per tile.
  const pavingCanvas = document.createElement("canvas");
  pavingCanvas.width = pavingCanvas.height = 128;
  const pavingContext = pavingCanvas.getContext("2d")!;
  pavingContext.fillStyle = "#d9dfd4";
  pavingContext.fillRect(0, 0, 128, 128);
  pavingContext.strokeStyle = "#a8b4a5";
  pavingContext.lineWidth = 2;
  for (let i = 0; i <= 128; i += 32) {
    pavingContext.beginPath();
    pavingContext.moveTo(i, 0);
    pavingContext.lineTo(i, 128);
    pavingContext.moveTo(0, i);
    pavingContext.lineTo(128, i);
    pavingContext.stroke();
  }
  const pavingTexture = new THREE.CanvasTexture(pavingCanvas);
  pavingTexture.colorSpace = THREE.SRGBColorSpace;
  pavingTexture.wrapS = pavingTexture.wrapT = THREE.RepeatWrapping;
  paving.map = pavingTexture;
  walk.map = pavingTexture;
  function strip(
    points: THREE.Vector2[],
    width: number,
    y: number,
    mat: THREE.Material,
  ) {
    const vertices: number[] = [];
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1],
        b = points[i],
        normal = b.clone().sub(a);
      if (normal.length() < 0.01) continue;
      normal.normalize();
      normal.set(-normal.y, normal.x).multiplyScalar(width / 2);
      const p = [
        a.clone().add(normal),
        a.clone().sub(normal),
        b.clone().add(normal),
        b.clone().sub(normal),
      ];
      for (const j of [0, 2, 1, 1, 2, 3]) vertices.push(p[j].x, y, p[j].y);
    }
    const combined = roadVertices.get(mat) || [];
    combined.push(...vertices);
    roadVertices.set(mat, combined);
  }
  // Thin architectural apron follows the unchanged actual building contour.
  for (const feature of features) {
    if (!boundIds.has(feature.properties.building_id || "")) continue;
    const contour = feature.geometry.coordinates[0].map(projectCampus);
    strip(contour, 2.4, 0.1, paving);
  }
  for (const road of roads) {
    if (road.geometry.type !== "LineString") continue;
    const points = road.geometry.coordinates.map(projectCampus),
      type = road.properties.highway;
    const pedestrian = [
        "footway",
        "path",
        "pedestrian",
        "steps",
        "cycleway",
      ].includes(type),
      reported = Number.parseFloat(road.properties.tags?.width || "");
    const width =
      Number.isFinite(reported) && reported >= 0.5 && reported <= 20
        ? reported
        : pedestrian
          ? 2.2
          : type === "service"
            ? 5.5
            : 7;
    strip(points, width + (pedestrian ? 0.9 : 2.4), 0.14, paving);
    strip(points, width, 0.22, pedestrian ? walk : asphalt);
    if (!pedestrian && width >= 5) {
      const geometry = new THREE.BufferGeometry().setFromPoints(
        points.map((p) => new THREE.Vector3(p.x, 0.3, p.y)),
      );
      const line = new THREE.Line(
        geometry,
        new THREE.LineDashedMaterial({
          color: 0xe8ece7,
          dashSize: 3,
          gapSize: 4,
          transparent: true,
          opacity: 0.9,
        }),
      );
      line.computeLineDistances();
      root.add(line);
    }
  }
  for (const [mat, vertices] of roadVertices) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(vertices, 3),
    );
    geometry.setAttribute(
      "uv",
      new THREE.Float32BufferAttribute(
        vertices.flatMap((v, i) =>
          i % 3 === 0 ? [v / 4, vertices[i + 2] / 4] : [],
        ),
        2,
      ),
    );
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, mat);
    mesh.receiveShadow = true;
    mat.side = THREE.DoubleSide;
    root.add(mesh);
  }
  // Reference-style landscaping: illustrative trees, not surveyed tree assets.
  const boundaryRing = boundary.geometry.coordinates[0].map(projectCampus);
  const buildingRings = features.map((f) =>
    f.geometry.coordinates[0].map(projectCampus),
  );
  function contains(p: THREE.Vector2, ring: THREE.Vector2[]) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i],
        b = ring[j];
      if (
        a.y > p.y !== b.y > p.y &&
        p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x
      )
        inside = !inside;
    }
    return inside;
  }
  const trees: THREE.Vector2[] = [],
    crossings: THREE.Matrix4[] = [];
  for (const road of roads) {
    if (
      ["footway", "path", "steps", "cycleway"].includes(road.properties.highway)
    )
      continue;
    const points = road.geometry.coordinates.map(projectCampus);
    for (let i = 1; i < points.length && trees.length < 350; i++) {
      const a = points[i - 1],
        delta = points[i].clone().sub(a),
        length = delta.length();
      if (length < 6) continue;
      const direction = delta.clone().normalize(),
        normal = new THREE.Vector2(-direction.y, direction.x);
      for (let t = 9; t < length; t += 18)
        for (const side of [-1, 1]) {
          const p = a
            .clone()
            .addScaledVector(direction, t)
            .addScaledVector(normal, side * 7.5);
          if (
            contains(p, boundaryRing) &&
            !buildingRings.some((r) => contains(p, r)) &&
            !trees.some((q) => q.distanceTo(p) < 10)
          )
            trees.push(p);
        }
    }
    if (crossings.length < 120 && points.length > 1) {
      const a = points[0],
        b = points[1],
        d = b.clone().sub(a);
      if (d.length() > 15) {
        d.normalize();
        const center = a.clone().addScaledVector(d, 7),
          rotation = new THREE.Quaternion().setFromAxisAngle(
            new THREE.Vector3(0, 1, 0),
            -Math.atan2(d.y, d.x),
          );
        for (let stripe = -2; stripe <= 2; stripe++) {
          const p = center.clone().addScaledVector(d, stripe * 0.85);
          crossings.push(
            new THREE.Matrix4().compose(
              new THREE.Vector3(p.x, 0.34, p.y),
              rotation,
              new THREE.Vector3(0.38, 0.025, 4),
            ),
          );
        }
      }
    }
  }
  if (trees.length) {
    const trunks = new THREE.InstancedMesh(
        new THREE.CylinderGeometry(0.17, 0.24, 2.5, 6),
        material(0x756651),
        trees.length,
      ),
      crowns = new THREE.InstancedMesh(
        new THREE.IcosahedronGeometry(1.55, 0),
        material(0x4f8058),
        trees.length,
      );
    for (let i = 0; i < trees.length; i++) {
      const p = trees[i];
      trunks.setMatrixAt(
        i,
        new THREE.Matrix4().makeTranslation(p.x, 1.25, p.y),
      );
      crowns.setMatrixAt(
        i,
        new THREE.Matrix4().compose(
          new THREE.Vector3(p.x, 3.1, p.y),
          new THREE.Quaternion(),
          new THREE.Vector3(1, 1.25, 1),
        ),
      );
      crowns.setColorAt(
        i,
        new THREE.Color([0x366c50, 0x56815b, 0x638862][i % 3]),
      );
    }
    trunks.userData.presentation_only =
      crowns.userData.presentation_only = true;
    root.add(trunks, crowns);
  }
  if (crossings.length) {
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1, 1, 1),
      material(0xe8ece7),
      crossings.length,
    );
    crossings.forEach((m, i) => mesh.setMatrixAt(i, m));
    mesh.userData.presentation_only = true;
    root.add(mesh);
  }
  return root;
}
