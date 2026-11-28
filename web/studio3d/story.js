// PeakCut 3D story visuals: things and happenings the narration talks about (studio/anim3d/story.py picks them,
// studio/anim3d/director.py places and times them). Props (a car, a cake, a kite…) enter the scene, sky effects
// (falling stars, fireworks, rain, lightning…) play, and the camera and the characters look at them.
// Everything is a function of t, like the rest of the runtime.
import * as THREE from "three";

const clamp01 = x => Math.max(0, Math.min(1, x));
const ease = x => { x = clamp01(x); return x * x * (3 - 2 * x); };
const backOut = x => { x = clamp01(x); const c = 1.9; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const bounceOut = x => { x = clamp01(x); const n = 7.5625, d = 2.75;
  if (x < 1 / d) return n * x * x; if (x < 2 / d) return n * (x -= 1.5 / d) * x + 0.75;
  if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + 0.9375; return n * (x -= 2.625 / d) * x + 0.984375; };
function rng(seed) { let s = (seed >>> 0) % 2147483646 + 1; return () => (s = (s * 16807) % 2147483647) / 2147483647; }
const M = (c, r = 0.55, extra = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: r, ...extra });
const B = (c, extra = {}) => new THREE.MeshBasicMaterial({ color: c, ...extra });
function mesh(geo, m, x = 0, y = 0, z = 0) { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; return o; }
const grp = (...o) => { const g = new THREE.Group(); o.forEach(x => g.add(x)); return g; };

