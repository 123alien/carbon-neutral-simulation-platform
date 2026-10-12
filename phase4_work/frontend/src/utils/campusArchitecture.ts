import * as THREE from "three";
import {
  campusFootprintBuilding,
  footprintCenter,
  projectCampus,
  type CampusFeature,
} from "./hbueFootprintBuildings";
export const coreCampusBuildings = new Set([
  "HBUE-B120",
  "HBUE-B119",
  "HBUE-B041",
  "HBUE-B001",
  "HBUE-B002",
  "HBUE-B003",
  "HBUE-B124",
  "HBUE-B125",
]);

/** Purpose-specific illustrative facades on unchanged real footprints.
 * Repeated facade and landscape details share four instance batches.
 */
export function campusArchitecture(
  f: CampusFeature,
  height: number,
  floorCount: number,
) {
  const root = campusFootprintBuilding(f, height, floorCount, false),
    center = footprintCenter(f);
  const ring = f.geometry.coordinates[0]
    .slice(0, -1)
    .map(projectCampus)
    .map((p) => p.sub(center));
  const name = f.properties.name || "",
    lab = /实验/.test(name),
    dorm = /宿舍/.test(name),
    hall = /体育|活动/.test(name),
    office = /行政|香帅/.test(name);
  const materials = [
    new THREE.MeshStandardMaterial({
      color: lab
        ? 0xb7ccd0
        : office
          ? 0xd1bea6
          : hall
            ? 0xd4cfbc
            : dorm
              ? 0xe3d6bf
              : 0xd8e0d9,
      roughness: 0.85,
    }),
    new THREE.MeshStandardMaterial({
      color: lab ? 0x254c62 : 0x304c59,
      roughness: 0.38,
      metalness: 0.18,
    }),
    new THREE.MeshStandardMaterial({
      color: lab ? 0x638b9b : office ? 0x9a846d : hall ? 0xa39b87 : 0x71888d,
      roughness: 0.8,
    }),
  ];
  materials.push(
    new THREE.MeshStandardMaterial({ color: 0x528365, roughness: 0.95 }),
  );
  const batches = materials.map(() => [] as THREE.Matrix4[]),
    floor = Math.max(2, Math.min(12, Math.round(floorCount || 4))),
    step = height / floor;
  const body = root.children[0] as THREE.Mesh;
  const oldMaterials = Array.isArray(body.material)
    ? body.material
    : [body.material];
  for (const old of oldMaterials) {
    if (old === (root.children[1] as THREE.Mesh).material) continue;
    (old as THREE.MeshStandardMaterial).map?.dispose();
    old.dispose();
  }
  body.material = materials[0];
  const area = ring.reduce((sum, a, i) => {
    const b = ring[(i + 1) % ring.length];
    return sum + a.x * b.y - b.x * a.y;
  }, 0);
  function box(
    w: number,
    h: number,
    d: number,
    p: THREE.Vector2,
    y: number,
    angle: number,
    m = 0,
  ) {
    batches[m].push(
      new THREE.Matrix4().compose(
        new THREE.Vector3(p.x, y, p.y),
        new THREE.Quaternion().setFromAxisAngle(
          new THREE.Vector3(0, 1, 0),
          angle,
        ),
        new THREE.Vector3(w, h, d),
      ),
    );
  }
  const edges = ring.map((a, i) => ({ a, b: ring[(i + 1) % ring.length] }));
  for (const { a, b } of edges) {
    const delta = b.clone().sub(a),
      length = delta.length();
    if (length < 2) continue;
    const tangent = delta.clone().normalize(),
      normal = new THREE.Vector2(tangent.y, -tangent.x).multiplyScalar(
        area > 0 ? 1 : -1,
      ),
      angle = -Math.atan2(tangent.y, tangent.x),
      bays = Math.max(1, Math.min(40, Math.floor(length / (hall ? 5 : 3.5))));
    for (let n = 0; n < floor; n++)
      for (let bay = 0; bay < bays; bay++) {
        const p = a
            .clone()
            .addScaledVector(delta, (bay + 0.5) / bays)
            .addScaledVector(normal, 0.09),
          width = (length / bays) * (hall ? 0.82 : lab ? 0.74 : 0.65),
          h = step * (hall ? 0.73 : 0.62),
          y = (n + 0.53) * step;
        box(width + 0.18, h + 0.18, 0.12, p, y, angle);
        box(
          width,
          h,
          0.08,
          p.clone().addScaledVector(normal, 0.08),
          y,
          angle,
          1,
        );
        box(0.07, h, 0.12, p.clone().addScaledVector(normal, 0.15), y, angle);
        box(
          width,
          0.06,
          0.12,
          p.clone().addScaledVector(normal, 0.15),
          y + 0.12 * h,
          angle,
        );
        box(
          width + 0.3,
          0.1,
          0.34,
          p.clone().addScaledVector(normal, 0.19),
          y - h / 2 - 0.08,
          angle,
          2,
        );
        if ((lab || office) && n > 0) {
          box(
            width + 0.35,
            0.12,
            0.65,
            p.clone().addScaledVector(normal, 0.32),
            y + h / 2 + 0.12,
            angle,
            2,
          );
          for (const side of [-1, 1])
            box(
              0.1,
              0.3,
              0.58,
              p
                .clone()
                .addScaledVector(tangent, side * width * 0.42)
                .addScaledVector(normal, 0.3),
              y + h / 2 - 0.02,
              angle,
              0,
            );
        }
        // Individual pane tones suggest reflected sky without transparency passes.
        if ((bay + n) % 5 === 0)
          box(
            width * 0.44,
            h * 0.92,
            0.03,
            p
              .clone()
              .addScaledVector(tangent, -width * 0.25)
              .addScaledVector(normal, 0.14),
            y,
            angle,
            2,
          );
        if (dorm)
          box(
            width + 0.35,
            0.13,
            0.45,
            p.clone().addScaledVector(normal, 0.22),
            n * step + 0.35,
            angle,
            2,
          );
      }
    for (let n = 1; n <= floor; n++)
      box(
        length,
        0.16,
        0.2,
        a.clone().add(b).multiplyScalar(0.5),
        n * step,
        angle,
        2,
      );
    box(
      length,
      0.5,
      0.2,
      a.clone().add(b).multiplyScalar(0.5),
      height + 0.25,
      angle,
    );
    const middle = a.clone().add(b).multiplyScalar(0.5);
    box(
      length,
      0.7,
      0.24,
      middle.clone().addScaledVector(normal, 0.08),
      0.35,
      angle,
      2,
    );
    box(
      length,
      0.16,
      0.42,
      middle.clone().addScaledVector(normal, 0.12),
      height + 0.52,
      angle,
      0,
    );
    // Drainage pipes and contrasting ground-floor base course.
    if (length > 10) {
      const pipe = a
        .clone()
        .addScaledVector(tangent, 0.7)
        .addScaledVector(normal, 0.25);
      box(0.12, height, 0.14, pipe, height / 2, angle, 2);
    }
    // Recessed corner pilasters and taller ground-floor portal articulation.
    for (const p of [a, b])
      box(
        0.42,
        height,
        0.32,
        p.clone().addScaledVector(normal, 0.1),
        height / 2,
        angle,
        2,
      );
    if (office || hall) {
      for (let bay = 0; bay <= bays; bay += 2) {
        const p = a
          .clone()
          .addScaledVector(delta, bay / bays)
          .addScaledVector(normal, 0.2);
        box(0.34, step, 0.4, p, step / 2, angle);
      }
    }
    if (lab)
      for (let bay = 0; bay <= bays; bay++) {
        const p = a
          .clone()
          .addScaledVector(delta, bay / bays)
          .addScaledVector(normal, 0.18);
        box(0.14, height, 0.24, p, height / 2, angle, 2);
      }
  }
  const longest = edges.sort(
    (a, b) => b.a.distanceTo(b.b) - a.a.distanceTo(a.b),
  )[0];
  const delta = longest.b.clone().sub(longest.a).normalize(),
    normal = new THREE.Vector2(delta.y, -delta.x).multiplyScalar(
      area > 0 ? 1 : -1,
    ),
    angle = -Math.atan2(delta.y, delta.x),
    entry = longest.a.clone().add(longest.b).multiplyScalar(0.5);
  box(
    office ? 7 : 5,
    Math.min(height, office ? 6 : 3.5),
    0.2,
    entry.clone().addScaledVector(normal, 0.24),
    office ? 3 : 1.75,
    angle,
    1,
  );
  box(
    office ? 10 : 7,
    0.25,
    2.6,
    entry.clone().addScaledVector(normal, 1.1),
    office ? 4 : 3.4,
    angle,
    2,
  );
  for (const side of [-1, 1])
    box(
      0.5,
      3.4,
      0.5,
      entry
        .clone()
        .addScaledVector(delta, side * 3)
        .addScaledVector(normal, 1.3),
      1.7,
      angle,
    );
  box(
    office ? 12 : 9,
    0.22,
    3.5,
    entry.clone().addScaledVector(normal, 1.4),
    0.12,
    angle,
  );
  for (let n = 0; n < 3; n++)
    box(
      office ? 12 : 9,
      0.12,
      1.1,
      entry.clone().addScaledVector(normal, 3.1 + n * 0.55),
      0.3 - n * 0.08,
      angle,
      0,
    );
  for (const side of [-1, 1]) {
    const rail = entry
      .clone()
      .addScaledVector(delta, side * 2.9)
      .addScaledVector(normal, 3.5);
    box(2.2, 0.08, 0.08, rail, 1.05, angle + Math.PI / 2, 2);
    for (const t of [-0.8, 0, 0.8])
      box(
        0.07,
        0.9,
        0.07,
        rail.clone().addScaledVector(normal, t),
        0.6,
        angle,
        2,
      );
  }
  // Shallow entrance paving with visible expansion joints, not a new footprint.
  box(
    office ? 14 : 11,
    0.08,
    4.8,
    entry.clone().addScaledVector(normal, 5.1),
    0.04,
    angle,
    0,
  );
  for (let n = -4; n <= 4; n++)
    box(
      0.035,
      0.012,
      4.8,
      entry
        .clone()
        .addScaledVector(delta, n * 1.15)
        .addScaledVector(normal, 5.1),
      0.085,
      angle,
      2,
    );
  for (let n = 0; n < 4; n++)
    box(
      office ? 14 : 11,
      0.012,
      0.035,
      entry.clone().addScaledVector(normal, 3 + n * 1.2),
      0.085,
      angle,
      2,
    );
  // Door mullions, lintel and a glazed upper lobby, all batched.
  for (const side of [-1, 0, 1])
    box(
      0.1,
      2.8,
      0.22,
      entry
        .clone()
        .addScaledVector(delta, side * 1.25)
        .addScaledVector(normal, 0.4),
      1.4,
      angle,
      0,
    );
  box(
    5.4,
    0.2,
    0.35,
    entry.clone().addScaledVector(normal, 0.33),
    2.9,
    angle,
    0,
  );
  for (const side of [-1, 1]) {
    const p = entry
      .clone()
      .addScaledVector(delta, side * (office ? 8 : 6))
      .addScaledVector(normal, 2.8);
    box(3, 0.55, 1.3, p, 0.28, angle, 2);
    // Decorative greenery has no business or telemetry identity.
    box(2.8, 0.35, 1.1, p, 0.73, angle, 3);
    const bench = p.clone().addScaledVector(normal, 2);
    box(2.4, 0.16, 0.6, bench, 0.48, angle, 2);
    for (const leg of [-1, 1])
      box(
        0.16,
        0.4,
        0.42,
        bench.clone().addScaledVector(delta, leg * 0.85),
        0.2,
        angle,
        2,
      );
  }
  // Roof plant is architectural illustration, not an invented business device.
  const roofPoint = THREE.ShapeUtils.triangulateShape(ring, [])
    .map((t) => t.map((i) => ring[i]))
    .sort(
      (a, b) =>
        Math.abs(THREE.ShapeUtils.area(b)) - Math.abs(THREE.ShapeUtils.area(a)),
    )[0];
  if (roofPoint) {
    const p = roofPoint
      .reduce((a, b) => a.add(b), new THREE.Vector2())
      .multiplyScalar(1 / 3);
    box(4, 0.12, 2.8, p, height + 0.3, 0, 0);
    box(3.2, 0.8, 2, p, height + 0.76, 0, 2);
    for (let n = -1; n <= 1; n++) {
      box(
        0.55,
        0.08,
        1.5,
        p.clone().add(new THREE.Vector2(n * 0.85, 0)),
        height + 1.2,
        0,
        1,
      );
    }
    for (let n = -4; n <= 4; n++)
      box(
        3.05,
        0.055,
        0.045,
        p.clone().add(new THREE.Vector2(0, n * 0.19)),
        height + 1.21,
        0,
        0,
      );
  }
  batches.forEach((matrices, index) => {
    if (!matrices.length) return;
    const mesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1, 1, 1),
      materials[index],
      matrices.length,
    );
    matrices.forEach((m, i) => mesh.setMatrixAt(i, m));
    mesh.castShadow = mesh.receiveShadow = true;
    root.add(mesh);
  });
  root.userData.architecture = lab
    ? "LAB_SCREEN"
    : dorm
      ? "DORM_LEDGES"
      : hall
        ? "PUBLIC_HALL"
        : office
          ? "OFFICE_PORTAL"
          : "TEACHING_GRID";
  root.userData.detail_instance_count = batches.reduce(
    (sum, b) => sum + b.length,
    0,
  );
  root.userData.model_notice =
    "真实底面；立面、高度和门厅为用途示意，不代表实景测绘复原";
  return root;
}
