// PeakCut 3D set kits: the places a scene can happen (studio/anim3d/sets.py picks the kit, the time and the
// weather from the scene). Each kit is built from simple parts, keeps the cast area clear (|x| < 7, -4.5 < z < 6)
// and dresses the background, sides and a little of the foreground. Same seed → same layout.
import * as THREE from "three";
import { PROPS } from "./story.js";

// ---------------------------------------------------------------- small helpers shared by the kits
function box(K, w, h, d, c, x, y, z, r = 0.85) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), K.mat(c, r)); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; K.scene.add(m); return m;
}
function cyl(K, r1, r2, h, c, x, y, z, seg = 16, r = 0.8) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, seg), K.mat(c, r)); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; K.scene.add(m); return m;
}
function plane(K, w, d, c, x, y, z, r = 0.95) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), K.mat(c, r)); m.rotation.x = -Math.PI / 2; m.position.set(x, y, z); m.receiveShadow = true; K.scene.add(m); return m;
}
const glow = c => new THREE.MeshBasicMaterial({ color: c });
function flame(K, x, y, z, s = 1, light = false) {
  const f = new THREE.Mesh(new THREE.ConeGeometry(0.05 * s, 0.14 * s, 8), glow(0xffb02e)); f.position.set(x, y + 0.07 * s, z); K.scene.add(f);
  if (light) { const l = new THREE.PointLight(0xffa64a, 2.2, 6); l.position.set(x, y + 0.4, z); K.scene.add(l); }
  halo(K, x, y + 0.1 * s, z, 0.5 * s, 0xffb84a, 0.8);   // every flame glows softly
  return f;
}
function diya(K, x, z, y = 0, light = false) {
  const d = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 6, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), K.mat(0xb5532b, 0.7)); d.position.set(x, y + 0.09, z); K.scene.add(d);
  flame(K, x, y + 0.08, z, 1, light);
}
function prop(K, name, x, z, rotY = 0, s = 1) {
  const b = PROPS[name] && PROPS[name](); if (!b) return null;
  b.g.position.set(x, 0, z); b.g.rotation.y = rotY; b.g.scale.setScalar(s); K.scene.add(b.g); return b.g;
}
function walls(K, wallC, floorC, opts = {}) {   // an indoor room: floor, back and side walls, a window
  const floor = plane(K, 30, 30, floorC, 0, 0, 0, 0.8);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(30, 9), K.mat(wallC, 0.95)); back.position.set(0, 4.5, -5); back.receiveShadow = true; K.scene.add(back);
  for (const s of [-1, 1]) { const side = new THREE.Mesh(new THREE.PlaneGeometry(20, 9), K.mat(wallC, 0.95)); side.position.set(s * 11, 4.5, 3); side.rotation.y = -s * Math.PI / 2; K.scene.add(side); }
  const skirting = box(K, 30, 0.25, 0.08, opts.trim || 0x8a6a4a, 0, 0.12, -4.95);
  if (opts.window !== false) {
    const night = ["night", "midnight", "dusk"].includes(K.w.time) || K.w.mood === "night" || K.w.mood === "dark";
    const win = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.2), glow(night ? 0x1b2650 : 0x9fd3ff)); win.position.set(opts.winX ?? -3.5, 3.6, -4.98); K.scene.add(win);
    box(K, 3.4, 0.12, 0.1, 0xffffff, opts.winX ?? -3.5, 3.6, -4.9); box(K, 0.12, 2.3, 0.1, 0xffffff, opts.winX ?? -3.5, 3.6, -4.9);
  }
  const lamp = new THREE.PointLight(0xffe2b0, 1.3, 16); lamp.position.set(0, 6, 1); K.scene.add(lamp);
  return floor;
}
function shikhara(K, x, z, s, stone, flagC = 0xff8a1f) {   // a temple tower: tapering stacked tiers, a pot on top and a flag
  for (let k = 0; k < 6; k++) { const w = (2.2 - k * 0.32) * s; box(K, w, 0.75 * s, w, stone, x, (2.6 + k * 0.72) * s, z, 0.9); }
  const kalash = new THREE.Mesh(new THREE.SphereGeometry(0.22 * s, 14, 10), K.mat(0xf2c14e, 0.3, { metalness: 0.6 })); kalash.position.set(x, 7.2 * s, z); K.scene.add(kalash);
  cyl(K, 0.03 * s, 0.03 * s, 1.4 * s, 0x5a3a22, x, 7.9 * s, z, 6);
  const flag = new THREE.Mesh(new THREE.PlaneGeometry(0.8 * s, 0.45 * s), K.mat(flagC, 0.7, { side: THREE.DoubleSide })); flag.position.set(x + 0.4 * s, 8.35 * s, z); K.scene.add(flag);
}
function building(K, x, z, w, h, d, c, litWindows, rot = 0) {   // a city or town building with a window grid
  const g = new THREE.Group();
  const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), K.mat(c, 0.85)); b.position.y = h / 2; b.castShadow = b.receiveShadow = true; g.add(b);
  const R = K.R, cols = Math.max(1, Math.floor(w / 1.3)), rows = Math.max(1, Math.floor(h / 1.6));
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
    const lit = litWindows && R() < 0.55;
    const wdw = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.8), lit ? glow(0xffe49a) : K.mat(0x9fc3dd, 0.2));
    wdw.position.set(-w / 2 + (i + 0.5) * (w / cols), 1.2 + j * 1.6, d / 2 + 0.01); g.add(wdw);
  }
  g.position.set(x, 0, z); g.rotation.y = rot; K.scene.add(g); return g;
}
function awning(K, x, z, w, c1, c2) {
  const g = new THREE.Group();
  for (let k = 0; k < 6; k++) { const s = new THREE.Mesh(new THREE.BoxGeometry(w / 6, 0.05, 1.5), K.mat(k % 2 ? c1 : c2, 0.7)); s.position.set(-w / 2 + (k + 0.5) * w / 6, 2.3, 0.4); s.rotation.x = 0.25; g.add(s); }
  g.position.set(x, 0, z); K.scene.add(g);
}
function stall(K, x, z, rot, c1, c2) {   // a market stall: counter, awning, crates of fruit
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = rot; K.scene.add(g);
  const add = m => { m.castShadow = m.receiveShadow = true; g.add(m); return m; };
  add(new THREE.Mesh(new THREE.BoxGeometry(2.4, 1, 1), K.mat(0x8a5a2b, 0.8))).position.y = 0.5;
  for (const px of [-1.15, 1.15]) add(new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.4, 6), K.mat(0x5a3a22))).position.set(px, 1.2, 0.45);
  for (let k = 0; k < 6; k++) { const s = add(new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.05, 1.4), K.mat(k % 2 ? c1 : c2, 0.7))); s.position.set(-1.05 + k * 0.42, 2.4, 0.15); s.rotation.x = 0.22; }
  const fruit = [0xff8a1f, 0xd8343c, 0xf2c12e, 0x4caf50];
  for (let k = 0; k < 9; k++) add(new THREE.Mesh(new THREE.SphereGeometry(0.11, 10, 8), K.mat(fruit[k % 4], 0.5))).position.set(-0.9 + (k % 9) * 0.22, 1.1, 0.15 + (k % 2) * 0.15);
  return g;
}
function stringLights(K, x0, x1, y, z, n = 14) {
  for (let k = 0; k <= n; k++) { const x = x0 + (x1 - x0) * k / n; const b = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 6), glow([0xffe066, 0xff6fa5, 0x7ad0ff, 0x9dff6b][k % 4])); b.position.set(x, y - Math.sin(Math.PI * k / n) * 0.6, z); K.scene.add(b); }
}
function pillar(K, x, z, h, c, r = 0.3) { cyl(K, r * 1.25, r * 1.3, 0.3, c, x, 0.15, z, 12); cyl(K, r, r, h, c, x, h / 2 + 0.3, z, 14); box(K, r * 2.6, 0.3, r * 2.6, c, x, h + 0.45, z); }
function mountains(K, snow = true) {
  for (let i = 0; i < 7; i++) {
    const x = -55 + i * 18 + (K.R() - 0.5) * 6, h = 26 + K.R() * 18, r = 15 + K.R() * 7;
    const m = new THREE.Mesh(new THREE.ConeGeometry(r, h, 7), K.mat(i % 2 ? 0x7d8a9c : 0x8f9bab, 1)); m.position.set(x, h / 2 - 1, -55 - K.R() * 10); K.scene.add(m);
    if (snow) { const cap = new THREE.Mesh(new THREE.ConeGeometry(r * 0.36, h * 0.36, 7), K.mat(0xf4f7fb, 0.8)); cap.position.set(x, h - 1 - h * 0.18, m.position.z); K.scene.add(cap); }
  }
}
function water(K, w, d, x, z, c = 0x2f8fc8) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), K.mat(c, 0.15, { metalness: 0.2 })); m.rotation.x = -Math.PI / 2; m.position.set(x, 0.03, z); m.userData.sea = true; K.scene.add(m);
  for (let k = 0; k < 12; k++) { const s = new THREE.Mesh(new THREE.PlaneGeometry(0.8 + K.R(), 0.05), glow(0xcfe8ff)); s.rotation.x = -Math.PI / 2; s.position.set(x + (K.R() - 0.5) * w * 0.8, 0.04, z + (K.R() - 0.5) * d * 0.8); K.scene.add(s); }
  return m;
}
function reeds(K, n, x0, x1, z0, z1) { for (let i = 0; i < n; i++) { const r = new THREE.Mesh(new THREE.ConeGeometry(0.04, 0.9 + K.R() * 0.6, 4), K.mat(0x6b8f3a, 0.9)); r.position.set(x0 + K.R() * (x1 - x0), 0.45, z0 + K.R() * (z1 - z0)); r.rotation.z = (K.R() - 0.5) * 0.3; K.scene.add(r); } }
const isNight = K => ["night", "midnight", "dusk"].includes(K.w.time) || ["night", "dark"].includes(K.w.mood);
const ancient = K => K.w.era === "ancient";
const indian = K => (K.w.culture || "indian") === "indian";