// ====================================================================== the things (about 1 unit tall)
export const PROPS = {
  car() {
    const body = mesh(new THREE.BoxGeometry(2.2, 0.6, 1.1), M(0xe74c3c, 0.35), 0, 0.6, 0);
    const glass = mesh(new THREE.BoxGeometry(1.1, 0.46, 0.92), M(0x9fd3ff, 0.12, { metalness: 0.3 }), -0.15, 1.12, 0);
    const roof = mesh(new THREE.BoxGeometry(1.22, 0.09, 1.0), M(0xe74c3c, 0.35), -0.15, 1.38, 0);
    const pillar = mesh(new THREE.BoxGeometry(0.08, 0.46, 0.94), M(0xe74c3c, 0.35), -0.15, 1.12, 0);
    const bumper = mesh(new THREE.BoxGeometry(0.12, 0.16, 1.12), M(0xd0d0d0, 0.3, { metalness: 0.5 }), 1.12, 0.42, 0);
    const g = grp(body, glass, roof, pillar, bumper), wheels = [];
    for (const [x, z] of [[-0.7, 0.56], [0.7, 0.56], [-0.7, -0.56], [0.7, -0.56]]) {
      const w = mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.22, 18), M(0x222222, 0.8), x, 0.3, z); w.rotation.x = Math.PI / 2; g.add(w); wheels.push(w);
      w.add(mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.24, 12), M(0xd0d0d0, 0.3, { metalness: 0.6 })));   // hubcap
    }
    for (const z of [0.3, -0.3]) g.add(mesh(new THREE.SphereGeometry(0.09, 10, 8), B(0xfff2a0), 1.11, 0.68, z));
    return { g, size: 1.5, wheels };
  },
  bicycle() {
    const g = new THREE.Group(), wheels = [];
    for (const x of [-0.6, 0.6]) { const w = mesh(new THREE.TorusGeometry(0.38, 0.05, 8, 24), M(0x222222, 0.7), x, 0.4, 0); g.add(w); wheels.push(w); }
    const bar = (a, b) => { const v = new THREE.Vector3().subVectors(b, a), m = mesh(new THREE.CylinderGeometry(0.04, 0.04, v.length(), 8), M(0x2f7fe0, 0.4));
      m.position.copy(a).add(b).multiplyScalar(0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.normalize()); g.add(m); };
    const P = (x, y) => new THREE.Vector3(x, y, 0);
    bar(P(-0.6, 0.4), P(0, 0.45)); bar(P(0, 0.45), P(0.45, 0.95)); bar(P(-0.6, 0.4), P(-0.25, 0.95)); bar(P(-0.25, 0.95), P(0.45, 0.95)); bar(P(0.6, 0.4), P(0.45, 0.95));
    g.add(mesh(new THREE.BoxGeometry(0.3, 0.06, 0.15), M(0x222222), -0.25, 1.0, 0));
    return { g, size: 1.1, wheels };
  },
  ball() { const g = grp(mesh(new THREE.SphereGeometry(0.35, 24, 16), M(0xffffff, 0.4), 0, 0.35, 0),
      mesh(new THREE.TorusGeometry(0.35, 0.05, 8, 28), M(0xe74c3c, 0.4), 0, 0.35, 0)); return { g, size: 0.7 }; },
  cake() {
    const g = grp(mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.45, 28), M(0xf6a5c0, 0.5), 0, 0.225, 0),
      mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.32, 28), M(0xfff3e0, 0.5), 0, 0.61, 0),
      mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.3, 8), M(0x5aa8f0), 0, 0.92, 0),
      mesh(new THREE.ConeGeometry(0.05, 0.12, 8), B(0xffb02e), 0, 1.13, 0));
    for (let k = 0; k < 8; k++) g.add(mesh(new THREE.SphereGeometry(0.06, 8, 6), M(0xe74c3c, 0.4), Math.cos(k * 0.785) * 0.42, 0.79, Math.sin(k * 0.785) * 0.42));
    return { g, size: 1.2, flame: true };
  },
  gift() { return { g: grp(mesh(new THREE.BoxGeometry(0.75, 0.65, 0.75), M(0x8e5bd9, 0.5), 0, 0.33, 0),
      mesh(new THREE.BoxGeometry(0.78, 0.67, 0.14), M(0xffd23f, 0.4), 0, 0.33, 0), mesh(new THREE.BoxGeometry(0.14, 0.67, 0.78), M(0xffd23f, 0.4), 0, 0.33, 0),
      mesh(new THREE.TorusGeometry(0.13, 0.05, 8, 16), M(0xffd23f, 0.4), -0.1, 0.72, 0), mesh(new THREE.TorusGeometry(0.13, 0.05, 8, 16), M(0xffd23f, 0.4), 0.1, 0.72, 0)), size: 0.9 }; },
  box() { return { g: grp(mesh(new THREE.BoxGeometry(0.85, 0.7, 0.85), M(0xb07a4a, 0.8), 0, 0.35, 0),
      mesh(new THREE.BoxGeometry(0.87, 0.08, 0.2), M(0x7a4b28, 0.8), 0, 0.5, 0)), size: 0.8 }; },
  treasure() {
    const g = grp(mesh(new THREE.BoxGeometry(1.1, 0.6, 0.7), M(0x8a5a2b, 0.7), 0, 0.3, 0),
      mesh(new THREE.BoxGeometry(1.14, 0.1, 0.74), M(0xf2c14e, 0.3, { metalness: 0.6 }), 0, 0.45, 0));
    const lid = mesh(new THREE.CylinderGeometry(0.35, 0.35, 1.1, 16, 1, false, 0, Math.PI), M(0x8a5a2b, 0.7), 0, 0.6, 0); lid.rotation.z = Math.PI / 2; lid.rotation.y = Math.PI / 2; g.add(lid);
    for (let k = 0; k < 6; k++) g.add(mesh(new THREE.SphereGeometry(0.09, 8, 6), B(0xffe066), -0.35 + k * 0.14, 0.66, 0.15 * Math.sin(k)));
    const l = new THREE.PointLight(0xffd36b, 2.5, 4); l.position.set(0, 1.0, 0.4); g.add(l);
    return { g, size: 1.0 };
  },
  book() { return { g: grp(mesh(new THREE.BoxGeometry(0.75, 0.14, 0.95), M(0xc0392b, 0.6), 0, 0.07, 0), mesh(new THREE.BoxGeometry(0.7, 0.12, 0.88), M(0xfdf6e3, 0.8), 0.03, 0.07, 0)), size: 0.6 }; },
  letter() { const g = grp(mesh(new THREE.BoxGeometry(0.7, 0.03, 0.46), M(0xfdf6e3, 0.8), 0, 0.03, 0), mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.04, 14), M(0xc0392b), 0, 0.05, 0)); return { g, size: 0.5 }; },
  map() {
    const p = mesh(new THREE.BoxGeometry(1.1, 0.02, 0.8), M(0xf0deb0, 0.9), 0, 0.03, 0);
    const g = grp(p); for (const x of [-0.55, 0.55]) { const r = mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.82, 10), M(0xd9c08a), x, 0.06, 0); r.rotation.x = Math.PI / 2; g.add(r); }
    for (const a of [0.7, -0.7]) { const x = mesh(new THREE.BoxGeometry(0.22, 0.01, 0.04), B(0xc0392b), 0.2, 0.05, 0.1); x.rotation.y = a; g.add(x); }
    return { g, size: 0.6 };
  },
  key() { const m = M(0xf2c14e, 0.25, { metalness: 0.7 }); const ring = mesh(new THREE.TorusGeometry(0.18, 0.05, 8, 20), m, -0.35, 0.05, 0); ring.rotation.x = Math.PI / 2;
    return { g: grp(ring, mesh(new THREE.BoxGeometry(0.6, 0.06, 0.08), m, 0.08, 0.05, 0), mesh(new THREE.BoxGeometry(0.06, 0.06, 0.16), m, 0.3, 0.05, 0.08), mesh(new THREE.BoxGeometry(0.06, 0.06, 0.12), m, 0.18, 0.05, 0.06)), size: 0.5 }; },
  phone() { return { g: grp(mesh(new THREE.BoxGeometry(0.36, 0.72, 0.06), M(0x222222, 0.3), 0, 0.36, 0), mesh(new THREE.PlaneGeometry(0.31, 0.6), B(0x5ac8fa), 0, 0.37, 0.031)), size: 0.8 }; },
  clock() {
    const face = mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.14, 32), M(0xfdf6e3, 0.6), 0, 0.5, 0); face.rotation.x = Math.PI / 2;
    const rim = mesh(new THREE.TorusGeometry(0.42, 0.05, 8, 32), M(0xe74c3c, 0.4), 0, 0.5, 0);
    const h1 = mesh(new THREE.BoxGeometry(0.04, 0.26, 0.02), B(0x222222), 0, 0.6, 0.08), h2 = mesh(new THREE.BoxGeometry(0.2, 0.04, 0.02), B(0x222222), 0.08, 0.5, 0.08);
    return { g: grp(face, rim, h1, h2, mesh(new THREE.SphereGeometry(0.12, 12, 8), M(0xe74c3c), -0.3, 0.92, 0), mesh(new THREE.SphereGeometry(0.12, 12, 8), M(0xe74c3c), 0.3, 0.92, 0)), size: 1.0, hand: h1 };
  },
  lantern() {
    const g = grp(mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.08, 16), M(0x333333), 0, 0.04, 0), mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.5, 16, 1, true), M(0xffe9a8, 0.2, { transparent: true, opacity: 0.55 }), 0, 0.33, 0),
      mesh(new THREE.ConeGeometry(0.32, 0.22, 16), M(0x333333), 0, 0.69, 0), mesh(new THREE.TorusGeometry(0.12, 0.025, 6, 16), M(0x333333), 0, 0.86, 0), mesh(new THREE.SphereGeometry(0.11, 12, 8), B(0xffc24a), 0, 0.33, 0));
    const l = new THREE.PointLight(0xffc24a, 3, 6); l.position.y = 0.4; g.add(l); return { g, size: 0.9, light: l };
  },
  candle() { const g = grp(mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.55, 14), M(0xfdf6e3, 0.6), 0, 0.27, 0), mesh(new THREE.ConeGeometry(0.06, 0.16, 10), B(0xffa62b), 0, 0.64, 0));
    const l = new THREE.PointLight(0xffa62b, 2, 4); l.position.y = 0.7; g.add(l); return { g, size: 0.7, light: l, flame: true }; },
  fire() {
    const g = new THREE.Group();
    for (let k = 0; k < 4; k++) { const log = mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.9, 8), M(0x6b4423, 0.9), 0, 0.1, 0); log.rotation.z = Math.PI / 2; log.rotation.y = k * 0.8; g.add(log); }
    const flames = [0xff5a1f, 0xff9a2e, 0xffd23f].map((c, i) => { const f = mesh(new THREE.ConeGeometry(0.32 - i * 0.08, 0.9 - i * 0.2, 12), B(c, { transparent: true, opacity: 0.9 }), 0, 0.5 - i * 0.05, 0); g.add(f); return f; });
    const l = new THREE.PointLight(0xff8a2e, 4, 8); l.position.y = 0.8; g.add(l); return { g, size: 1.0, light: l, flames };
  },
  flower() {
    const g = new THREE.Group();
    for (const [x, c] of [[-0.3, 0xf06292], [0, 0xffd23f], [0.3, 0xb57bff]]) {
      g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.7, 6), M(0x4caf50), x, 0.35, 0));
      for (let k = 0; k < 6; k++) g.add(mesh(new THREE.SphereGeometry(0.08, 8, 6), M(c, 0.5), x + Math.cos(k * 1.05) * 0.11, 0.74, Math.sin(k * 1.05) * 0.11));
      g.add(mesh(new THREE.SphereGeometry(0.06, 8, 6), M(0xff9800), x, 0.74, 0));
    }
    return { g, size: 0.8 };
  },
  apple() { return { g: grp(mesh(new THREE.SphereGeometry(0.3, 20, 14), M(0xd62828, 0.35), 0, 0.3, 0), mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.14, 6), M(0x6b4423), 0, 0.64, 0),
      mesh(new THREE.SphereGeometry(0.08, 8, 6), M(0x4caf50), 0.08, 0.66, 0)), size: 0.7 }; },
  mango() { const m = mesh(new THREE.SphereGeometry(0.3, 20, 14), M(0xffb02e, 0.4), 0, 0.3, 0); m.scale.set(1, 1.25, 0.9); return { g: grp(m), size: 0.75 }; },
  laddoo() { const g = grp(mesh(new THREE.CylinderGeometry(0.6, 0.5, 0.08, 28), M(0xc0c0c0, 0.3, { metalness: 0.6 }), 0, 0.04, 0));
    for (const [x, y, z] of [[-0.2, 0.2, 0.12], [0.2, 0.2, 0.12], [0, 0.2, -0.2], [0, 0.48, 0]]) g.add(mesh(new THREE.SphereGeometry(0.17, 14, 10), M(0xf59e0b, 0.7), x, y, z));
    return { g, size: 0.8 }; },
  honey() { const pot = mesh(new THREE.SphereGeometry(0.38, 20, 14), M(0xd98e2b, 0.5), 0, 0.38, 0); pot.scale.y = 0.9;
    return { g: grp(pot, mesh(new THREE.CylinderGeometry(0.24, 0.28, 0.16, 18), M(0xd98e2b, 0.5), 0, 0.74, 0), mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.06, 18), M(0xf2c14e, 0.4), 0, 0.84, 0),
      mesh(new THREE.BoxGeometry(0.4, 0.2, 0.02), M(0xfdf6e3), 0, 0.4, 0.37)), size: 0.9 }; },
  icecream() { return { g: grp(mesh(new THREE.ConeGeometry(0.2, 0.6, 16), M(0xd9a066, 0.7), 0, 0.3, 0).rotateX(Math.PI),
      mesh(new THREE.SphereGeometry(0.22, 16, 12), M(0xf6a5c0, 0.5), 0, 0.68, 0), mesh(new THREE.SphereGeometry(0.2, 16, 12), M(0x8bd3c7, 0.5), 0, 0.92, 0)), size: 1.0 }; },
  egg() { const e = mesh(new THREE.SphereGeometry(0.25, 20, 14), M(0xfff8e7, 0.4), 0, 0.32, 0); e.scale.y = 1.3; return { g: grp(e), size: 0.7 }; },
  umbrella() { const top = mesh(new THREE.ConeGeometry(0.9, 0.45, 16), M(0xe74c3c, 0.5), 0, 1.4, 0);
    return { g: grp(top, mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.4, 8), M(0x333333), 0, 0.7, 0), mesh(new THREE.TorusGeometry(0.1, 0.03, 6, 12, Math.PI), M(0x333333), 0.1, 0.02, 0)), size: 1.6 }; },
  drum() { return { g: grp(mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.8, 24), M(0xc0392b, 0.6), 0, 0.4, 0), mesh(new THREE.CylinderGeometry(0.44, 0.44, 0.06, 24), M(0xfdf6e3, 0.7), 0, 0.81, 0),
      mesh(new THREE.CylinderGeometry(0.44, 0.44, 0.06, 24), M(0xfdf6e3, 0.7), 0, 0.02, 0)), size: 0.9 }; },
  crown() { const m = M(0xf2c14e, 0.25, { metalness: 0.8 }); const g = grp(mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.22, 24, 1, true), m, 0, 0.11, 0));
    for (let k = 0; k < 6; k++) { const a = k * 1.047; g.add(mesh(new THREE.ConeGeometry(0.09, 0.26, 8), m, Math.cos(a) * 0.4, 0.34, Math.sin(a) * 0.4)); g.add(mesh(new THREE.SphereGeometry(0.05, 8, 6), B([0xe74c3c, 0x5aa8f0, 0x4caf50][k % 3]), Math.cos(a) * 0.42, 0.11, Math.sin(a) * 0.42)); }
    return { g, size: 0.5 }; },
  kite() { const s = new THREE.Shape(); s.moveTo(0, 0.6); s.lineTo(0.42, 0); s.lineTo(0, -0.75); s.lineTo(-0.42, 0); s.lineTo(0, 0.6);
    const g = grp(mesh(new THREE.ShapeGeometry(s), M(0xff4d8d, 0.5, { side: THREE.DoubleSide }), 0, 0, 0));
    for (let k = 0; k < 5; k++) g.add(mesh(new THREE.BoxGeometry(0.12, 0.08, 0.02), M([0xffd23f, 0x5aa8f0][k % 2]), Math.sin(k) * 0.1, -0.9 - k * 0.22, 0));
    return { g, size: 1.2 }; },
  balloons() { const g = new THREE.Group();
    for (const [x, y, c] of [[-0.35, 1.6, 0xe74c3c], [0.3, 1.75, 0x5aa8f0], [0, 2.0, 0xffd23f]]) { const b = mesh(new THREE.SphereGeometry(0.32, 18, 14), M(c, 0.3), x, y, 0); b.scale.y = 1.15; g.add(b);
      const v = new THREE.Vector3(x, y - 0.35, 0), o = new THREE.Vector3(0, 0.1, 0), d = new THREE.Vector3().subVectors(v, o);
      const st = mesh(new THREE.CylinderGeometry(0.008, 0.008, d.length(), 4), M(0xffffff)); st.position.copy(v).add(o).multiplyScalar(0.5); st.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); g.add(st); }
    return { g, size: 2.2 }; },
  orb() { const g = grp(mesh(new THREE.SphereGeometry(0.28, 24, 16), B(0xfff6b0), 0, 0, 0), mesh(new THREE.SphereGeometry(0.45, 24, 16), B(0xffe066, { transparent: true, opacity: 0.25 }), 0, 0, 0));
    const l = new THREE.PointLight(0xffe066, 4, 7); g.add(l); return { g, size: 0.9, light: l, glow: g.children[1] }; },
  bell() { const pts = []; for (let i = 0; i <= 10; i++) { const u = i / 10; pts.push(new THREE.Vector2(0.08 + 0.32 * u * u + 0.04 * Math.sin(u * 3), 0.7 - u * 0.65)); }
    return { g: grp(mesh(new THREE.LatheGeometry(pts, 24), M(0xf2c14e, 0.25, { metalness: 0.8, side: THREE.DoubleSide }), 0, 0, 0), mesh(new THREE.SphereGeometry(0.07, 8, 6), M(0x7a4b28), 0, 0.03, 0)), size: 0.8 }; },
  boat() { const hull = mesh(new THREE.BoxGeometry(1.6, 0.35, 0.6), M(0x8a5a2b, 0.7), 0, 0.18, 0);
    const s = new THREE.Shape(); s.moveTo(0, 0); s.lineTo(0, 1.1); s.lineTo(0.7, 0); s.lineTo(0, 0);
    return { g: grp(hull, mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.3, 6), M(0x6b4423), 0, 0.95, 0), mesh(new THREE.ShapeGeometry(s), M(0xfdf6e3, 0.7, { side: THREE.DoubleSide }), 0.03, 0.4, 0)), size: 1.4 }; },
  rocket() { const g = grp(mesh(new THREE.CylinderGeometry(0.3, 0.35, 1.4, 18), M(0xf4f4f4, 0.4), 0, 0.9, 0), mesh(new THREE.ConeGeometry(0.3, 0.6, 18), M(0xe74c3c, 0.4), 0, 1.9, 0),
      mesh(new THREE.ConeGeometry(0.22, 0.5, 12), B(0xffa62b), 0, 0.0, 0).rotateX(Math.PI));
    for (let k = 0; k < 3; k++) { const f = mesh(new THREE.BoxGeometry(0.05, 0.45, 0.4), M(0xe74c3c, 0.4), Math.cos(k * 2.1) * 0.32, 0.4, Math.sin(k * 2.1) * 0.32); f.rotation.y = -k * 2.1; g.add(f); }
    return { g, size: 2.0 }; },
  ghost() {
    const m = M(0xf4f7ff, 0.6, { transparent: true, opacity: 0.82, emissive: 0x8899cc, emissiveIntensity: 0.35 });
    const body = mesh(new THREE.CylinderGeometry(0.35, 0.6, 1.2, 20, 1, true), m, 0, 0.75, 0);
    const g = grp(mesh(new THREE.SphereGeometry(0.42, 20, 14), m, 0, 1.4, 0), body,
      mesh(new THREE.SphereGeometry(0.07, 8, 6), B(0x111111), -0.14, 1.48, 0.36), mesh(new THREE.SphereGeometry(0.07, 8, 6), B(0x111111), 0.14, 1.48, 0.36),
      mesh(new THREE.SphereGeometry(0.09, 8, 6), B(0x111111), 0, 1.25, 0.38));
    return { g, size: 1.8 };
  },
};


