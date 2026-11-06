import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { FOV, CAM_Z, H3, W3, toScreen } from "./project";

/** Layers as 3D slabs, top to bottom. One layer can be highlighted (e.g. attacker-controlled input). */
export const Stack3D: React.FC<{ layers: string[]; highlight?: number | null }> = ({ layers, highlight }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ry = -0.42 + Math.sin(frame / (fps * 2.6)) * 0.14, rx = 0.22 + Math.sin(frame / (fps * 3.3)) * 0.04;
  const gap = Math.min(1.9, 6.6 / layers.length);
  const y0 = ((layers.length - 1) * gap) / 2;
  const appear = (i: number) => spring({ frame: frame - 4 - i * 9, fps, config: { damping: 15, stiffness: 110 } });
  const pulse = 0.5 + 0.5 * Math.sin(frame / (fps * 0.28));
  return (
    <div style={{ position: "absolute", left: 285, top: 190, width: W3, height: H3 }}>
      <ThreeCanvas width={W3} height={H3} camera={{ fov: FOV, position: [0, 0, CAM_Z] }} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.85} />
        <directionalLight position={[5, 9, 10]} intensity={1.7} />
        <pointLight position={[-8, 2, 7]} intensity={26} color="#7dd3fc" />
        <group rotation={[rx, ry, 0]}>
          {layers.map((_, i) => {
            const hot = i === highlight;
            const a = Math.min(appear(i), 1);
            return (
              <mesh key={i} position={[(1 - a) * -6, y0 - i * gap, hot ? 0.5 : 0]} scale={Math.min(appear(i), 1.04)}>
                <boxGeometry args={[11.5, gap * 0.8, 2.4]} />
                <meshStandardMaterial color={hot ? "#7c4a03" : "#1b2f55"} emissive={hot ? "#fbbf24" : "#38bdf8"} emissiveIntensity={hot ? 0.35 + pulse * 0.55 : 0.1} metalness={0.25} roughness={0.35} />
              </mesh>
            );
          })}
        </group>
      </ThreeCanvas>
      {layers.map((l, i) => {
        const hot = i === highlight;
        const sp = toScreen([0, y0 - i * gap, (hot ? 0.5 : 0) + 1.2], rx, ry);
        return (<div key={i} style={{ position: "absolute", left: sp.x, top: sp.y, transform: `translate(-50%,-50%) scale(${Math.min(1.2, sp.scale)})`, opacity: Math.min(appear(i), 1), whiteSpace: "nowrap",
          color: hot ? "#fde68a" : "#f1f5f9", fontSize: 38, fontWeight: 700, fontFamily: "Menlo, 'DejaVu Sans Mono', monospace", textShadow: "0 2px 8px rgba(0,0,0,.95)" }}>{l}</div>);
      })}
    </div>
  );
};