// ---------------------------------------------------------------- the kits
export const KITS = {
  temple: { ground: 0xd9c8a6, build(K) {
    const stone = ancient(K) ? 0xc9a77a : 0xe8d2a8;
    box(K, 9, 0.6, 6, stone, 0, 0.3, -12); for (let k = 0; k < 3; k++) box(K, 5 - k * 0.6, 0.25, 0.6, stone, 0, 0.12 + k * 0.25, -8.7 - k * 0.6);
    box(K, 3.6, 2.4, 3.2, stone, 0, 1.8, -12); box(K, 1.1, 1.8, 0.1, 0x3a2614, 0, 1.5, -10.35);
    shikhara(K, 0, -12, 1, stone);
    for (const s of [-1, 1]) {   // pillared halls on both sides
      for (let k = 0; k < 4; k++) pillar(K, s * (8 + (k % 2) * 2.4), -5 - Math.floor(k / 2) * 3, 2.8, stone, 0.22);
      box(K, 3.6, 0.35, 4.4, stone, s * 9.2, 3.35, -6.5);
    }
    const bell = new THREE.Mesh(new THREE.SphereGeometry(0.35, 16, 10, 0, Math.PI * 2, 0, Math.PI / 1.6), K.mat(0xc9a24a, 0.3, { metalness: 0.7, side: THREE.DoubleSide })); bell.position.set(-2.6, 3.2, -9); bell.rotation.x = Math.PI; K.scene.add(bell);
    box(K, 1.8, 0.1, 0.1, 0x5a3a22, -2.6, 3.6, -9); for (const x of [-3.4, -1.8]) cyl(K, 0.06, 0.06, 3.6, 0x5a3a22, x, 1.8, -9, 6);
    for (let k = -6; k <= 6; k++) diya(K, k * 0.6, -8.4, 0.75, k === 0 || Math.abs(k) === 5);
    K.tree(-11, -12, 1.5, [0x3f8a34, 0x4f9a3a]); K.tree(12, -13, 1.3, [0x3f8a34, 0x4f9a3a]);
    if (indian(K)) for (let k = 0; k < 8; k++) { const p = new THREE.Mesh(new THREE.CircleGeometry(0.22, 8), K.mat([0xff6fa5, 0xffd23f, 0xff8a1f, 0x7ad0ff][k % 4], 0.6)); p.rotation.x = -Math.PI / 2; p.position.set(-1.4 + (k % 4) * 0.9, 0.02, 3.5 + Math.floor(k / 4) * 0.7); K.scene.add(p); }
  } },
  palace: { ground: 0xe0c89a, build(K) {
    const sand = ancient(K) ? 0xd49a5a : 0xe8b878, trim = 0xb06a3a;
    box(K, 60, 7, 1.6, sand, 0, 3.5, -16); for (let k = -14; k <= 14; k++) box(K, 1, 0.9, 1.7, sand, k * 2.1, 7.4, -16);
    const arch = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.35, 8, 20, Math.PI), K.mat(trim, 0.8)); arch.position.set(0, 3.2, -15.1); K.scene.add(arch);
    box(K, 3.2, 3.2, 0.2, 0x3a2614, 0, 1.6, -15.15);
    for (const x of [-9, 9, -20, 20]) {
      cyl(K, 1.6, 1.8, 10, sand, x, 5, -15.5, 16);
      const dome = new THREE.Mesh(new THREE.SphereGeometry(1.7, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), K.mat(0xf3e3c3, 0.6)); dome.position.set(x, 10, -15.5); K.scene.add(dome);
      cyl(K, 0.03, 0.03, 1.6, 0x5a3a22, x, 12.2, -15.5, 6);
      const fl = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.55), K.mat(0xff8a1f, 0.7, { side: THREE.DoubleSide })); fl.position.set(x + 0.5, 12.7, -15.5); K.scene.add(fl);
    }
    for (const s of [-1, 1]) {   // chhatris on the courtyard sides
      for (const [dx, dz] of [[-0.9, -0.9], [0.9, -0.9], [-0.9, 0.9], [0.9, 0.9]]) cyl(K, 0.12, 0.12, 2.6, sand, s * 10 + dx, 1.3, -7 + dz, 8);
      box(K, 2.4, 0.25, 2.4, trim, s * 10, 2.7, -7);
      const d = new THREE.Mesh(new THREE.SphereGeometry(1.0, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), K.mat(0xf3e3c3, 0.6)); d.position.set(s * 10, 2.8, -7); K.scene.add(d);
    }
    for (let k = 0; k < 10; k++) plane(K, 2, 2, k % 2 ? 0xd9c2a0 : 0xc9aa7a, -9 + k * 2, 0.01, -2.5);
    for (const x of [-6.5, 6.5]) { cyl(K, 0.5, 0.6, 0.8, 0xc0582f, x, 0.4, -9, 12); K.tree && K.tree(x, -9, 0.45, [0x3f8a34]); }
  } },
  ruins: { ground: 0xb8a77a, build(K) {
    const st = 0xa89a82;
    for (let k = 0; k < 9; k++) { const x = (k % 2 ? -1 : 1) * (7.5 + (k % 4) * 2.2) + (K.R() - 0.5), z = -6 - Math.floor(k / 2) * 3.2; const h = 1 + K.R() * 4.5; pillar(K, x, z, h, st, 0.32); }
    for (let k = 0; k < 3; k++) { const p = cyl(K, 0.32, 0.32, 3.2, st, -3 + k * 3.5, 0.32, -10 - k * 2, 14); p.rotation.z = Math.PI / 2; p.rotation.y = K.R(); }
    for (let k = 0; k < 6; k++) { const w = 2 + K.R() * 3, h = 1 + K.R() * 3; box(K, w, h, 0.8, st, (K.R() - 0.5) * 30, h / 2, -14 - K.R() * 8); }
    box(K, 14, 0.8, 1.2, st, 0, 6.5, -12);   // a broken lintel high up
    K.rocks(16); K.tufts(140, 0x6f8f3a); K.hills(0x9bae7a);
    K.forest([0x4f7f3a, 0x5f8f44], 18);
  } },
  ghat: { ground: 0xcbb48a, build(K) {
    water(K, 120, 40, 0, -32);
    for (let k = 0; k < 7; k++) box(K, 60, 0.4, 1.4, k % 2 ? 0xc9a77a : 0xbf9a6a, 0, -0.2 - k * 0.4, -6.5 - k * 1.4);
    for (const x of [-12, 11]) shikhara(K, x, -9, 0.55, 0xe0b080);
    for (const x of [-7, 7.5, -16]) { cyl(K, 0.04, 0.04, 2.4, 0x5a3a22, x, 1.2, -7, 6); const u = new THREE.Mesh(new THREE.ConeGeometry(1.4, 0.5, 12), K.mat([0xd8343c, 0xff8a1f, 0x2f7fe0][Math.abs(x) % 3], 0.7)); u.position.set(x, 2.5, -7); K.scene.add(u); }
    for (let k = 0; k < 22; k++) diya(K, (K.R() - 0.5) * 30, -18 - K.R() * 14, 0.02, k < 2);
    for (const [x, z] of [[-9, -22], [8, -26]]) { const b = box(K, 4, 0.6, 1.4, 0x8a5a2b, x, 0.25, z); b.rotation.y = 0.2; }
    for (let k = -8; k <= 8; k += 2) diya(K, k, -6.2, 0.2, false);
    building(K, -22, -4, 6, 8, 4, 0xf0b9a0, isNight(K), 0.3); building(K, 22, -4, 6, 9, 4, 0xf3d7a6, isNight(K), -0.3);
  } },
  bazaar: { ground: 0xc8b48c, build(K) {
    const cols = [[0xd8343c, 0xffffff], [0xf2c12e, 0x2f7fe0], [0x3f9a3a, 0xffffff], [0xff8a1f, 0x8e5bd8], [0x1fa2a0, 0xffd23f]];
    for (let k = 0; k < 5; k++) { stall(K, -9 - (k % 2) * 0.4, -4 - k * 3.2, Math.PI / 2 - 0.2, ...cols[k % 5]); stall(K, 9 + (k % 2) * 0.4, -5 - k * 3.2, -Math.PI / 2 + 0.2, ...cols[(k + 2) % 5]); }
    for (let k = 0; k < 4; k++) { building(K, -15, -4 - k * 6, 5, 6 + k, 5, [0xf3d7a6, 0xf0b9a0, 0xd9e7f5, 0xfff1c9][k], isNight(K), Math.PI / 2); building(K, 15, -4 - k * 6, 5, 7 + (k % 2) * 2, 5, [0xf0b9a0, 0xfff1c9, 0xf3d7a6, 0xd9e7f5][k], isNight(K), -Math.PI / 2); }
    for (let k = 0; k < 3; k++) stall(K, -4.5 + k * 4.5, -9.5 - (k % 2), 0, ...cols[(k + 1) % 5]);
    stringLights(K, -9, 9, 4.6, -6); stringLights(K, -9, 9, 4.8, -12);
    for (let k = 0; k < 30; k++) { const c = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 0.3), K.mat([0x8a5a2b, 0xc9a24a][k % 2], 0.9)); c.position.set((K.R() < 0.5 ? -1 : 1) * (7.3 + K.R() * 1.2), 0.15 + (k % 3) * 0.3, -3 - K.R() * 12); K.scene.add(c); }
    if (indian(K)) {   // a chai stall and a rickshaw
      box(K, 1.6, 1, 0.9, 0x6e4224, 5, 0.5, 2.5); const k1 = cyl(K, 0.2, 0.25, 0.4, 0xc0c0c0, 5, 1.2, 2.5, 12); k1.material = K.mat(0xc0c0c0, 0.3, { metalness: 0.6 });
      const rk = new THREE.Group(); const body = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.3, 1.2), K.mat(0xf2c12e, 0.6)); body.position.y = 1; rk.add(body);
      const top = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.12, 1.3), K.mat(0x1a1a1a, 0.6)); top.position.y = 1.72; rk.add(top);
      for (const [x, z] of [[0.7, 0.55], [0.7, -0.55], [-0.75, 0]]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.15, 14), K.mat(0x1a1a1a)); w.rotation.x = Math.PI / 2; w.position.set(x, 0.3, z); rk.add(w); }
      rk.position.set(-10.5, 0, 3); rk.rotation.y = 0.5; rk.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(rk);
    }
  } },
  city_street: { ground: 0x9a9a98, build(K) {
    const night = isNight(K);
    plane(K, 14, 120, 0x3c3f45, 0, 0.012, -30, 0.9);
    for (let k = 0; k < 14; k++) plane(K, 0.25, 1.6, 0xf4f4f4, 0, 0.02, -2 - k * 4);
    for (const s of [-1, 1]) {
      box(K, 3, 0.25, 120, 0xb9b4aa, s * 8.5, 0.12, -30);
      for (let k = 0; k < 7; k++) building(K, s * 14, -4 - k * 8, 7, 8 + K.R() * 14, 6, [0xd9c7b0, 0xb9c4d0, 0xe6d3c3, 0xa9b6a0, 0xd8b4a0][k % 5], night, s < 0 ? Math.PI / 2 : -Math.PI / 2);
      for (let k = 0; k < 4; k++) { cyl(K, 0.08, 0.1, 5, 0x3a3f48, s * 7.4, 2.5, -2 - k * 10, 8); const head = new THREE.Mesh(new THREE.SphereGeometry(0.25, 10, 8), glow(night ? 0xfff0c0 : 0xdddddd)); head.position.set(s * 6.9, 5, -2 - k * 10); K.scene.add(head); if (night && k < 2) { const l = new THREE.PointLight(0xffe2a8, 3, 12); l.position.set(s * 6.9, 4.6, -2 - k * 10); K.scene.add(l); } }
    }
    prop(K, "car", -3, -14, 0, 1.4); prop(K, "car", 3.5, -24, Math.PI, 1.4);
    cyl(K, 0.08, 0.08, 4, 0x2a2a2a, 7.2, 2, 2, 8); box(K, 0.4, 1.1, 0.35, 0x2a2a2a, 7.2, 4.3, 2);
    [0xd8343c, 0xf2c12e, 0x3f9a3a].forEach((c, i) => { const b = new THREE.Mesh(new THREE.CircleGeometry(0.11, 12), glow(i === 2 ? c : 0x333333)); b.position.set(7.2, 4.65 - i * 0.33, 2.18); K.scene.add(b); });
    for (const x of [-9.5, 9.5]) for (let k = 0; k < 3; k++) K.tree(x, -6 - k * 12, 0.8, [0x4f9a3a, 0x3f8a34]);
  } },
  highway: { ground: 0xa8a06a, build(K) {
    plane(K, 8, 160, 0x404349, 0, 0.012, -60, 0.9); for (let k = 0; k < 20; k++) plane(K, 0.25, 2, 0xf2c12e, 0, 0.02, -4 - k * 6);
    const hut = new THREE.Group(); const hb = new THREE.Mesh(new THREE.BoxGeometry(6, 2.6, 3.5), K.mat(0xe8c99a, 0.9)); hb.position.y = 1.3; hut.add(hb);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(4.6, 1.6, 4), K.mat(0xc9a24a, 1)); roof.position.y = 3.3; roof.rotation.y = Math.PI / 4; roof.scale.set(1.15, 1, 0.75); hut.add(roof);
    const sign = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.7, 0.08), K.mat(0xd8343c, 0.6)); sign.position.set(0, 2.9, 1.8); hut.add(sign);
    hut.position.set(-11, 0, -8); hut.rotation.y = 0.4; hut.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; } }); K.scene.add(hut);
    for (const [x, z] of [[-8.5, -3.5], [-11.5, -2.5]]) { box(K, 1.9, 0.12, 0.9, 0xd9b98a, x, 0.55, z); for (const [dx, dz] of [[-0.85, -0.4], [0.85, -0.4], [-0.85, 0.4], [0.85, 0.4]]) cyl(K, 0.05, 0.05, 0.55, 0x6e4224, x + dx, 0.27, z + dz, 6); }
    const truck = new THREE.Group(); const cab = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2.2), K.mat(0xd8343c, 0.5)); cab.position.set(2.6, 1.4, 0); truck.add(cab);
    const load = new THREE.Mesh(new THREE.BoxGeometry(4.6, 2.6, 2.3), K.mat(0xf2c12e, 0.6)); load.position.set(-0.8, 1.7, 0); truck.add(load);
    for (const x of [2.4, -0.4, -2.4]) for (const z of [1.1, -1.1]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.3, 14), K.mat(0x1a1a1a)); w.rotation.x = Math.PI / 2; w.position.set(x, 0.45, z); truck.add(w); }
    truck.position.set(10, 0, -9); truck.rotation.y = -0.3; truck.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(truck);
    const ms = cyl(K, 0.35, 0.35, 0.9, 0xffffff, 5.5, 0.45, 2.5, 14); const mt = new THREE.Mesh(new THREE.SphereGeometry(0.35, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), K.mat(0xf2c12e, 0.6)); mt.position.set(5.5, 0.9, 2.5); K.scene.add(mt);
    for (let k = 0; k < 8; k++) { cyl(K, 0.08, 0.1, 7, 0x6e4224, 16, 3.5, -4 - k * 12, 6); box(K, 1.6, 0.08, 0.08, 0x6e4224, 16, 6.6, -4 - k * 12); }
    K.hills(0xb5ad78); K.tufts(80, 0x8a9a4a);
  } },
  station: { ground: 0x8d8a84, build(K) {
    plane(K, 60, 8, 0xb9b4aa, 0, 0.012, 1); plane(K, 60, 0.35, 0xf2c12e, 0, 0.02, -2.6); box(K, 60, 0.9, 0.3, 0x8d8a84, 0, -0.44, -2.95);
    plane(K, 60, 6, 0x6e6a64, 0, -0.85, -6);
    for (const z of [-4.2, -5.6]) box(K, 60, 0.12, 0.12, 0x6b6f78, 0, -0.75, z, 0.4);
    for (let k = -28; k <= 28; k += 1.2) box(K, 0.3, 0.08, 2.4, 0x5a4030, k, -0.81, -4.9);
    const train = new THREE.Group();
    for (let c = 0; c < 4; c++) { const coach = new THREE.Mesh(new THREE.BoxGeometry(11, 3.2, 3), K.mat(c === 0 ? 0xd8343c : 0x2f5fa0, 0.6)); coach.position.set(-16 + c * 11.4, 2.1, 0); train.add(coach);
      const stripe = new THREE.Mesh(new THREE.BoxGeometry(11.02, 0.3, 3.02), K.mat(0xf2c12e, 0.6)); stripe.position.set(-16 + c * 11.4, 1.3, 0); train.add(stripe);
      for (let w = 0; w < 6; w++) { const win = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.8), isNight(K) ? glow(0xffe49a) : K.mat(0x9fc3dd, 0.2)); win.position.set(-20.5 + c * 11.4 + w * 1.8, 2.6, 1.51); train.add(win); } }
    train.position.set(0, -0.85, -4.9); train.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(train);
    for (let k = -3; k <= 3; k++) { if (Math.abs(k) < 1) continue; cyl(K, 0.12, 0.12, 4.2, 0x3a4a5a, k * 4, 3, 3.5, 8); }
    box(K, 30, 0.2, 5, 0x5a6a7a, 0, 5.1, 2.6);
    const board = box(K, 4.2, 1, 0.12, 0xf2c12e, 0, 4.4, 3.8); const bl = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 0.5), glow(0x1a1a1a)); bl.position.set(0, 4.4, 3.87); K.scene.add(bl);
    const clock = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.1, 24), K.mat(0xffffff, 0.5)); clock.rotation.x = Math.PI / 2; clock.position.set(7, 4.3, 3.8); K.scene.add(clock);
    for (const x of [-9, 9]) { box(K, 2.2, 0.12, 0.6, 0x8a5a2b, x, 1.45, 3.4); box(K, 2.2, 0.6, 0.1, 0x8a5a2b, x, 1.8, 3.7); }
    K.hills(0x9bae7a);
  } },
  school: { indoor: true, build(K) {
    walls(K, 0xf3e7c9, 0xb08a5a, { winX: 6 });
    box(K, 7, 2.6, 0.1, 0x2f4a3a, -1, 3.2, -4.92, 0.7); box(K, 7.3, 0.12, 0.25, 0x8a5a2b, -1, 1.85, -4.85);
    for (let k = 0; k < 4; k++) { const ln = new THREE.Mesh(new THREE.PlaneGeometry(2.6 + K.R() * 2.5, 0.06), glow(0xeef2ee)); ln.position.set(-2.4 + K.R() * 1.2, 4 - k * 0.5, -4.86); K.scene.add(ln); }
    box(K, 2.2, 0.9, 1, 0x8a5a2b, 5.5, 0.45, -3);
    for (const s of [-1, 1]) for (let r = 0; r < 2; r++) { const x = s * (8.4 + r * 0), z = -1 + r * 2.8; box(K, 1.8, 0.08, 0.9, 0xb07a4a, x, 1.0, z); for (const dx of [-0.8, 0.8]) cyl(K, 0.04, 0.04, 1, 0x3a3a3a, x + dx, 0.5, z, 6); box(K, 1.8, 0.08, 0.45, 0xb07a4a, x, 0.6, z + 0.8); }
    for (let k = 0; k < 3; k++) { const p = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.4), K.mat([0xffd23f, 0x7ad0ff, 0xff6fa5][k], 0.6)); p.position.set(10.95, 3.5, -1 + k * 1.6); p.rotation.y = -Math.PI / 2; K.scene.add(p); }
    const globe = new THREE.Mesh(new THREE.SphereGeometry(0.35, 20, 14), K.mat(0x2f7fe0, 0.5)); globe.position.set(5.2, 1.35, -3); K.scene.add(globe);
  } },
  hospital: { indoor: true, build(K) {
    walls(K, 0xe3f1ef, 0xd9e2e2, { trim: 0x7aaba5, winX: 0 });
    for (const s of [-1, 1]) for (let r = 0; r < 2; r++) {
      const x = s * 7.6, z = -3 + r * 3.6;
      box(K, 2, 0.5, 3.6, 0xffffff, x, 0.8, z, 0.7); box(K, 2.05, 0.25, 3.65, 0x9fd3d0, x, 1.1, z + 0.4, 0.8); box(K, 0.8, 0.2, 0.6, 0xffffff, x, 1.2, z - 1.4);
      for (const dx of [-0.95, 0.95]) cyl(K, 0.04, 0.04, 1.2, 0xc7cdd6, x + dx, 0.6, z - 1.75, 6);
      cyl(K, 0.03, 0.03, 2.2, 0xc7cdd6, x - s * 1.3, 1.1, z - 1.3, 6); box(K, 0.25, 0.35, 0.1, 0xcfe8ff, x - s * 1.3, 2.1, z - 1.3, 0.2);
    }
    const crossM = glow(0xd8343c); for (const [w, h] of [[0.9, 0.3], [0.3, 0.9]]) { const c = new THREE.Mesh(new THREE.PlaneGeometry(w, h), crossM); c.position.set(4, 4.4, -4.97); K.scene.add(c); }
    box(K, 1.6, 1.8, 0.6, 0xffffff, -2.5, 0.9, -4.6, 0.5); box(K, 1.2, 0.8, 0.1, 0x1a2a3a, 1.6, 2.6, -4.93, 0.3);
    const line = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.05), glow(0x7affc8)); line.position.set(1.6, 2.6, -4.87); K.scene.add(line);
    const cur = new THREE.Mesh(new THREE.PlaneGeometry(3, 3.6), K.mat(0x9fd3d0, 0.8, { side: THREE.DoubleSide })); cur.position.set(-6, 1.8, -2); cur.rotation.y = Math.PI / 2; K.scene.add(cur);
  } },
  kitchen: { indoor: true, build(K) {
    walls(K, 0xfff1c9, 0xc98a5a, { winX: 2 });
    box(K, 16, 1.0, 1.1, 0xd9c2a0, -1, 0.5, -4.3); box(K, 16, 0.08, 1.2, 0x8a7a6a, -1, 1.04, -4.3, 0.4);
    for (let k = 0; k < 6; k++) box(K, 1.6, 1.0, 0.6, 0xc9a77a, -8 + k * 2.6, 3.4, -4.6);
    box(K, 1.4, 0.15, 0.8, 0x3a3a3a, -4, 1.12, -4.3); for (const dx of [-0.35, 0.35]) { const b = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.03, 6, 16), K.mat(0x1a1a1a)); b.rotation.x = Math.PI / 2; b.position.set(-4 + dx, 1.22, -4.3); K.scene.add(b); }
    const pot = cyl(K, 0.28, 0.24, 0.35, 0xc7cdd6, -3.65, 1.42, -4.3, 16, 0.3);
    box(K, 1.6, 3.6, 1.2, 0xe8eef4, 8.4, 1.8, -4.2, 0.4);
    for (let k = 0; k < 5; k++) { const j = cyl(K, 0.12, 0.12, 0.3, [0xff8a1f, 0xd8343c, 0xf2c12e, 0x3f9a3a, 0x8a5a2b][k], 1 + k * 0.4, 1.23, -4.4, 10); }
    prop(K, "apple", 3, -4.2, 0, 0.6);
  } },
  bedroom: { indoor: true, build(K) {
    walls(K, 0xd9e7f5, 0xb07a4a, { winX: 5 });
    box(K, 3.4, 0.6, 4.6, 0x8a5a2b, -7.5, 0.3, -2.4); box(K, 3.3, 0.35, 4.3, 0xffffff, -7.5, 0.75, -2.3); box(K, 3.35, 0.2, 3, [0x7ad0ff, 0xff6fa5, 0xf2c12e][Math.floor(K.R() * 3)], -7.5, 0.95, -1.6, 0.8);
    box(K, 3.4, 1.6, 0.25, 0x8a5a2b, -7.5, 1.1, -4.7); box(K, 1.4, 0.3, 0.7, 0xffffff, -7.5, 1.0, -4);
    box(K, 2.4, 4, 1, 0xc9a77a, 8.5, 2, -4.2); box(K, 0.06, 3.6, 0.02, 0x8a5a2b, 8.5, 2.1, -3.68);
    box(K, 1, 0.8, 0.8, 0xc9a77a, -4.8, 0.4, -4.3); cyl(K, 0.05, 0.08, 0.6, 0x3a3a3a, -4.8, 1.1, -4.3, 8);
    const shade = new THREE.Mesh(new THREE.ConeGeometry(0.35, 0.4, 16, 1, true), glow(0xffe49a)); shade.position.set(-4.8, 1.55, -4.3); K.scene.add(shade);
    const rug = new THREE.Mesh(new THREE.CircleGeometry(2.6, 32), K.mat(0x8e5bd8, 0.9)); rug.rotation.x = -Math.PI / 2; rug.position.set(0, 0.01, 0.5); K.scene.add(rug);
  } },
  mountain: { ground: 0x8a9a6a, build(K) {
    if (K.scene.fog) { K.scene.fog.near = Math.max(K.scene.fog.near, 45); K.scene.fog.far = Math.max(K.scene.fog.far, 170); }
    mountains(K, true); mountains(K, true);
    for (let k = 0; k < 10; k++) { const r = new THREE.Mesh(new THREE.DodecahedronGeometry(1 + K.R() * 2.5), K.mat(0x8a8478, 0.95)); r.position.set((K.R() < 0.5 ? -1 : 1) * (9 + K.R() * 14), 0.5, -6 - K.R() * 20); r.castShadow = true; K.scene.add(r); }
    for (let i = 0; i < 16; i++) { const x = (K.R() < 0.5 ? -1 : 1) * (8 + K.R() * 18), z = -6 - K.R() * 22; K.tree(x, z, 0.8 + K.R() * 0.6, [0x2f5a3a, 0x3a6a44, 0x24452f], true); }
    plane(K, 3, 50, 0xb5a27a, 0, 0.012, -25);
    K.rocks(10); K.tufts(90, 0x6a8a44);
  } },
  desert: { ground: 0xe6c88a, build(K) {
    for (let k = 0; k < 9; k++) { const d = new THREE.Mesh(new THREE.SphereGeometry(8 + K.R() * 8, 20, 12), K.mat(k % 2 ? 0xe0b878 : 0xebc78e, 1)); d.scale.set(1.6, 0.28, 1); d.position.set(-50 + k * 13, -1, -30 - K.R() * 20); K.scene.add(d); }
    for (const [x, z, r] of [[-13, -10, 6], [12, -12, 7], [-3, -18, 8], [20, -6, 5]]) { const d = new THREE.Mesh(new THREE.SphereGeometry(r, 24, 14), K.mat(0xe8c084, 1)); d.scale.set(1.8, 0.32, 1.1); d.position.set(x, -0.6, z); d.receiveShadow = true; K.scene.add(d); }
    for (let k = 0; k < 6; k++) {   // cacti
      const x = (k % 2 ? -1 : 1) * (8 + K.R() * 10), z = -4 - K.R() * 14, g = new THREE.Group(), m = K.mat(0x5a8f3a, 0.8);
      const t = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 2.2, 6, 10), m); t.position.y = 1.4; g.add(t);
      for (const s of [-1, 1]) { const a = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.8, 6, 8), m); a.position.set(s * 0.5, 1.6 + K.R() * 0.6, 0); g.add(a); const b = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.4, 6, 8), m); b.position.set(s * 0.3, 1.5, 0); b.rotation.z = s * Math.PI / 2; g.add(b); }
      g.position.set(x, 0, z); g.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(g);
    }
    K.rocks(8);
    for (let k = 0; k < 40; k++) { const s = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.04), K.mat(0xd9b070, 1)); s.rotation.x = -Math.PI / 2; s.position.set((K.R() - 0.5) * 30, 0.02, (K.R() - 0.5) * 12 - 2); K.scene.add(s); }
  } },
  river: { ground: 0x7aaa4a, build(K) {
    water(K, 120, 9, 0, -10);
    for (let k = 0; k < 7; k++) { const s = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.6, 0.3, 10), K.mat(0x9a9488, 0.9)); s.position.set(-6 + k * 2 + (K.R() - 0.5), 0.12, -10 + (K.R() - 0.5) * 2); K.scene.add(s); }
    reeds(K, 60, -20, 20, -6.2, -5.4); reeds(K, 40, -20, 20, -14.8, -14);
    const bridge = new THREE.Group(); const deck = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.2, 10), K.mat(0x8a5a2b, 0.8)); deck.position.y = 1; bridge.add(deck);
    for (const s of [-1, 1]) { const rail = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.1, 10), K.mat(0x6e4224)); rail.position.set(s * 1.1, 1.8, 0); bridge.add(rail); for (let k = -4; k <= 4; k += 2) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.8, 0.1), K.mat(0x6e4224)); p.position.set(s * 1.1, 1.4, k); bridge.add(p); } }
    bridge.position.set(-12, 0, -10); bridge.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(bridge);
    const boat = box(K, 3.4, 0.5, 1.2, 0x8a5a2b, 9, 0.2, -11); boat.rotation.y = 0.3;
    K.forest([0x4f9a3a, 0x6cb648, 0x3f8a34], 35); K.hills(0x9bbf63); K.flowers(25); K.tufts(100);
  } },
  cave: { indoor: true, build(K) {
    const shell = new THREE.Mesh(new THREE.SphereGeometry(22, 32, 20, 0, Math.PI * 2, 0, Math.PI / 2), K.mat(0x4a4038, 1, { side: THREE.BackSide })); shell.scale.set(1.3, 0.55, 1); shell.position.set(0, -0.2, -6); K.scene.add(shell);
    plane(K, 50, 50, 0x5a5048, 0, 0, -6, 1);
    for (let k = 0; k < 26; k++) { const st = new THREE.Mesh(new THREE.ConeGeometry(0.25 + K.R() * 0.5, 1 + K.R() * 2.5, 6), K.mat(0x6a5e52, 0.95)); st.rotation.x = Math.PI; st.position.set((K.R() - 0.5) * 34, 10.5 - K.R() * 2, -4 - K.R() * 20); K.scene.add(st); }
    for (let k = 0; k < 10; k++) { const sm = new THREE.Mesh(new THREE.ConeGeometry(0.3 + K.R() * 0.4, 0.8 + K.R() * 2, 6), K.mat(0x6a5e52, 0.95)); sm.position.set((K.R() < 0.5 ? -1 : 1) * (8 + K.R() * 8), 0.5, -4 - K.R() * 14); K.scene.add(sm); }
    for (let k = 0; k < 8; k++) { const c = new THREE.Mesh(new THREE.OctahedronGeometry(0.25 + K.R() * 0.35), glow([0x7ad0ff, 0xb57bff, 0x7affc8][k % 3])); c.position.set((K.R() < 0.5 ? -1 : 1) * (7.5 + K.R() * 6), 0.4, -3 - K.R() * 10); c.rotation.set(K.R(), K.R(), 0); K.scene.add(c); }
    const cl = new THREE.PointLight(0x9fd8ff, 2.5, 14); cl.position.set(-9, 1.2, -6); K.scene.add(cl);
    cyl(K, 0.05, 0.07, 1.2, 0x5a3a22, 8, 1.6, -4.6, 6); flame(K, 8, 2.2, -4.6, 3, true);
    K.rocks(12);
  } },
};
KITS.ruins_temple = KITS.ruins;
export const INDOOR_KITS = new Set(Object.entries(KITS).filter(([, k]) => k.indoor).map(([n]) => n));