// ====================================================================== places named in a line (seen far off, or in a
// thought bubble): real size, a few units tall; "size" is about their height, for the camera
const place = (parts, size) => ({ g: grp(...parts), size });
const FAR = 1.6;   // a place seen far off is built bigger, so it stands over the roofs and trees in between
function tiers(x, y, z, w, n, c) { const o = []; for (let k = 0; k < n; k++) { const s = w * (1 - k * 0.15); o.push(mesh(new THREE.BoxGeometry(s, 0.7, s), M(c, 0.8), x, y + k * 0.66, z)); } return o; }
Object.assign(PROPS, {
  place_temple() {
    const st = 0xe8d2a8;
    return place([mesh(new THREE.BoxGeometry(4.4, 0.6, 4.4), M(st, 0.85), 0, 0.3, 0), mesh(new THREE.BoxGeometry(2.8, 2.0, 2.8), M(st, 0.85), 0, 1.6, 0),
      mesh(new THREE.BoxGeometry(0.9, 1.4, 0.1), M(0x3a2614), 0, 1.3, 1.42), ...tiers(0, 2.9, 0, 2.4, 6, st),
      mesh(new THREE.SphereGeometry(0.22, 12, 8), M(0xf2c14e, 0.3, { metalness: 0.6 }), 0, 6.9, 0),
      mesh(new THREE.PlaneGeometry(0.8, 0.45), M(0xff8a1f, 0.7, { side: THREE.DoubleSide }), 0.4, 7.6, 0),
      mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.2, 6), M(0x5a3a22), 0, 7.4, 0)], 7);
  },
  place_haveli() {
    const wall = 0xe8a86a, trim = 0xb0502a, parts = [mesh(new THREE.BoxGeometry(8, 5, 3), M(wall, 0.85), 0, 2.5, 0),
      mesh(new THREE.BoxGeometry(8.4, 0.3, 3.4), M(trim, 0.8), 0, 5.1, 0)];
    for (const x of [-2.6, 0, 2.6]) {
      parts.push(mesh(new THREE.BoxGeometry(1.1, 1.8, 0.1), M(0x5a3a22), x, 0.9, 1.52));
      parts.push(mesh(new THREE.BoxGeometry(1.4, 0.9, 0.6), M(trim, 0.8), x, 3.6, 1.6));
    }
    for (let k = -3; k <= 3; k++) parts.push(mesh(new THREE.BoxGeometry(0.6, 0.6, 0.6), M(wall, 0.85), k * 1.2, 5.55, 1.4));
    return place(parts, 6);
  },
  place_palace() {
    const sand = 0xe8b878, parts = [mesh(new THREE.BoxGeometry(10, 5, 2), M(sand, 0.85), 0, 2.5, 0)];
    for (const x of [-5, 5]) { parts.push(mesh(new THREE.CylinderGeometry(1.1, 1.2, 7.5, 14), M(sand, 0.85), x, 3.75, 0));
      parts.push(mesh(new THREE.SphereGeometry(1.2, 14, 10, 0, Math.PI * 2, 0, Math.PI / 2), M(0xf3e3c3, 0.6), x, 7.5, 0)); }
    parts.push(mesh(new THREE.SphereGeometry(1.8, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), M(0xf3e3c3, 0.6), 0, 5, 0));
    parts.push(mesh(new THREE.BoxGeometry(1.6, 2.4, 0.1), M(0x3a2614), 0, 1.2, 1.02));
    return place(parts, 8);
  },
  place_castle() {
    const st = 0x9a9a98, parts = [mesh(new THREE.BoxGeometry(10, 5.5, 2), M(st, 0.9), 0, 2.75, 0)];
    for (let k = -4; k <= 4; k++) parts.push(mesh(new THREE.BoxGeometry(0.7, 0.7, 2.1), M(st, 0.9), k * 1.1, 5.85, 0));
    for (const x of [-5.5, 5.5]) { parts.push(mesh(new THREE.CylinderGeometry(1.3, 1.4, 8, 14), M(st, 0.9), x, 4, 0));
      parts.push(mesh(new THREE.ConeGeometry(1.7, 2.6, 14), M(0x3a4a8a, 0.7), x, 9.3, 0)); }
    parts.push(mesh(new THREE.BoxGeometry(1.8, 2.6, 0.1), M(0x4a3020), 0, 1.3, 1.02));
    return place(parts, 9);
  },
  place_mountain() {
    const parts = [];
    for (const [x, h, r] of [[0, 18, 11], [-12, 13, 8], [11, 14, 9]]) {
      parts.push(mesh(new THREE.ConeGeometry(r, h, 7), M(0x7a8a6a, 0.95), x, h / 2, 0));
      parts.push(mesh(new THREE.ConeGeometry(r * 0.32, h * 0.3, 7), M(0xf4f6fa, 0.8), x, h * 0.86, 0));
    }
    return place(parts, 18);
  },
  place_river() { return place([mesh(new THREE.CylinderGeometry(1.6, 1.6, 0.1, 24), M(0x3f8fd0, 0.2, { metalness: 0.2 }), 0, 0.05, 0),
    mesh(new THREE.TorusGeometry(0.8, 0.04, 6, 24), B(0xd9f0ff), 0, 0.12, 0), mesh(new THREE.TorusGeometry(1.3, 0.04, 6, 30), B(0xd9f0ff), 0, 0.12, 0)], 1.2); },
  place_lake() { return PROPS.place_river(); },
  place_waterfall() {
    return place([mesh(new THREE.BoxGeometry(5, 6, 2), M(0x8a7a66, 0.95), 0, 3, -0.6), mesh(new THREE.PlaneGeometry(1.8, 6), B(0xe6f6ff), 0, 3, 0.45),
      mesh(new THREE.CylinderGeometry(2.4, 2.4, 0.12, 24), M(0x3f8fd0, 0.2), 0, 0.06, 1.6)], 6);
  },
  place_school() {
    const parts = [mesh(new THREE.BoxGeometry(7, 3.2, 3), M(0xfff1c9, 0.85), 0, 1.6, 0), mesh(new THREE.BoxGeometry(7.4, 0.4, 3.4), M(0xc0582f, 0.8), 0, 3.4, 0),
      mesh(new THREE.BoxGeometry(2.6, 0.7, 0.1), M(0x2f7fe0, 0.6), 0, 2.7, 1.52), mesh(new THREE.BoxGeometry(1.1, 1.8, 0.1), M(0x5a3a22), 0, 0.9, 1.52),
      mesh(new THREE.CylinderGeometry(0.05, 0.05, 4.5, 6), M(0x9a9a9a), 4.2, 2.25, 1.6), mesh(new THREE.PlaneGeometry(1.1, 0.7), M(0xff8a1f, 0.7, { side: THREE.DoubleSide }), 4.75, 4.1, 1.6)];
    for (const x of [-2.4, 2.4]) parts.push(mesh(new THREE.BoxGeometry(1, 0.8, 0.1), M(0x9fd3ff, 0.2), x, 1.7, 1.52));
    return place(parts, 4.5);
  },
  place_hospital() {
    return place([mesh(new THREE.BoxGeometry(6, 4.4, 3), M(0xf6f8fa, 0.8), 0, 2.2, 0), mesh(new THREE.BoxGeometry(1.6, 0.45, 0.1), M(0xd8343c, 0.6), 0, 3.4, 1.52),
      mesh(new THREE.BoxGeometry(0.45, 1.6, 0.1), M(0xd8343c, 0.6), 0, 3.4, 1.53), mesh(new THREE.BoxGeometry(1.4, 1.8, 0.1), M(0x9fd3ff, 0.2), 0, 0.9, 1.52)], 5);
  },
  place_train() {
    const parts = [mesh(new THREE.BoxGeometry(2.6, 1.6, 1.4), M(0x2f5aa0, 0.6), -3.4, 1.2, 0), mesh(new THREE.CylinderGeometry(0.6, 0.6, 2, 16), M(0x2a2a2a, 0.6), -1.6, 1.1, 0),
      mesh(new THREE.CylinderGeometry(0.18, 0.24, 0.8, 10), M(0x2a2a2a, 0.6), -1.0, 2.1, 0)];
    parts[1].rotation.z = Math.PI / 2;
    for (const x of [1.4, 4.6]) { parts.push(mesh(new THREE.BoxGeometry(3, 1.6, 1.4), M(0xc0392b, 0.6), x, 1.2, 0));
      for (const dx of [-0.8, 0, 0.8]) parts.push(mesh(new THREE.BoxGeometry(0.5, 0.45, 0.05), M(0xfff1c9, 0.4), x + dx, 1.45, 0.72)); }
    for (let x = -4; x <= 5.5; x += 1.6) { const w = mesh(new THREE.CylinderGeometry(0.3, 0.3, 1.5, 12), M(0x222222, 0.8), x, 0.3, 0); w.rotation.x = Math.PI / 2; parts.push(w); }
    return place(parts, 2.6);
  },
  place_tree() {
    const parts = [mesh(new THREE.CylinderGeometry(0.45, 0.7, 4, 10), M(0x6e4224, 0.9), 0, 2, 0)];
    for (const [x, y, z, r] of [[0, 5.2, 0, 2.4], [-1.6, 4.4, 0.4, 1.7], [1.7, 4.5, -0.3, 1.8], [0.3, 6.4, 0.2, 1.6]])
      parts.push(mesh(new THREE.SphereGeometry(r, 14, 10), M(0x3f8a34, 0.85), x, y, z));
    return place(parts, 7);
  },
  place_well() {
    const parts = [mesh(new THREE.CylinderGeometry(1, 1.05, 0.9, 18, 1, true), M(0x9a8a76, 0.95, { side: THREE.DoubleSide }), 0, 0.45, 0),
      mesh(new THREE.CylinderGeometry(0.95, 0.95, 0.05, 18), M(0x1f3550, 0.2), 0, 0.5, 0)];
    for (const x of [-0.9, 0.9]) parts.push(mesh(new THREE.BoxGeometry(0.12, 2.2, 0.12), M(0x6e4224), x, 1.1, 0));
    parts.push(mesh(new THREE.ConeGeometry(1.5, 0.8, 4), M(0xb0502a, 0.8), 0, 2.5, 0));
    return place(parts, 2.6);
  },
  place_hut() {
    return place([mesh(new THREE.CylinderGeometry(1.6, 1.7, 1.8, 16), M(0xc9a27a, 0.95), 0, 0.9, 0), mesh(new THREE.ConeGeometry(2.2, 1.8, 16), M(0xd9b45a, 0.9), 0, 2.7, 0),
      mesh(new THREE.BoxGeometry(0.7, 1.2, 0.1), M(0x5a3a22), 0, 0.6, 1.66)], 3.5);
  },
  place_tower() {
    return place([mesh(new THREE.CylinderGeometry(0.9, 1.3, 10, 12), M(0xd9c2a0, 0.85), 0, 5, 0), mesh(new THREE.CylinderGeometry(1.4, 1.4, 0.5, 12), M(0xb0502a, 0.8), 0, 10.2, 0),
      mesh(new THREE.SphereGeometry(0.9, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), M(0xf3e3c3, 0.6), 0, 10.4, 0)], 10);
  },
  place_bridge() {
    const deck = mesh(new THREE.BoxGeometry(8, 0.35, 1.6), M(0x9a8a76, 0.9), 0, 1.8, 0);
    const arch = mesh(new THREE.TorusGeometry(2.2, 0.35, 8, 20, Math.PI), M(0x9a8a76, 0.9), 0, 0, 0);
    return place([deck, arch, mesh(new THREE.BoxGeometry(8, 0.05, 3), M(0x3f8fd0, 0.2), 0, 0.03, 0)], 3);
  },
  place_cave() {
    const rock = mesh(new THREE.DodecahedronGeometry(3.2), M(0x7a7266, 0.95), 0, 2.2, 0); rock.scale.set(1.3, 0.9, 0.8);
    return place([rock, mesh(new THREE.CircleGeometry(1.1, 18), M(0x0d0b0a, 1), 0, 1.2, 2.3)], 5);
  },
});

