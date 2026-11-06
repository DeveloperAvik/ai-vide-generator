import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { SceneProps } from "../../utils/types";
import { FOV, H3, W3, toScreen } from "./project";

const CAM = 8; // closer camera than the stack scene so the graph fills the frame

type G = NonNullable<SceneProps["graph3d"]>;
const COLORS: Record<string, string> = { box: "#1e3a5f", diamond: "#5b3a0f", circle: "#2b3a67" };
const EDGE = "#38bdf8";

const Beam: React.FC<{ a: THREE.Vector3; b: THREE.Vector3; opacity: number }> = ({ a, b, opacity }) => {
  const dir = new THREE.Vector3().subVectors(b, a);
  const len = dir.length();
  const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  return (
    <mesh position={mid} quaternion={q}>
      <cylinderGeometry args={[0.045, 0.045, len, 12]} />
      <meshStandardMaterial color={EDGE} emissive={EDGE} emissiveIntensity={0.6} transparent opacity={opacity} />
    </mesh>
  );
};

export const Graph3D: React.FC<{ graph: G }> = ({ graph }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ry = Math.sin(frame / (fps * 2.4)) * 0.3, rx = -0.16 + Math.sin(frame / (fps * 3.1)) * 0.05;
  const pos = Object.fromEntries(graph.nodes.map((n) => [n.id, new THREE.Vector3(n.x, n.y, n.z)]));
  const appear = (i: number) => spring({ frame: frame - 6 - i * 10, fps, config: { damping: 14, stiffness: 120 } });
  const order = Object.fromEntries(graph.nodes.map((n, i) => [n.id, i]));
  return (
    <div style={{ position: "absolute", left: 285, top: 190, width: W3, height: H3 }}>
      <ThreeCanvas width={W3} height={H3} camera={{ fov: FOV, position: [0, 0, CAM] }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.9} />
        <directionalLight position={[6, 8, 10]} intensity={1.6} />
        <pointLight position={[-8, -4, 6]} intensity={30} color="#7dd3fc" />
        <group rotation={[rx, ry, 0]}>
          {graph.edges.map((e, i) => {
            const a = pos[e.a], b = pos[e.b];
            const o = Math.min(appear(Math.max(order[e.a], order[e.b])), 1);
            const t = ((frame / fps) * 0.55 + i * 0.27) % 1; // glowing packet travels a -> b, looping
            const p = new THREE.Vector3().lerpVectors(a, b, t);
            return (
              <group key={i}>
                <Beam a={a} b={b} opacity={0.55 * o} />
                <mesh position={p} scale={o}><sphereGeometry args={[0.17, 20, 20]} /><meshStandardMaterial color="#fbbf24" emissive="#fbbf24" emissiveIntensity={1.6} /></mesh>
              </group>
            );
          })}
          {graph.nodes.map((n, i) => {
            const s = Math.min(appear(i), 1.05);
            return (
              <group key={n.id} position={[n.x, n.y, n.z]} scale={s}>
                {n.shape === "diamond" ? (
                  <mesh scale={[1.5, 1.05, 0.9]}><octahedronGeometry args={[1]} /><meshStandardMaterial color={COLORS.diamond} emissive="#fbbf24" emissiveIntensity={0.25} metalness={0.2} roughness={0.35} /></mesh>
                ) : (
                  <mesh><boxGeometry args={[2.75, 1.25, 0.8]} /><meshStandardMaterial color={COLORS[n.shape] ?? COLORS.box} emissive={EDGE} emissiveIntensity={0.12} metalness={0.25} roughness={0.35} /></mesh>
                )}
              </group>
            );
          })}
        </group>
      </ThreeCanvas>
      {graph.nodes.map((n, i) => {
        const sp = toScreen([n.x, n.y, n.z + 0.45], rx, ry, CAM);
        const o = interpolate(appear(i), [0.4, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (<div key={n.id} style={{ position: "absolute", left: sp.x, top: sp.y, transform: `translate(-50%,-50%) scale(${Math.min(1.15, sp.scale)})`, opacity: o, width: 205, textAlign: "center",
          color: "#f1f5f9", fontSize: 22, fontWeight: 700, lineHeight: 1.15, textShadow: "0 2px 6px rgba(0,0,0,.9)" }}>{n.label}</div>);
      })}
      {graph.edges.filter((e) => e.label).map((e, i) => {
        const a = pos[e.a], b = pos[e.b];
        // label sits 30% along the edge, on the side away from the node it would otherwise cover
        const t = 0.3, up = b.y - a.y >= 0;
        const sp = toScreen([a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t + (up ? -0.62 : 0.62), a.z + (b.z - a.z) * t + 0.5], rx, ry, CAM);
        const o = Math.min(appear(Math.max(order[e.a], order[e.b])), 1);
        return (<div key={`l${i}`} style={{ position: "absolute", left: sp.x, top: sp.y, transform: "translate(-50%,-50%)", opacity: o, background: "#0b1220", color: "#fbbf24", fontSize: 19, fontWeight: 700, padding: "2px 10px", borderRadius: 8, border: "1px solid #3b2a12" }}>{e.label}</div>);
      })}
    </div>
  );
};
