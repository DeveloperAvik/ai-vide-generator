import * as THREE from "three";

export const W3 = 1350, H3 = 630, FOV = 45, CAM_Z = 10;
const cams = new Map<number, THREE.PerspectiveCamera>();
function camAt(z: number) {
  let c = cams.get(z);
  if (!c) { c = new THREE.PerspectiveCamera(FOV, W3 / H3, 0.1, 100); c.position.set(0, 0, z); c.lookAt(0, 0, 0); c.updateMatrixWorld(true); c.updateProjectionMatrix(); cams.set(z, c); }
  return c;
}

/** Screen position (px inside the 3D canvas) of a point in a group rotated by (rx, ry): pins HTML labels to 3D objects. */
export function toScreen(p: [number, number, number], rx: number, ry: number, camZ = CAM_Z): { x: number; y: number; scale: number } {
  const v = new THREE.Vector3(...p).applyEuler(new THREE.Euler(rx, ry, 0));
  const dist = camZ - v.z;
  v.project(camAt(camZ));
  return { x: ((v.x + 1) / 2) * W3, y: ((1 - v.y) / 2) * H3, scale: camZ / dist };
}