function bubbleCloud() {   // a thought bubble: a white cloud with two small puffs leading down to the speaker
  const m = M(0xffffff, 0.9, { emissive: 0xffffff, emissiveIntensity: 0.25 });
  const g = new THREE.Group();
  for (const [x, y, r] of [[0, 0, 0.75], [-0.6, -0.05, 0.5], [0.6, -0.05, 0.5], [-0.3, 0.32, 0.5], [0.32, 0.3, 0.52]]) { const s = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 12), m); s.position.set(x, y, -0.25); s.scale.z = 0.45; g.add(s); }
  for (const [x, y, r] of [[-0.55, -0.85, 0.16], [-0.8, -1.2, 0.1]]) { const s = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), m); s.position.set(x, y, 0); g.add(s); }
  return g;
}

// ====================================================================== happenings in the world and the sky
function buildFx(scene, f, R) {
  const fx = { ...f, parts: [] };
  const add = o => { scene.add(o); fx.parts.push(o); o.visible = false; return o; };
  const glowM = c => B(c, { transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false });
  if (f.name === "falling_stars") {
    for (let i = 0; i < 26; i++) {
      const tail = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.09, 3.2, 6), glowM(0xfff2b0)); tail.position.y = 1.6;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 8), glowM(0xffffff));
      const s = add(new THREE.Group()); s.add(tail, head);
      const dir = R() < 0.5 ? -1 : 1;
      s.userData = { start: f.t0 + i * 0.17 + R() * 0.2, life: 1.0 + R() * 0.5, x: (R() - 0.5) * 30, y: 15 + R() * 8, z: -16 - R() * 12, dx: dir * (5 + R() * 4), dy: -(10 + R() * 5) };
      s.rotation.z = Math.atan2(-s.userData.dx, -s.userData.dy) * -1;
    }
  } else if (f.name === "stars") {
    for (let i = 0; i < 140; i++) { const s = add(new THREE.Mesh(new THREE.SphereGeometry(0.09 + R() * 0.1, 6, 4), glowM(0xffffff))); s.position.set((R() - 0.5) * 70, 7 + R() * 26, -38 - R() * 8); s.userData = { ph: R() * 6 }; }
  } else if (f.name === "rain" || f.name === "snowfall") {
    const snow = f.name === "snowfall";
    const geo = snow ? new THREE.SphereGeometry(0.045, 6, 4) : new THREE.BoxGeometry(0.012, 0.42, 0.012);
    const m = B(snow ? 0xffffff : 0xb8d8ff, { transparent: true, opacity: snow ? 0.95 : 0.55 });
    for (let i = 0; i < (snow ? 260 : 380); i++) { const p = add(new THREE.Mesh(geo, m)); p.userData = { x: (R() - 0.5) * 26, z: -10 + R() * 18, y0: R() * 12, sp: snow ? 0.8 + R() * 0.6 : 13 + R() * 5, ph: R() * 6 }; }
  } else if (f.name === "lightning") {
    const bolt = add(new THREE.Group()), m = glowM(0xe8f0ff);
    let x = (R() - 0.5) * 16, y = 24;
    for (let k = 0; k < 7; k++) { const nx = x + (R() - 0.5) * 3, ny = y - 2.6, v = new THREE.Vector3(nx - x, ny - y, 0);
      const seg = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, v.length(), 5), m); seg.position.set((x + nx) / 2, (y + ny) / 2, -26);
      seg.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.normalize()); bolt.add(seg); x = nx; y = ny; }
    fx.flash = new THREE.AmbientLight(0xdfe8ff, 0); scene.add(fx.flash);
  } else if (f.name === "fireworks") {
    const cols = [0xff4d6d, 0xffd23f, 0x5ae0ff, 0x9dff6b, 0xd78bff];
    fx.bursts = [];
    for (let b = 0; b < 6; b++) {
      const at = { t: f.t0 + 0.2 + b * 0.75, x: (R() - 0.5) * 22, y: 11 + R() * 6, z: -24 - R() * 6, c: cols[b % cols.length] };
      const trail = add(new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 6), glowM(0xfff2b0)));
      const sparks = [];
      for (let i = 0; i < 46; i++) { const s = add(new THREE.Mesh(new THREE.SphereGeometry(0.11, 6, 4), glowM(at.c)));
        const th = R() * Math.PI * 2, ph = Math.acos(2 * R() - 1), sp = 3.5 + R() * 1.5; s.userData = { vx: Math.sin(ph) * Math.cos(th) * sp, vy: Math.cos(ph) * sp, vz: Math.sin(ph) * Math.sin(th) * sp }; sparks.push(s); }
      fx.bursts.push({ at, trail, sparks });
    }
  } else if (f.name === "rainbow") {
    [0xff3b30, 0xff9500, 0xffcc00, 0x34c759, 0x007aff, 0x5856d6].forEach((c, i) => {
      const a = add(new THREE.Mesh(new THREE.TorusGeometry(15 - i * 0.55, 0.28, 8, 60, Math.PI), B(c, { transparent: true, opacity: 0.0, depthWrite: false })));
      a.position.set(2, -1, -34);
    });
  } else if (f.name === "moon" || f.name === "sun") {
    const moon = f.name === "moon";
    const g = add(new THREE.Group());
    g.add(new THREE.Mesh(new THREE.SphereGeometry(moon ? 2.2 : 2.8, 28, 20), B(moon ? 0xfff6d5 : 0xffd23f)));
    g.add(new THREE.Mesh(new THREE.SphereGeometry(moon ? 3.4 : 4.6, 28, 20), B(moon ? 0xfff6d5 : 0xffb02e, { transparent: true, opacity: 0.18, depthWrite: false })));
    g.userData = { x: moon ? 9 : -10, y: 15, z: -42 };
  } else if (f.name === "birds") {
    for (let i = 0; i < 9; i++) {
      const m = M(0x2a2a2a, 0.8, { side: THREE.DoubleSide }), b = add(new THREE.Group());
      const l = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.03, 0.22), m), r = l.clone(); l.position.x = -0.35; r.position.x = 0.35;
      const wl = new THREE.Group(); wl.add(l); const wr = new THREE.Group(); wr.add(r); b.add(wl, wr);
      b.userData = { wl, wr, row: i, x0: -30 - (i % 3) * 1.6 - Math.floor(i / 3) * 0.8, y: 10 + (i % 3) * 0.9 + R(), z: -18 - Math.floor(i / 3) * 1.2, ph: R() * 6 };
    }
  } else if (f.name === "butterflies") {
    for (let i = 0; i < 6; i++) {
      const c = [0xff8ad8, 0xffd23f, 0x7ad0ff][i % 3], m = M(c, 0.5, { side: THREE.DoubleSide }), b = add(new THREE.Group());
      const l = new THREE.Mesh(new THREE.CircleGeometry(0.16, 12), m), r = l.clone(); l.position.x = -0.15; r.position.x = 0.15;
      const wl = new THREE.Group(); wl.add(l); const wr = new THREE.Group(); wr.add(r); b.add(wl, wr);
      b.userData = { wl, wr, x: (R() - 0.5) * 7, y: 1.2 + R() * 1.4, z: -0.5 + R() * 2.5, ph: R() * 6 };
    }
  } else if (f.name === "sparkles") {
    for (let i = 0; i < 40; i++) { const s = add(new THREE.Mesh(new THREE.OctahedronGeometry(0.07), glowM([0xffffff, 0xfff27a, 0xffc8f0][i % 3])));
      const th = R() * Math.PI * 2, el = (R() - 0.3) * 1.4; s.userData = { vx: Math.cos(th) * (0.6 + R()), vy: el, vz: Math.sin(th) * (0.6 + R()), ph: R() * 6 }; }
  } else if (f.name === "wind") {
    for (let i = 0; i < 70; i++) { const p = add(new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.1), M([0xd9822b, 0x8bc34a, 0xf2c14e][i % 3], 0.8, { side: THREE.DoubleSide })));
      p.userData = { y: 0.4 + R() * 4, z: -6 + R() * 10, x0: R() * 30, sp: 6 + R() * 4, ph: R() * 6 }; }
  }
  return fx;
}