// ---------------------------------------------------------------- sky: clouds, sun or moon, stars
export function buildSky(K, T) {
  const w = K.w, weather = w.weather || "clear", time = w.time || "";
  const night = ["night", "midnight"].includes(time) || ["night", "dark"].includes(w.mood);
  const grey = ["overcast", "rain", "storm", "snow"].includes(weather);
  const n = grey ? 22 : weather === "fog" ? 8 : night ? 4 : 9;
  const cm = K.mat(grey ? (weather === "storm" ? 0x5a6270 : 0xa9b2bd) : (night ? 0x3a4270 : 0xffffff), 1, { transparent: true, opacity: night ? 0.55 : 0.92 });
  for (let i = 0; i < n; i++) {
    const g = new THREE.Group(), x = (K.R() - 0.5) * 150, y = 22 + K.R() * 14, z = -60 - K.R() * 30;
    for (let k = 0; k < 5; k++) { const s = new THREE.Mesh(new THREE.SphereGeometry(3 + K.R() * 3, 12, 8), cm); s.position.set((k - 2) * 3.2 + K.R(), K.R() * 1.5, K.R() * 2); s.scale.y = 0.55; g.add(s); }
    g.position.set(x, y, z); K.scene.add(g);
  }
  if (!grey && weather !== "fog") {
    if (night) {
      const moon = new THREE.Mesh(new THREE.SphereGeometry(3, 24, 16), glow(0xfff6d5)); moon.position.set(28, 34, -90); K.scene.add(moon);
      for (let i = 0; i < 160; i++) { const s = new THREE.Mesh(new THREE.SphereGeometry(0.12 + K.R() * 0.15, 6, 4), glow(0xffffff)); s.position.set((K.R() - 0.5) * 220, 14 + K.R() * 60, -95 - K.R() * 10); K.scene.add(s); }
    } else if (["dawn", "golden", "dusk"].includes(time) || w.mood === "sunset") {
      const p = new THREE.Vector3(...T.sunPos).normalize();
      const sun = new THREE.Mesh(new THREE.SphereGeometry(5, 24, 16), glow(time === "dawn" ? 0xffc79a : 0xffb05a)); sun.position.set(p.x * 90, Math.max(5, p.y * 90 * 0.35), -85); K.scene.add(sun);
      const halo = new THREE.Mesh(new THREE.SphereGeometry(9, 24, 16), new THREE.MeshBasicMaterial({ color: 0xffd9a0, transparent: true, opacity: 0.25, depthWrite: false })); halo.position.copy(sun.position); K.scene.add(halo);
    }
  }
}