function updateFx(fx, t, story) {
  const on = t >= fx.t0 && t <= fx.t1 + 1.5;
  const k = clamp01((t - fx.t0) / 0.8) * clamp01((fx.t1 + 1.5 - t) / 1.5);
  if (!on) { fx.parts.forEach(p => { p.visible = false; }); if (fx.flash) fx.flash.intensity = 0; return; }
  const dt = t - fx.t0;
  if (fx.name === "falling_stars") {
    fx.parts.forEach(s => { const d = s.userData, u = (t - d.start) / d.life;
      s.visible = u >= 0 && u <= 1;
      if (s.visible) { s.position.set(d.x + d.dx * (t - d.start), d.y + d.dy * (t - d.start), d.z); s.scale.setScalar(1 - u * 0.5); } });
  } else if (fx.name === "stars") {
    fx.parts.forEach(s => { s.visible = true; s.scale.setScalar(k * (0.6 + 0.4 * Math.sin(t * 3 + s.userData.ph))); });
  } else if (fx.name === "rain" || fx.name === "snowfall") {
    const snow = fx.name === "snowfall";
    fx.parts.forEach(p => { const d = p.userData; p.visible = k > 0.05;
      const y = 12 - ((d.y0 + t * d.sp) % 12);
      p.position.set(d.x + (snow ? Math.sin(t * 0.9 + d.ph) * 0.5 : 0.08 * y), y, d.z); });
  } else if (fx.name === "lightning") {
    const pulse = [0, 0.12, 0.75].some(o => dt >= o && dt < o + 0.09);
    fx.parts.forEach(p => { p.visible = pulse; });
    fx.flash.intensity = pulse ? 3.2 : Math.max(0, 1.2 - (dt - 0.84) * 6) * (dt > 0.84 ? 1 : 0);
  } else if (fx.name === "fireworks") {
    for (const b of fx.bursts) {
      const u = t - b.at.t;
      b.trail.visible = u > -0.7 && u < 0;
      if (b.trail.visible) b.trail.position.set(b.at.x, b.at.y - 7 * (-u / 0.7), b.at.z);
      b.sparks.forEach(s => { const d = s.userData, live = u >= 0 && u < 1.6; s.visible = live;
        if (live) { s.position.set(b.at.x + d.vx * u, b.at.y + d.vy * u - 2.2 * u * u, b.at.z + d.vz * u); s.scale.setScalar(Math.max(0.05, 1 - u / 1.6)); } });
    }
  } else if (fx.name === "rainbow") {
    fx.parts.forEach(a => { a.visible = true; a.material.opacity = 0.55 * k; });
  } else if (fx.name === "moon" || fx.name === "sun") {
    const g = fx.parts[0], d = g.userData; g.visible = true; g.position.set(d.x, d.y - 4 * (1 - ease(dt / 2.2)), d.z); g.scale.setScalar(0.4 + 0.6 * k);
  } else if (fx.name === "birds") {
    fx.parts.forEach(b => { const d = b.userData; b.visible = true;
      b.position.set(d.x0 + dt * 10, d.y + Math.sin(dt * 2 + d.ph) * 0.3, d.z); b.rotation.y = 0;
      const f = Math.sin(t * 14 + d.ph) * 0.7; d.wl.rotation.z = f; d.wr.rotation.z = -f; });
  } else if (fx.name === "butterflies") {
    fx.parts.forEach(b => { const d = b.userData; b.visible = true;
      b.position.set(d.x + Math.sin(t * 0.8 + d.ph) * 1.5, d.y + Math.sin(t * 1.7 + d.ph) * 0.4, d.z + Math.cos(t * 0.6 + d.ph) * 0.8);
      b.rotation.y = t * 0.8 + d.ph; const f = Math.sin(t * 18 + d.ph) * 1.1; d.wl.rotation.y = f; d.wr.rotation.y = -f; b.scale.setScalar(k); });
  } else if (fx.name === "sparkles") {
    const at = story.pointOf(fx, t), u = clamp01(dt / 2.0);
    fx.parts.forEach(s => { const d = s.userData; s.visible = u < 1;
      s.position.set(at.x + d.vx * u * 1.6, at.y + d.vy * u * 1.6 + Math.sin(t * 4 + d.ph) * 0.05, at.z + d.vz * u * 1.6);
      s.rotation.set(t * 4 + d.ph, t * 3, 0); s.scale.setScalar(Math.sin(Math.PI * u) * 1.4); });
  } else if (fx.name === "wind") {
    fx.parts.forEach(p => { const d = p.userData; p.visible = true;
      p.position.set(-15 + ((d.x0 + dt * d.sp) % 30), d.y + Math.sin(t * 3 + d.ph) * 0.4, d.z); p.rotation.set(t * 5 + d.ph, t * 3, t * 4); });
  }
}

// ====================================================================== the story of a scene
export function buildStory(scene, spec, cast) {
  const st = spec.story || {}, R = rng((spec.seed || 1) + 991);
  const story = { props: [], fx: [], looks: st.looks || [], cast };
  for (const p of st.props || []) try {   // one thing that fails to build is left out; the scene still renders
    const make = PROPS[p.name] || PROPS.orb, built = make();
    const g = built.g; g.visible = false;
    let holder = g;
    if (p.how === "bubble") {   // the thing, small, inside a thought bubble over the speaker
      holder = new THREE.Group(); const cloud = bubbleCloud(); holder.add(cloud);
      g.scale.setScalar(0.5 / Math.max(0.6, built.size)); g.position.set(0, -0.25, 0.15); holder.add(g); g.visible = true; holder.visible = false;
    }
    scene.add(holder);
    story.props.push({ ...p, g, holder, built, side: p.x <= 0 ? -1 : 1 });
  } catch (e) { console.warn("story prop", p.name, e); }
  for (const f of st.fx || []) try { story.fx.push(buildFx(scene, f, R)); } catch (e) { console.warn("story fx", f.name, e); }
  story.pointOf = (fx, t) => {   // where a sparkle burst happens: over its speaker's head, or the middle of the scene
    const c = fx.who && cast[fx.who];
    return c ? new THREE.Vector3(c.root.position.x, c.headY * c.scale + 0.3, c.root.position.z + 0.3) : new THREE.Vector3(0, 2.2, 1);
  };
  return story;
}