// ---------------------------------------------------------------- light by time of day and weather
export const TIMES = {
  dawn:     { sky: ["#3b4a8a", "#f2a07b", "#ffd9a8"], fog: 0xf3c4a0, hemi: [0xffd6c0, 0x5a4a4e, 0.95], sun: [0xffb27a, 2.2], sunPos: [-14, 4, 6], exp: 1.08 },
  morning:  { sky: ["#5aa8f0", "#a9d6ff", "#fff0d0"], fog: 0xe6eef0, hemi: [0xe8f4ff, 0x6b5a2e, 1.15], sun: [0xfff0d8, 2.8], sunPos: [-9, 11, 8], exp: 1.05 },
  noon:     { sky: ["#3d8fe8", "#8cc8ff", "#e8f4ff"], fog: 0xdbe8ef, hemi: [0xf0f8ff, 0x6b6a3e, 1.2], sun: [0xffffff, 3.0], sunPos: [-3, 16, 6], exp: 1.0 },
  golden:   { sky: ["#4a6fc0", "#f6b86a", "#ffe2a8"], fog: 0xf2c890, hemi: [0xffe0b8, 0x5a4a2e, 1.05], sun: [0xffb860, 2.8], sunPos: [-12, 6, 7], exp: 1.05 },
  dusk:     { sky: ["#2f3a7a", "#e07a5d", "#ffc39a"], fog: 0xd89a80, hemi: [0xffc8b0, 0x4a3a3e, 0.95], sun: [0xff9a60, 2.2], sunPos: [-13, 3.5, 6], exp: 1.12 },
  night:    { sky: ["#0b1233", "#22306a", "#46508a"], fog: 0x1f2a55, hemi: [0x8fa4ff, 0x1c2238, 1.1], sun: [0xb8c8ff, 2.0], sunPos: [6, 12, 7], exp: 1.45 },
  midnight: { sky: ["#05081c", "#121a40", "#2a3260"], fog: 0x121a3a, hemi: [0x7a8ae8, 0x10141f, 0.95], sun: [0xa8b8f0, 1.6], sunPos: [6, 12, 7], exp: 1.55 },
};
const mixHex = (a, b, t) => { const A = new THREE.Color(a), B = new THREE.Color(b); return "#" + A.lerp(B, t).getHexString(); };
export function weatherize(base, weather) {
  const T = { ...base, sky: [...base.sky], hemi: [...base.hemi], sun: [...base.sun], fogNear: null, fogFar: null };
  if (["overcast", "rain", "storm", "snow"].includes(weather)) {
    const g = weather === "storm" ? "#4a5260" : weather === "snow" ? "#c8d2dc" : "#8a95a5", k = weather === "overcast" ? 0.55 : 0.75;
    T.sky = T.sky.map(c => mixHex(c, g, k)); T.fog = new THREE.Color(mixHex("#" + new THREE.Color(T.fog).getHexString(), g, k)).getHex();
    T.sun = [T.sun[0], T.sun[1] * (weather === "storm" ? 0.3 : 0.45)];
    T.hemi = [T.hemi[0], T.hemi[1], T.hemi[2] * (weather === "storm" ? 0.42 : weather === "rain" ? 0.7 : 1.0)];
    T.exp = (T.exp || 1) * (weather === "storm" ? 0.68 : weather === "rain" ? 0.85 : 1);
    T.fogNear = 16; T.fogFar = weather === "storm" ? 48 : 60;
  }
  if (weather === "fog") { T.fog = new THREE.Color(T.sky[1]).lerp(new THREE.Color(0xffffff), 0.35).getHex(); T.fogNear = 4; T.fogFar = 30; T.sun = [T.sun[0], T.sun[1] * 0.6]; }
  return T;
}