export function updateStory(story, t) {
  if (!story) return;
  for (const p of story.props) {
    const live = t >= p.t0 && t <= p.t1 + (p.how === "bubble" ? 0.3 : 0);
    p.holder.visible = live;
    if (!live) continue;
    const dt = t - p.t0, g = p.g, b = p.built;
    if (p.how === "bubble") {
      const c = story.cast[p.who];
      if (c) { const hy = c.headY * c.scale + c.root.position.y; p.holder.position.set(c.root.position.x + p.side * -0.2 + 0.9, hy + 1.35, c.root.position.z + 0.2); }
      const s = backOut(dt / 0.45) * clamp01((p.t1 + 0.3 - t) / 0.3);
      p.holder.scale.setScalar(Math.max(0.001, s)); g.rotation.y = Math.sin(t * 1.5) * 0.4;
      continue;
    }
    let x = p.x, y = 0, z = p.z, s = 1;
    if (p.how === "pop") s = backOut(dt / 0.45);
    else if (p.how === "drop") y = 6 * (1 - bounceOut(dt / 0.9));
    else if (p.how === "drive") { const u = ease(dt / 1.7); x = p.x + p.side * 13 * (1 - u); g.rotation.y = p.side < 0 ? 0 : Math.PI;   // in from its own side, facing the way it goes
      (b.wheels || []).forEach(w => { w.rotation.y = 0; w.rotation[w.geometry.type === "TorusGeometry" ? "z" : "y"] = -(13 * (1 - u)) / 0.3 * p.side; }); }
    else if (p.how === "float") { s = backOut(dt / 0.6); y = 0.6 + Math.sin(t * 1.6) * 0.15; if (p.name === "ghost") { x = p.x + Math.sin(t * 0.7) * 0.4; y = 0.3 + Math.sin(t * 1.3) * 0.2; } }
    else if (p.how === "far") { const u = backOut(dt / 0.9); g.visible = true; g.position.set(x, 0, z); g.scale.set(FAR, FAR * Math.max(0.001, u), FAR);
      if (b.light) b.light.intensity = 0; continue; }   // a place over there rises into view and stays
    else if (p.how === "fly") { s = backOut(dt / 0.4); const up = Math.max(0, dt - 0.5); y = Math.min(9, up * up * 0.9 + up * 1.2); x = p.x + Math.sin(t * 1.2) * 0.4 * clamp01(up); if (p.name === "kite") { y += 0.8; g.rotation.z = Math.sin(t * 2) * 0.25; } }
    g.visible = true; g.position.set(x, y, z); g.scale.setScalar(Math.max(0.001, s));
    if (b.light) b.light.intensity = (b.light.userData.base ??= b.light.intensity) * (0.8 + 0.25 * Math.sin(t * 17) * Math.sin(t * 7.3));
    if (b.flames) b.flames.forEach((f, i) => { f.scale.set(1, 0.85 + 0.25 * Math.sin(t * (11 + i * 3) + i), 1); });
    if (b.glow) b.glow.scale.setScalar(1 + 0.15 * Math.sin(t * 4));
    if (b.hand) b.hand.rotation.z = -t * 2;
  }
  for (const f of story.fx) updateFx(f, t, story);
}

// where a prop is now (for the cut-in shot and for the characters to look at)
export function propPoint(story, id) {
  const p = story && story.props.find(x => x.id === id);
  if (!p) return null;
  const v = new THREE.Vector3(); (p.how === "bubble" ? p.holder : p.g).getWorldPosition(v);
  return { v, size: p.how === "bubble" ? 1.4 : p.built.size * (p.how === "far" ? FAR : 1), p };
}

// the characters look at what the story shows (a prop, or up at the sky)
export function storyLook(story, t, c) {
  if (!story) return null;
  const L = story.looks.find(l => t >= l.t0 && t <= l.t1 && (!l.who || l.who.includes(c.id)));
  if (!L) return null;
  let tx, ty, tz;
  if (L.prop) { const pp = propPoint(story, L.prop); if (!pp) return null; tx = pp.v.x; ty = pp.v.y + pp.size * 0.4; tz = pp.v.z; }
  else [tx, ty, tz] = L.at;
  const hy = c.headY * c.scale + c.root.position.y, dx = tx - c.root.position.x, dz = tz - c.root.position.z;
  const yaw = Math.atan2(dx, dz), pitch = -Math.atan2(ty - hy, Math.hypot(dx, dz));
  const u = clamp01((t - L.t0) / 0.35) * clamp01((L.t1 - t) / 0.35);
  return { yaw, pitch: Math.max(-0.75, Math.min(0.45, pitch)), u };
}

// the story's own shots: "sky" (looking up past the cast), "insert" (a cut-in on a prop), "bubble" (the speaker and
// their thought bubble). Returns true when it placed the camera.
export function storyCamera(story, sh, u, cam, cx, cast) {
  if (sh.kind === "landmark") {   // turn to a place: from the characters' side, towards it, pushing in slowly
    let tx, ty, tz, size;
    if (sh.target) {   // a place far off: over the characters' heads, from up and close behind them, looking out to it
      const pp = propPoint(story, sh.target); if (!pp) return false;
      tx = pp.v.x; tz = pp.v.z; size = pp.size; ty = size * 0.5;
      cam.position.set(cx * 0.7 + tx * 0.15, 9.5 + u * 0.3, 5 - u * 1.0);   // high, over the treetops and roofs between
      cam.lookAt(tx, ty, tz);
      return true;
    }
    else if (sh.at) [tx, ty, tz, size] = sh.at;
    else return false;
    const dx = cx - tx, dz = 4 - tz, L = Math.hypot(dx, dz) || 1;
    const d = Math.min(L, size * 2.2 + 3) * (1 - 0.1 * u);
    cam.position.set(tx + dx / L * d + Math.sin(u * 0.8) * 0.3, Math.max(1.3, ty * 0.5 + 0.9), tz + dz / L * d);
    cam.lookAt(tx, ty, tz);
    return true;
  }
  if (sh.kind === "sky") {
    cam.position.set(cx + Math.sin(u * 1.2) * 0.5, 1.15, 7.8 - u * 0.6);
    cam.lookAt(cx, 6.2 + u * 1.6, -14);
    return true;
  }
  if (sh.kind === "insert") {
    const pp = propPoint(story, sh.target); if (!pp) return false;
    const d = 2.0 + pp.size * 1.7, side = pp.p.side || 1;
    cam.position.set(pp.v.x - side * d * 0.35, pp.v.y + 0.45 + pp.size * 0.45, pp.v.z + d - u * 0.4);
    cam.lookAt(pp.v.x, pp.v.y + pp.size * 0.42, pp.v.z);
    return true;
  }
  if (sh.kind === "bubble") {
    const c = cast[sh.target]; if (!c) return false;
    const hy = c.headY * c.scale + c.root.position.y;
    cam.position.set(c.root.position.x + 1.4, hy + 0.7, c.root.position.z + 4.6 - u * 0.3);
    cam.lookAt(c.root.position.x + 0.5, hy + 0.75, c.root.position.z);
    return true;
  }
  return false;
}