// ====================================================================== beauty: glow, depth, horizon (Plan 12 P3)
let _haloTex = null;
function haloTex() {   // a soft round glow, drawn once
  if (_haloTex) return _haloTex;
  const cv = document.createElement("canvas"); cv.width = cv.height = 64;
  const g = cv.getContext("2d"), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.25, "rgba(255,255,255,0.55)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  _haloTex = new THREE.CanvasTexture(cv); return _haloTex;
}
export function halo(K, x, y, z, size = 0.8, color = 0xffc46a, strength = 0.85) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex(), color, transparent: true, opacity: strength, depthWrite: false, blending: THREE.AdditiveBlending }));
  s.position.set(x, y, z); s.scale.setScalar(size); K.scene.add(s); return s;
}
function bush(K, x, z, s = 1, c = 0x4f8f34) {
  const g = new THREE.Group();
  for (let k = 0; k < 4; k++) { const b = new THREE.Mesh(new THREE.SphereGeometry((0.5 + K.R() * 0.3) * s, 12, 8), K.mat(k % 2 ? c : 0x5f9f40, 0.85)); b.position.set((K.R() - 0.5) * 0.8 * s, 0.35 * s, (K.R() - 0.5) * 0.6 * s); b.castShadow = true; g.add(b); }
  g.position.set(x, 0, z); K.scene.add(g); return g;
}
function palm(K, x, z, s = 1) {
  const g = new THREE.Group();
  for (let k = 0; k < 6; k++) { const seg = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.2 * s, 0.6 * s, 10), K.mat(0x9a6a3a, 0.9)); seg.position.set(k * 0.07 * s, (0.3 + k * 0.55) * s, 0); g.add(seg); }
  for (let k = 0; k < 7; k++) { const lf = new THREE.Mesh(new THREE.SphereGeometry(0.9 * s, 10, 6), K.mat(0x3f9a3a, 0.7)); lf.scale.set(1.3, 0.12, 0.38); const a = (k / 7) * Math.PI * 2; lf.rotation.y = a; lf.position.set(0.4 * s + Math.cos(a) * 0.8 * s, 3.35 * s, Math.sin(a) * 0.8 * s); g.add(lf); }
  g.position.set(x, 0, z); g.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(g); return g;
}
function skyline(K, color = 0x6a7488) {   // a far city silhouette, softened by the haze
  for (let k = 0; k < 26; k++) { const w = 4 + K.R() * 6, h = 8 + K.R() * 26; const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, 3), K.mat(color, 1)); b.position.set(-90 + k * 7 + K.R() * 3, h / 2 - 1, -75 - K.R() * 15); K.scene.add(b); }
}
function farHills(K, color = 0x8fae6a) {
  for (let i = 0; i < 9; i++) { const h = new THREE.Mesh(new THREE.SphereGeometry(14 + K.R() * 10, 16, 10), K.mat(color, 1)); h.scale.y = 0.45; h.position.set(-80 + i * 20, -3, -70 - K.R() * 15); K.scene.add(h); }
}
function groundPatches(K, n, colors) {   // the ground is never one flat colour
  for (let i = 0; i < n; i++) { const p = new THREE.Mesh(new THREE.CircleGeometry(1.5 + K.R() * 4, 20), K.mat(colors[i % colors.length], 1)); p.rotation.x = -Math.PI / 2; p.position.set((K.R() - 0.5) * 50, 0.006 + i * 0.0003, -2 - K.R() * 30); p.receiveShadow = true; K.scene.add(p); }
}
function lantern(K, x, y, z, c = 0xd8343c) {   // a paper lantern (Japanese streets, festivals)
  const l = new THREE.Mesh(new THREE.SphereGeometry(0.28, 14, 10), new THREE.MeshBasicMaterial({ color: c })); l.scale.y = 1.25; l.position.set(x, y, z); K.scene.add(l); halo(K, x, y, z, 1.4, c, 0.6);
}
function torch(K, x, z, h = 2.2) { cyl(K, 0.05, 0.07, h, 0x5a3a22, x, h / 2, z, 6); flame(K, x, h, z, 2.4, false); halo(K, x, h + 0.2, z, 1.6, 0xffa64a, 0.9); }
function bench(K, x, z, rot = 0, c = 0x8a5a2b) {
  const g = new THREE.Group(); const seat = new THREE.Mesh(new THREE.BoxGeometry(2, 0.1, 0.6), K.mat(c, 0.8)); seat.position.y = 0.55; g.add(seat);
  const back = new THREE.Mesh(new THREE.BoxGeometry(2, 0.6, 0.08), K.mat(c, 0.8)); back.position.set(0, 0.9, -0.28); g.add(back);
  for (const dx of [-0.9, 0.9]) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.55, 0.55), K.mat(0x3a3a3a)); l.position.set(dx, 0.27, 0); g.add(l); }
  g.position.set(x, 0, z); g.rotation.y = rot; g.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(g); return g;
}
function deadTree(K, x, z, s = 1) {
  const g = new THREE.Group(), m = K.mat(0x3a2e26, 0.95);
  const t = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * s, 0.25 * s, 3 * s, 7), m); t.position.y = 1.5 * s; g.add(t);
  for (let k = 0; k < 4; k++) { const b = new THREE.Mesh(new THREE.CylinderGeometry(0.04 * s, 0.09 * s, 1.4 * s, 5), m); b.position.set(0, (2 + k * 0.35) * s, 0); b.rotation.set(0, k * 1.6, 0.9 * (k % 2 ? 1 : -1)); b.translateY(0.6 * s); g.add(b); }
  g.position.set(x, 0, z); g.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(g); return g;
}
function gravestone(K, x, z, rot = 0) {
  const g = new THREE.Group(); const s = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.9, 0.18), K.mat(0x8a8a8f, 0.95)); s.position.y = 0.45; g.add(s);
  const top = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.18, 14, 1, false, 0, Math.PI), K.mat(0x8a8a8f, 0.95)); top.rotation.set(Math.PI / 2, 0, Math.PI / 2); top.position.y = 0.9; g.add(top);
  g.position.set(x, 0, z); g.rotation.set(0, rot, (K.R() - 0.5) * 0.15); g.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(g);
}
function seats(K, rows, cols, x0, z0, dx, dz, c) { for (let r = 0; r < rows; r++) for (let k = 0; k < cols; k++) { box(K, dx * 0.8, 0.5, 0.6, c, x0 + k * dx, 0.25, z0 + r * dz); box(K, dx * 0.8, 0.7, 0.12, c, x0 + k * dx, 0.75, z0 + r * dz - 0.28); } }

// ====================================================================== more places (Plan 12 P5)
Object.assign(KITS, {
  train_interior: { indoor: true, build(K) {
    const night = isNight(K);
    plane(K, 14, 40, 0x5a5048, 0, 0, -6, 0.8);
    for (const s of [-1, 1]) {
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(40, 4), K.mat(0x2f5f8a, 0.8, { side: THREE.DoubleSide })); wall.position.set(s * 5.5, 2, -6); wall.rotation.y = Math.PI / 2; K.scene.add(wall);
      for (let k = 0; k < 7; k++) { const win = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.0), glow(night ? 0x14204a : 0x9fd3ff)); win.position.set(s * 5.48, 2.2, -1 - k * 3); win.rotation.y = -s * Math.PI / 2; K.scene.add(win); }
      for (let k = 0; k < 6; k++) { const z = -2 - k * 3; box(K, 2.2, 0.45, 1.1, 0x8a3a2a, s * 4.2, 0.6, z); box(K, 2.2, 1.1, 0.25, 0x8a3a2a, s * 4.2, 1.2, z - 0.55); box(K, 2.4, 0.08, 0.9, 0x9aa4b4, s * 4.4, 3.2, z, 0.4); }
    }
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(11, 40), K.mat(0xe8e2d4, 0.9, { side: THREE.DoubleSide })); ceil.rotation.x = Math.PI / 2; ceil.position.set(0, 4, -6); K.scene.add(ceil);
    for (let k = 0; k < 5; k++) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.06, 1.6), glow(0xfff6d8)); l.position.set(0, 3.96, -1 - k * 4); K.scene.add(l); }
    const back = new THREE.Mesh(new THREE.PlaneGeometry(11, 4), K.mat(0x2f5f8a, 0.8)); back.position.set(0, 2, -24); K.scene.add(back); box(K, 1.2, 2.6, 0.1, 0x9aa4b4, 0, 1.3, -23.9, 0.4);
    const lamp = new THREE.PointLight(0xfff0d0, 1.6, 18); lamp.position.set(0, 3.6, 0); K.scene.add(lamp);
  } },
  office: { indoor: true, build(K) {
    walls(K, 0xe8ecef, 0x9aa4b4, { window: false, trim: 0x6a7480 });
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(18, 5), glow(isNight(K) ? 0x1a2a50 : 0xbfe0f5)); glass.position.set(0, 3.2, -4.96); K.scene.add(glass);
    for (let k = 0; k < 9; k++) { const b = new THREE.Mesh(new THREE.PlaneGeometry(1.2 + K.R(), 1 + K.R() * 2.6), glow(isNight(K) ? 0x2a3a6a : 0x8fb0c8)); b.position.set(-8 + k * 2, 1.4 + K.R(), -4.94); K.scene.add(b); }
    for (const s of [-1, 1]) for (let r = 0; r < 2; r++) { const x = s * 7.3, z = -3.2 - r * 0.2 + r * 3.2; box(K, 2.2, 0.08, 1.1, 0xd9c2a0, x, 1.0, z); for (const dx of [-1, 1]) box(K, 0.06, 1, 1, 0x6a7480, x + dx, 0.5, z); box(K, 0.9, 0.6, 0.06, 0x1a1a1a, x, 1.45, z - 0.3); const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.5), glow(0x7ad0ff)); scr.position.set(x, 1.45, z - 0.26); K.scene.add(scr); }
    for (const x of [-10, 10]) { cyl(K, 0.4, 0.3, 0.7, 0xf4f4f4, x, 0.35, -4.2, 12); bush(K, x, -4.2, 0.9); }
    cyl(K, 0.3, 0.3, 1.3, 0x9fd3ff, 5, 0.65, -4.5, 14);
  } },
  cafe: { indoor: true, build(K) {
    walls(K, 0xf0dcc0, 0x8a5a3a, { winX: -6, trim: 0x5a3a22 });
    box(K, 8, 1.1, 1, 0x6e4224, 3, 0.55, -4.3); box(K, 8.2, 0.1, 1.1, 0x3a2614, 3, 1.12, -4.3);
    box(K, 0.8, 0.9, 0.6, 0xc7cdd6, 5.5, 1.6, -4.4, 0.3);
    const menu = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 1.6), K.mat(0x1a2a1e, 0.8)); menu.position.set(3, 3.4, -4.95); K.scene.add(menu);
    for (let k = 0; k < 5; k++) { const ln = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 0.06), glow(0xf4f4f4)); ln.position.set(3, 3.9 - k * 0.25, -4.94); K.scene.add(ln); }
    for (const [x, z] of [[-8.5, -1.5], [8.5, -1], [-8.5, 2.5], [8.5, 3]]) { cyl(K, 0.6, 0.6, 0.06, 0xf4f4f4, x, 1.0, z, 20); cyl(K, 0.05, 0.05, 1, 0x3a3a3a, x, 0.5, z, 8); for (const dx of [-0.9, 0.9]) cyl(K, 0.28, 0.28, 0.06, 0x8a5a2b, x + dx, 0.6, z, 14); cyl(K, 0.1, 0.08, 0.15, 0xffffff, x, 1.1, z, 10); }
    for (const x of [-3, 0, 3]) { cyl(K, 0.01, 0.01, 1.2, 0x2a2a2a, x, 5.4, -1, 4); const sh = new THREE.Mesh(new THREE.ConeGeometry(0.35, 0.35, 16, 1, true), K.mat(0xd9822b, 0.6, { side: THREE.DoubleSide })); sh.position.set(x, 4.7, -1); K.scene.add(sh); halo(K, x, 4.5, -1, 1.2, 0xffd08a, 0.7); }
  } },
  library: { indoor: true, build(K) {
    walls(K, 0xe8d9b8, 0x7a4a2a, { window: false, trim: 0x4a2e1a });
    const bookC = [0xd8343c, 0x2f7fe0, 0x3f9a3a, 0xf2c12e, 0x8e5bd8, 0x6e4224, 0x1fa2a0];
    for (let sx = -2; sx <= 2; sx++) { const x = sx * 3.6; box(K, 3.2, 4.2, 0.6, 0x6e4224, x, 2.1, -4.65); for (let r = 0; r < 4; r++) { box(K, 3.1, 0.06, 0.55, 0x4a2e1a, x, 0.5 + r * 1, -4.6); let bx = x - 1.45; while (bx < x + 1.4) { const w = 0.08 + K.R() * 0.1, h = 0.55 + K.R() * 0.3; const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.4), K.mat(bookC[Math.floor(K.R() * bookC.length)], 0.7)); b.position.set(bx + w / 2, 0.55 + r * 1 + h / 2, -4.55); K.scene.add(b); bx += w + 0.01; } } }
    for (const s of [-1, 1]) { box(K, 2.6, 0.1, 1.4, 0x8a5a2b, s * 8.2, 1, 0); for (const dx of [-1.1, 1.1]) box(K, 0.08, 1, 1.3, 0x6e4224, s * 8.2 + dx, 0.5, 0); cyl(K, 0.05, 0.07, 0.6, 0x2a2a2a, s * 8.2, 1.35, -0.4, 8); halo(K, s * 8.2, 1.75, -0.4, 1, 0xffd08a, 0.8); const sh = new THREE.Mesh(new THREE.ConeGeometry(0.25, 0.25, 14, 1, true), glow(0x3f8a54)); sh.position.set(s * 8.2, 1.75, -0.4); K.scene.add(sh); }
  } },
  lab: { indoor: true, build(K) {
    walls(K, 0xeef2f5, 0xc7cdd6, { trim: 0x7a8a9a, winX: 6 });
    for (const s of [-1, 1]) { box(K, 3.2, 1, 1.2, 0xf4f4f4, s * 8, 0.5, -2, 0.4); box(K, 3.3, 0.08, 1.3, 0x2a2a2a, s * 8, 1.04, -2, 0.3);
      for (let k = 0; k < 4; k++) { const c = [0x7affc8, 0xff6fa5, 0x7ad0ff, 0xffe066][k]; const fl = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.36, 12), K.mat(0xe8f4ff, 0.05, { transparent: true, opacity: 0.45 })); fl.position.set(s * 8 - 1.2 + k * 0.8, 1.26, -2); K.scene.add(fl); const liq = new THREE.Mesh(new THREE.ConeGeometry(0.11, 0.18, 12), glow(c)); liq.position.set(s * 8 - 1.2 + k * 0.8, 1.17, -2); K.scene.add(liq); halo(K, s * 8 - 1.2 + k * 0.8, 1.25, -1.9, 0.7, c, 0.5); } }
    const wb = new THREE.Mesh(new THREE.PlaneGeometry(5, 2.4), K.mat(0xffffff, 0.3)); wb.position.set(-1.5, 3.1, -4.96); K.scene.add(wb);
    for (let k = 0; k < 4; k++) { const ln = new THREE.Mesh(new THREE.PlaneGeometry(1.5 + K.R() * 2.5, 0.05), glow([0x2f7fe0, 0xd8343c, 0x2a2a2a][k % 3])); ln.position.set(-2.4 + K.R(), 3.8 - k * 0.45, -4.95); K.scene.add(ln); }
  } },
  rooftop: { ground: 0xa9a49a, build(K) {
    for (const [w, d, x, z] of [[40, 0.3, 0, -9], [0.3, 20, -12, 0], [0.3, 20, 12, 0]]) box(K, w, 1.1, d, 0xc9c2b4, x, 0.55, z);
    cyl(K, 1.3, 1.3, 2.2, 0x2a2a2a, -8.5, 2.6, -6.5, 16); for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) cyl(K, 0.06, 0.06, 1.5, 0x6a6a6a, -8.5 + dx, 0.75, -6.5 + dz, 6);
    cyl(K, 0.03, 0.03, 2.2, 0x6a6a6a, 6, 1.1, -6, 6); cyl(K, 0.03, 0.03, 2.2, 0x6a6a6a, 10, 1.1, -6, 6); cyl(K, 0.01, 0.01, 4, 0x3a3a3a, 8, 2.1, -6, 4).rotation.z = Math.PI / 2;
    for (let k = 0; k < 4; k++) { const cl = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.8), K.mat([0xd8343c, 0x2f7fe0, 0xf2c12e, 0x3f9a3a][k], 0.8, { side: THREE.DoubleSide })); cl.position.set(6.5 + k * 0.95, 1.6, -6); K.scene.add(cl); }
    for (let k = 0; k < 8; k++) building(K, -30 + k * 8.5, -24 - (k % 3) * 6, 6, 10 + K.R() * 16, 6, [0xd9c7b0, 0xb9c4d0, 0xe6d3c3, 0xf0b9a0][k % 4], isNight(K));
    skyline(K);
  } },
  playground: { ground: 0x7aaa4a, build(K) {
    for (const x of [-9, -7]) { cyl(K, 0.06, 0.06, 3, 0xd8343c, x, 1.5, -6, 6); } box(K, 2.4, 0.1, 0.1, 0xd8343c, -8, 3, -6); for (const x of [-8.5, -7.5]) { cyl(K, 0.01, 0.01, 2, 0x3a3a3a, x, 2, -6, 4); box(K, 0.5, 0.06, 0.25, 0xf2c12e, x, 1, -6); }
    box(K, 1, 2.2, 1, 0x2f7fe0, 8, 1.1, -7); const slide = box(K, 0.9, 0.08, 3.4, 0xf2c12e, 8, 1.1, -5); slide.rotation.x = -0.6;
    const ss = box(K, 3, 0.12, 0.3, 0x3f9a3a, 0, 0.6, -9); ss.rotation.z = 0.2; cyl(K, 0.15, 0.2, 0.5, 0x6a6a6a, 0, 0.25, -9, 8);
    plane(K, 4, 3, 0xe6d2a0, -3.5, 0.01, -10);
    for (let k = -10; k <= 10; k++) cyl(K, 0.05, 0.05, 1.1, 0xf4f4f4, k * 1.6, 0.55, -14, 6); box(K, 33, 0.08, 0.06, 0xf4f4f4, 0, 0.9, -14);
    K.forest([0x4f9a3a, 0x6cb648], 20); K.tufts(80); K.flowers(16);
  } },
  garden: { ground: 0x6fae4a, build(K) {
    for (const s of [-1, 1]) for (let k = 0; k < 4; k++) { const x = s * (8 + k * 0.1), z = -3 - k * 3; box(K, 2.2, 0.3, 2, 0x6e4224, x, 0.15, z); for (let f = 0; f < 8; f++) { const fl = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 6), K.mat([0xff5c8a, 0xffd23f, 0xffffff, 0xb57bff, 0xff8a1f][(f + k) % 5], 0.6)); fl.position.set(x - 0.8 + (f % 4) * 0.5, 0.42, z - 0.5 + Math.floor(f / 4)); K.scene.add(fl); } }
    for (let k = -4; k <= 4; k++) box(K, 1.6, 1, 0.7, 0x3f7a2e, k * 1.8, 0.5, -13, 0.9);
    cyl(K, 1.6, 1.8, 0.5, 0xd9d4c8, 0, 0.25, -8, 24); cyl(K, 0.2, 0.25, 1.2, 0xd9d4c8, 0, 0.8, -8, 12); const wtr = new THREE.Mesh(new THREE.CylinderGeometry(1.45, 1.45, 0.05, 24), K.mat(0x6fc8e8, 0.1)); wtr.position.set(0, 0.48, -8); K.scene.add(wtr);
    bench(K, -4.5, -6, 0.3); bench(K, 4.5, -6, -0.3);
    K.forest([0x4f9a3a, 0x6cb648, 0x3f8a34], 22);
  } },
  lake: { ground: 0x6fae4a, build(K) {
    water(K, 120, 40, 0, -28, 0x3f9fc8);
    box(K, 2, 0.15, 9, 0x8a5a2b, 6, 0.3, -9); for (let k = 0; k < 5; k++) for (const dx of [-0.9, 0.9]) cyl(K, 0.08, 0.08, 1, 0x6e4224, 6 + dx, 0, -5 - k * 2, 6);
    const boat = box(K, 3, 0.5, 1.1, 0xd8343c, 9, 0.2, -14); boat.rotation.y = 0.5;
    reeds(K, 50, -20, 0, -9, -8); farHills(K, 0x5f8f4a); K.forest([0x3f8a34, 0x4f9a3a], 25); K.tufts(80); K.flowers(14);
  } },
  waterfall: { ground: 0x6a9a44, build(K) {
    for (let k = 0; k < 7; k++) { const r = new THREE.Mesh(new THREE.DodecahedronGeometry(4 + K.R() * 3), K.mat(0x7a7466, 0.95)); r.position.set(-14 + k * 4.6, 4 + (k % 2) * 3, -22 - K.R() * 3); r.scale.y = 1.6; K.scene.add(r); }
    const fall = new THREE.Mesh(new THREE.PlaneGeometry(4, 12), K.mat(0xd9f2ff, 0.2, { transparent: true, opacity: 0.85 })); fall.position.set(0, 6, -18.5); K.scene.add(fall);
    for (let k = 0; k < 10; k++) { const st = new THREE.Mesh(new THREE.PlaneGeometry(0.15, 12), glow(0xffffff)); st.position.set(-1.8 + k * 0.4, 6, -18.4); K.scene.add(st); }
    water(K, 22, 10, 0, -13, 0x3fa8c8); for (let k = 0; k < 14; k++) halo(K, (K.R() - 0.5) * 4, 0.6 + K.R(), -17.5 + K.R() * 2, 1.8, 0xffffff, 0.35);
    K.forest([0x2f7a2e, 0x3f8a34, 0x4f9a3a], 30); K.rocks(10); K.tufts(80);
  } },
  jungle: { ground: 0x4f7f34, build(K) {
    for (let i = 0; i < 40; i++) { const x = (K.R() - 0.5) * 50, z = -5 - K.R() * 25; if (!K.keepClear(x, z)) K.tree(x, z, 1.1 + K.R() * 0.8, [0x2f6a2a, 0x3f7a2e, 0x2a5a24]); }
    for (let i = 0; i < 12; i++) { const v = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4 + K.R() * 3, 5), K.mat(0x3f6a2a, 0.9)); v.position.set((K.R() < 0.5 ? -1 : 1) * (7 + K.R() * 8), 4, -5 - K.R() * 10); K.scene.add(v); }
    for (let i = 0; i < 14; i++) { const lf = new THREE.Mesh(new THREE.SphereGeometry(1, 10, 6), K.mat(0x3f8a34, 0.7)); lf.scale.set(1.4, 0.08, 0.6); lf.rotation.set(0.4, K.R() * 6, 0.3); lf.position.set((K.R() < 0.5 ? -1 : 1) * (7.5 + K.R() * 5), 0.6 + K.R(), -1 - K.R() * 8); K.scene.add(lf); }
    for (let i = 0; i < 8; i++) palm(K, (K.R() < 0.5 ? -1 : 1) * (9 + K.R() * 10), -4 - K.R() * 14, 0.9 + K.R() * 0.4);
    K.tufts(160, 0x3f7a2e); K.flowers(20); K.mushrooms(6);
    if (K.scene.fog) { K.scene.fog.near = 8; K.scene.fog.far = 45; }
  } },
  field: { ground: 0x9ab84a, build(K) {
    for (let r = 0; r < 14; r++) for (let k = 0; k < 40; k++) { const w = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.9 + K.R() * 0.3, 5), K.mat(K.w.weather === "clear" ? 0xd9b84a : 0xc9a84a, 0.9)); w.position.set(-30 + k * 1.5 + (K.R() - 0.5) * 0.4, 0.45, -7 - r * 1.4); K.scene.add(w); }
    const sc = new THREE.Group(); const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.6, 6), K.mat(0x6e4224)); pole.position.y = 1.3; sc.add(pole); const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2, 6), K.mat(0x6e4224)); arm.rotation.z = Math.PI / 2; arm.position.y = 1.9; sc.add(arm);
    const shirt = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.8, 0.3), K.mat(0xd8343c)); shirt.position.y = 1.7; sc.add(shirt); const hd = new THREE.Mesh(new THREE.SphereGeometry(0.25, 12, 8), K.mat(0xf3d7a6)); hd.position.y = 2.4; sc.add(hd); const hat = new THREE.Mesh(new THREE.ConeGeometry(0.45, 0.3, 14), K.mat(0xc9a24a)); hat.position.y = 2.7; sc.add(hat);
    sc.position.set(-9, 0, -10); sc.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(sc);
    K.house(16, -24, -0.3, 0xf3d7a6, 0xc0392b); farHills(K); K.tufts(60);
  } },
  haveli: { ground: 0xd9b88a, build(K) {
    const wall = 0xe8a86a, trim = 0xb0502a;
    box(K, 30, 7, 1, wall, 0, 3.5, -10); for (const s of [-1, 1]) box(K, 1, 7, 20, wall, s * 13, 3.5, 0);
    for (let k = -2; k <= 2; k++) { const a = new THREE.Mesh(new THREE.TorusGeometry(1, 0.15, 8, 16, Math.PI), K.mat(trim, 0.8)); a.position.set(k * 4.5, 2.6, -9.45); K.scene.add(a); box(K, 1.9, 2.6, 0.1, 0x5a3a22, k * 4.5, 1.3, -9.48); }
    for (let k = -2; k <= 2; k++) { box(K, 1.8, 1.1, 0.8, trim, k * 4.5, 5.3, -9.2); const jw = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.7), glow(isNight(K) ? 0xffd08a : 0x3a2614)); jw.position.set(k * 4.5, 5.3, -8.79); K.scene.add(jw); }
    box(K, 1.2, 0.9, 1.2, 0xc0582f, 0, 0.45, -5); bush(K, 0, -5, 0.5, 0x3f8a34);
    for (const dx of [-1.1, 1.1]) cyl(K, 0.02, 0.02, 3.2, 0x5a3a22, -8 + dx, 2.4, -6, 4); box(K, 2.4, 0.12, 0.8, 0x8a5a2b, -8, 0.9, -6); box(K, 2.6, 0.1, 0.1, 0x5a3a22, -8, 4, -6);
    box(K, 1.9, 0.12, 0.9, 0xd9b98a, 8, 0.55, -5); for (const [dx, dz] of [[-0.85, -0.4], [0.85, -0.4], [-0.85, 0.4], [0.85, 0.4]]) cyl(K, 0.05, 0.05, 0.55, 0x6e4224, 8 + dx, 0.27, -5 + dz, 6);
    for (let k = -3; k <= 3; k++) diya(K, k * 1.2, -8.8, 0, k === 0);
  } },
  mela: { ground: 0xc8b48c, build(K) {
    const fw = new THREE.Group(); fw.add(new THREE.Mesh(new THREE.TorusGeometry(5, 0.15, 8, 40), K.mat(0xd8343c, 0.5)));
    for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2; const sp = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 5, 5), K.mat(0xf4f4f4)); sp.rotation.z = a; sp.position.set(Math.sin(-a) * 2.5, Math.cos(a) * 2.5, 0); fw.add(sp);
      const cab = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.7, 0.8), K.mat([0xf2c12e, 0x2f7fe0, 0x3f9a3a, 0xff6fa5][k % 4], 0.6)); cab.position.set(Math.cos(a) * 5, Math.sin(a) * 5 - 0.5, 0); fw.add(cab); }
    fw.position.set(-9, 6.5, -14); K.scene.add(fw); for (const dx of [-1.5, 1.5]) { const leg = cyl(K, 0.15, 0.2, 7, 0x6a6a6a, -9 + dx, 3.5, -14, 8); leg.rotation.z = dx * 0.15; }
    cyl(K, 3.2, 3.2, 0.4, 0xf2c12e, 9, 0.2, -12, 24); const roof = new THREE.Mesh(new THREE.ConeGeometry(3.6, 1.6, 24), K.mat(0xd8343c, 0.6)); roof.position.set(9, 4, -12); K.scene.add(roof); cyl(K, 0.15, 0.15, 3.6, 0xf4f4f4, 9, 2, -12, 8);
    for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2; const h = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.6, 1), K.mat([0xffffff, 0x7ad0ff][k % 2], 0.6)); h.position.set(9 + Math.cos(a) * 2.4, 1, -12 + Math.sin(a) * 2.4); K.scene.add(h); }
    stall(K, -3, -10, 0, 0xd8343c, 0xffffff); stall(K, 3, -10.5, 0, 0x2f7fe0, 0xf2c12e);
    stringLights(K, -12, 12, 5.5, -7, 22); for (let k = 0; k < 10; k++) halo(K, -10 + k * 2.2, 5.2, -7, 0.8, 0xffe066, 0.55);
    prop(K, "balloons", 6, -6, 0, 1);
  } },
  stage: { indoor: true, build(K) {
    plane(K, 30, 30, 0x5a3a2a, 0, 0, 0, 0.7); box(K, 22, 0.6, 9, 0x6e4224, 0, -0.3, -1);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(30, 10), K.mat(0x1a1020, 1)); back.position.set(0, 5, -6); K.scene.add(back);
    for (const s of [-1, 1]) { for (let k = 0; k < 6; k++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 8, 10), K.mat(0x9a1a2a, 0.8)); c.position.set(s * (7.5 + k * 0.55), 4, -5 + k * 0.1); K.scene.add(c); } }
    const valance = box(K, 24, 1.2, 0.4, 0x9a1a2a, 0, 7.6, -4.8);
    for (let k = -4; k <= 4; k++) { const fl = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 6), glow(0xfff2b0)); fl.position.set(k * 2, 0.05, 3.2); K.scene.add(fl); halo(K, k * 2, 0.15, 3.2, 0.9, 0xffe8a0, 0.6); }
    for (const x of [-5, 5]) { const sp = new THREE.SpotLight(0xfff0d0, 40, 30, 0.35, 0.5); sp.position.set(x, 9, 6); sp.target.position.set(x * 0.3, 0, 0); K.scene.add(sp); K.scene.add(sp.target); halo(K, x, 9, 6, 1.4, 0xffffff, 0.8); }
  } },
  space_station: { indoor: true, build(K) {
    plane(K, 30, 30, 0x4a5060, 0, 0, 0, 0.5); const back = new THREE.Mesh(new THREE.PlaneGeometry(30, 9), K.mat(0xc7cdd6, 0.4, { metalness: 0.5 })); back.position.set(0, 4.5, -5); K.scene.add(back);
    for (const s of [-1, 1]) { const side = new THREE.Mesh(new THREE.PlaneGeometry(20, 9), K.mat(0xb9c0cc, 0.4, { metalness: 0.5 })); side.position.set(s * 11, 4.5, 3); side.rotation.y = -s * Math.PI / 2; K.scene.add(side); }
    const win = new THREE.Mesh(new THREE.CircleGeometry(2.2, 40), glow(0x02030a)); win.position.set(0, 4.2, -4.97); K.scene.add(win);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(2.25, 0.2, 10, 40), K.mat(0x6a7480, 0.3, { metalness: 0.7 })); ring.position.set(0, 4.2, -4.92); K.scene.add(ring);
    const pl = new THREE.Mesh(new THREE.CircleGeometry(0.9, 30), glow(0x4a8fd8)); pl.position.set(0.6, 3.8, -4.96); K.scene.add(pl);
    for (let k = 0; k < 30; k++) { const st = new THREE.Mesh(new THREE.CircleGeometry(0.025, 5), glow(0xffffff)); const a = K.R() * 6.28, r = K.R() * 2; st.position.set(Math.cos(a) * r, 4.2 + Math.sin(a) * r, -4.965); K.scene.add(st); }
    for (const s of [-1, 1]) { box(K, 3, 1.1, 1.2, 0x2a3040, s * 8, 0.55, -3.5, 0.4); const pan = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 0.6), glow(0x7affc8)); pan.position.set(s * 8, 1.15, -2.89); pan.rotation.x = -0.5; K.scene.add(pan); for (let k = 0; k < 5; k++) halo(K, s * 8 - 1 + k * 0.5, 1.2, -2.8, 0.4, [0xff3b30, 0x7affc8, 0xffe066][k % 3], 0.7); }
    for (let k = -2; k <= 2; k++) { const l = new THREE.Mesh(new THREE.BoxGeometry(2, 0.05, 0.3), glow(0xdff6ff)); l.position.set(k * 4, 8.9, 0); K.scene.add(l); }
    const amb = new THREE.PointLight(0xbfe8ff, 2, 20); amb.position.set(0, 7, 1); K.scene.add(amb);
  } },
  planet: { ground: 0x7a4a8a, build(K) {
    K.scene.background = new THREE.Color(0x2a1040); if (K.scene.fog) { K.scene.fog.color = new THREE.Color(0x5a2a6a); K.scene.fog.near = 25; K.scene.fog.far = 90; }
    for (let k = 0; k < 8; k++) { const c = new THREE.Mesh(new THREE.TorusGeometry(1.2 + K.R() * 2, 0.35, 8, 24), K.mat(0x5a3a6a, 0.9)); c.rotation.x = Math.PI / 2; c.position.set((K.R() - 0.5) * 40, 0.05, -6 - K.R() * 25); K.scene.add(c); }
    for (let k = 0; k < 12; k++) { const cr = new THREE.Mesh(new THREE.ConeGeometry(0.5 + K.R() * 0.8, 2 + K.R() * 5, 5), glow([0x7affc8, 0xff6fd8, 0x7ad0ff][k % 3])); cr.position.set((K.R() < 0.5 ? -1 : 1) * (8 + K.R() * 14), 1, -4 - K.R() * 22); cr.rotation.z = (K.R() - 0.5) * 0.4; K.scene.add(cr); halo(K, cr.position.x, 1.5, cr.position.z, 3, 0xff9af0, 0.35); }
    for (const [x, y, r, c] of [[-30, 30, 6, 0xffc8a0], [25, 22, 3, 0xa0e8ff]]) { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 24, 16), glow(c)); m.position.set(x, y, -90); K.scene.add(m); }
    for (let k = 0; k < 120; k++) { const s = new THREE.Mesh(new THREE.SphereGeometry(0.15, 6, 4), glow(0xffffff)); s.position.set((K.R() - 0.5) * 220, 20 + K.R() * 60, -95); K.scene.add(s); }
  } },
  underwater: { ground: 0xd9c89a, build(K) {
    K.scene.background = new THREE.Color(0x0a3a6a); K.scene.fog = new THREE.Fog(0x0e4a7a, 6, 40);
    for (let k = 0; k < 18; k++) { const x = (K.R() < 0.5 ? -1 : 1) * (7.5 + K.R() * 12), z = -3 - K.R() * 22, c = [0xff6f8a, 0xffa64a, 0xb57bff, 0xffe066][k % 4];
      if (k % 2) cyl(K, 0.15, 0.3, 1 + K.R() * 2, c, x, 0.8, z, 8); else { const s = new THREE.Mesh(new THREE.SphereGeometry(0.6 + K.R() * 0.6, 12, 8), K.mat(c, 0.6)); s.scale.y = 0.6; s.position.set(x, 0.3, z); K.scene.add(s); } }
    for (let k = 0; k < 24; k++) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.08, 2 + K.R() * 3, 5), K.mat(0x3f9a5a, 0.8)); w.position.set((K.R() - 0.5) * 34, 1.2, -4 - K.R() * 20); w.rotation.z = (K.R() - 0.5) * 0.4; K.scene.add(w); }
    for (let k = 0; k < 40; k++) halo(K, (K.R() - 0.5) * 20, 0.5 + K.R() * 8, -2 - K.R() * 14, 0.25, 0xcfe8ff, 0.6);
    for (let k = 0; k < 6; k++) { const ray = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 20), new THREE.MeshBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.08, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide })); ray.position.set(-12 + k * 5, 8, -12); ray.rotation.z = 0.25; K.scene.add(ray); }
    K.rocks(12); const amb = new THREE.HemisphereLight(0x7ac8ff, 0x1a3a5a, 0.9); K.scene.add(amb);
  } },
  castle: { ground: 0x7a8a5a, build(K) {
    const st = 0x9a9a98;
    box(K, 44, 8, 2, st, 0, 4, -16); for (let k = -10; k <= 10; k++) box(K, 1.1, 1, 2.1, st, k * 2.1, 8.5, -16);
    for (const x of [-12, 12, -24, 24]) { cyl(K, 2.4, 2.6, 13, st, x, 6.5, -16, 16); const r = new THREE.Mesh(new THREE.ConeGeometry(3, 4, 16), K.mat(0x3a4a8a, 0.7)); r.position.set(x, 15, -16); K.scene.add(r); const fl = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.7), K.mat(0xd8343c, 0.7, { side: THREE.DoubleSide })); fl.position.set(x + 0.6, 18, -16); K.scene.add(fl); cyl(K, 0.03, 0.03, 2, 0x3a3a3a, x, 17.5, -16, 4); }
    const arch = new THREE.Mesh(new THREE.TorusGeometry(2, 0.4, 8, 20, Math.PI), K.mat(0x7a7a78, 0.9)); arch.position.set(0, 3.6, -14.9); K.scene.add(arch); box(K, 3.6, 3.6, 0.3, 0x4a3020, 0, 1.8, -14.95);
    box(K, 4, 0.2, 6, 0x6e4224, 0, 0.1, -11.5); for (const x of [-4, 4]) torch(K, x, -13.5, 2.6);
    farHills(K, 0x6a8a4a); K.tufts(60);
  } },
  haunted_house: { ground: 0x3a4a34, build(K) {
    const h = new THREE.Group(); const body = new THREE.Mesh(new THREE.BoxGeometry(10, 7, 6), K.mat(0x3a3036, 0.95)); body.position.y = 3.5; h.add(body);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(7.5, 4, 4), K.mat(0x1f1a22, 0.95)); roof.position.y = 9; roof.rotation.y = Math.PI / 4; roof.scale.set(1, 1, 0.65); h.add(roof);
    const tower = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 6, 10), K.mat(0x3a3036, 0.95)); tower.position.set(4, 8, 0); h.add(tower); const tr = new THREE.Mesh(new THREE.ConeGeometry(1.6, 2.6, 10), K.mat(0x1f1a22)); tr.position.set(4, 12.3, 0); h.add(tr);
    for (const [x, y] of [[-3, 2], [3, 2], [-3, 5], [0, 5], [3, 5]]) { const w = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 1.4), glow(K.R() < 0.5 ? 0xffb84a : 0x141018)); w.position.set(x, y, 3.01); h.add(w); }
    const door = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 2.4), K.mat(0x1a1016)); door.position.set(0, 1.2, 3.02); h.add(door);
    h.position.set(0, 0, -16); h.rotation.z = 0.02; K.scene.add(h); halo(K, -3, 2, -12.9, 1.6, 0xffb84a, 0.6);
    for (let k = -8; k <= 8; k++) { const p = cyl(K, 0.05, 0.05, 1.2 + K.R() * 0.4, 0x2a2a2a, k * 1.3, 0.6, -8, 5); p.rotation.z = (K.R() - 0.5) * 0.3; }
    for (const [x, z] of [[-10, -8], [11, -10], [-13, -14], [14, -6]]) deadTree(K, x, z, 1.2 + K.R() * 0.5);
    if (K.scene.fog) { K.scene.fog.near = Math.min(K.scene.fog.near, 8); K.scene.fog.far = Math.min(K.scene.fog.far, 40); }
  } },
  graveyard: { ground: 0x3f5a3a, build(K) {
    for (let r = 0; r < 4; r++) for (let k = 0; k < 7; k++) { const x = -12 + k * 4 + (K.R() - 0.5), z = -6 - r * 3.4; if (Math.abs(x) < 7 && z > -7) continue; gravestone(K, x, z, (K.R() - 0.5) * 0.3); }
    for (let k = -12; k <= 12; k++) { cyl(K, 0.04, 0.04, 1.6, 0x1a1a1a, k * 1.2, 0.8, -20, 5); const tip = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.2, 5), K.mat(0x1a1a1a)); tip.position.set(k * 1.2, 1.7, -20); K.scene.add(tip); }
    for (const [x, z] of [[-10, -4], [10, -5], [-15, -16], [15, -15]]) deadTree(K, x, z, 1.4);
    K.tufts(80, 0x2a4a2a);
    if (K.scene.fog) { K.scene.fog.near = Math.min(K.scene.fog.near, 6); K.scene.fog.far = Math.min(K.scene.fog.far, 36); }
  } },
  bus_stop: { ground: 0xa9a49a, build(K) {
    plane(K, 10, 140, 0x3c3f45, 0, 0.012, -40, 0.9); for (let k = 0; k < 16; k++) plane(K, 0.25, 1.6, 0xf4f4f4, 0, 0.02, -2 - k * 5);
    const sh = new THREE.Group(); const roof = new THREE.Mesh(new THREE.BoxGeometry(5, 0.15, 2), K.mat(0x2f7fe0, 0.5)); roof.position.y = 2.8; sh.add(roof);
    for (const dx of [-2.3, 2.3]) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.8, 6), K.mat(0x6a6a6a)); p.position.set(dx, 1.4, -0.8); sh.add(p); }
    const back = new THREE.Mesh(new THREE.PlaneGeometry(4.6, 1.8), K.mat(0xcfe8ff, 0.1, { transparent: true, opacity: 0.5 })); back.position.set(0, 1.6, -0.9); sh.add(back);
    sh.position.set(-9, 0, -4); sh.rotation.y = 0.5; sh.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(sh); bench(K, -9, -3.6, 0.5, 0x6a6a6a);
    cyl(K, 0.05, 0.05, 2.6, 0x6a6a6a, -6.5, 1.3, -2, 6); box(K, 0.6, 0.6, 0.05, 0x3f9a3a, -6.5, 2.6, -2);
    const bus = new THREE.Group(); const bb = new THREE.Mesh(new THREE.BoxGeometry(9, 3, 2.6), K.mat(0xf2c12e, 0.5)); bb.position.y = 1.9; bus.add(bb);
    for (let k = 0; k < 6; k++) { const w = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.9), isNight(K) ? glow(0xffe49a) : K.mat(0x9fc3dd, 0.2)); w.position.set(-3.6 + k * 1.4, 2.4, 1.31); bus.add(w); }
    for (const x of [-3, 3]) for (const z of [1.3, -1.3]) { const wh = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.3, 14), K.mat(0x1a1a1a)); wh.rotation.x = Math.PI / 2; wh.position.set(x, 0.5, z); bus.add(wh); }
    bus.position.set(2.5, 0, -16); bus.rotation.y = Math.PI / 2 + 0.05; bus.traverse(o => { if (o.isMesh) o.castShadow = true; }); K.scene.add(bus);
    for (let k = 0; k < 5; k++) building(K, 14, -6 - k * 9, 7, 8 + K.R() * 10, 6, [0xd9c7b0, 0xb9c4d0, 0xe6d3c3][k % 3], isNight(K), -Math.PI / 2);
    skyline(K);
  } },
});

// ---------------------------------------------------------------- every kit gets the beauty pass and its culture and era
const URBAN = new Set(["city_street", "bazaar", "bus_stop", "highway", "rooftop", "station", "mela"]);
const NATURE = new Set(["temple", "ruins", "river", "lake", "garden", "playground", "field", "mountain", "waterfall", "jungle", "castle", "palace"]);
for (const [name, kit] of Object.entries(KITS)) {
  if (kit._dressed) continue;
  const base = kit.build;
  kit._dressed = true;
  kit.build = K => {
    base(K);
    if (kit.indoor || ["planet", "underwater"].includes(name)) return;
    const cult = K.w.culture || "indian", era = K.w.era || "modern";
    // depth: varied ground, soft bushes to the sides in front, a far horizon behind
    groundPatches(K, 14, [kit.ground ? new THREE.Color(kit.ground).offsetHSL(0, 0, -0.05).getHex() : 0x5f9f40, kit.ground ? new THREE.Color(kit.ground).offsetHSL(0, 0, 0.04).getHex() : 0x7fbf50]);
    if (NATURE.has(name)) { for (const s of [-1, 1]) bush(K, s * (8.5 + K.R() * 2), 3.5 + K.R() * 2, 0.9 + K.R() * 0.4); farHills(K, isNight(K) ? 0x2a3a3a : 0x8fae6a); }
    if (URBAN.has(name) && !["rooftop", "bus_stop"].includes(name)) skyline(K, isNight(K) ? 0x2a3048 : 0x8a93a6);
    // culture: what a street there looks like
    if (URBAN.has(name) && cult === "japanese") for (let k = 0; k < 8; k++) lantern(K, (k % 2 ? -1 : 1) * 7.8, 3.2, -3 - Math.floor(k / 2) * 4);
    if (URBAN.has(name) && cult === "western") { for (const s of [-1, 1]) { box(K, 0.5, 0.5, 0.7, 0x2f5fa0, s * 7.6, 1.15, 1.5); cyl(K, 0.05, 0.05, 0.9, 0x4a4a4a, s * 7.6, 0.45, 1.5, 6); } cyl(K, 0.22, 0.25, 0.8, 0xd8343c, 7.2, 0.4, 4, 10); }
    if (URBAN.has(name) && cult === "indian" && name !== "highway") for (let k = 0; k < 4; k++) { cyl(K, 0.08, 0.1, 6.5, 0x4a4a4a, (k % 2 ? -1 : 1) * 16, 3.25, -6 - k * 9, 6); }
    // era: torches instead of electric lights in the old times, neon in the future
    if (era === "ancient" && URBAN.has(name)) for (const s of [-1, 1]) for (let k = 0; k < 3; k++) torch(K, s * 7.4, -2 - k * 6);
    if (era === "future" && URBAN.has(name)) for (let k = 0; k < 8; k++) { const n = new THREE.Mesh(new THREE.BoxGeometry(0.1, 3 + K.R() * 3, 0.1), glow([0xff3bd0, 0x3bd8ff, 0x9dff3b][k % 3])); n.position.set((k % 2 ? -1 : 1) * 10.4, 4 + K.R() * 3, -4 - k * 4); K.scene.add(n); halo(K, n.position.x, n.position.y, n.position.z, 2, n.material.color.getHex(), 0.5); }
  };
}
