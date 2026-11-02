"use client";

import { Canvas } from "@react-three/fiber";
import { Grid, Html, OrbitControls } from "@react-three/drei";
import { useEffect, useState } from "react";
import { Machine, machineSeverity, Severity } from "@/lib/api";

const ZONES = [
  { id: "A", name: "Zone A: Manufacturing", x: -10.5, width: 15 },
  { id: "B", name: "Zone B: Fluid Systems", x: 5, width: 12 },
  { id: "C", name: "Zone C: Power and Environment", x: 17.5, width: 11 },
];

const SIZE: Record<string, [number, number, number]> = {
  motor: [3, 2, 2],
  conveyor: [4.5, 1, 1.8],
  robot: [1.8, 3.2, 1.8],
  pump: [2.4, 1.8, 2],
  tank: [2.6, 4, 2.6],
  power: [2, 3, 1.4],
  environment: [1.4, 2.2, 1.4],
};

function useThemeColors() {
  const [colors, setColors] = useState<Record<string, string>>({});
  useEffect(() => {
    const read = () => {
      const style = getComputedStyle(document.documentElement);
      const get = (name: string) => style.getPropertyValue(`--${name}`).trim();
      setColors({
        good: get("idle"),
        warning: get("warning"),
        critical: get("critical"),
        idle: get("surface-2"),
        floor: get("surface"),
        line: get("line"),
        accent: get("accent"),
      });
    };
    read();
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return colors;
}

function MachineMesh({
  machine,
  selected,
  colors,
  onSelect,
}: {
  machine: Machine;
  selected: boolean;
  colors: Record<string, string>;
  onSelect: () => void;
}) {
  const { severity, label } = machineSeverity(machine);
  const size = SIZE[machine.kind] ?? [2, 2, 2];
  const [x, z] = machine.position;
  const faulted = (["warning", "critical"] as Severity[]).includes(severity);
  return (
    <group position={[x, size[1] / 2, z]}>
      <mesh
        onClick={(event) => {
          event.stopPropagation();
          onSelect();
        }}
        onPointerOver={() => (document.body.style.cursor = "pointer")}
        onPointerOut={() => (document.body.style.cursor = "")}
      >
        {machine.kind === "tank" ? (
          <cylinderGeometry args={[size[0] / 2, size[0] / 2, size[1], 24]} />
        ) : (
          <boxGeometry args={size} />
        )}
        <meshStandardMaterial color={colors[severity] || "#888"} roughness={0.75} />
      </mesh>
      {selected && (
        <mesh>
          <boxGeometry args={[size[0] + 0.3, size[1] + 0.3, size[2] + 0.3]} />
          <meshBasicMaterial color={colors.accent || "#2a78d6"} wireframe />
        </mesh>
      )}
      {(faulted || selected) && (
        <Html center position={[0, size[1] / 2 + 0.7, 0]} zIndexRange={[10, 0]}>
          <div
            className="pointer-events-none whitespace-nowrap rounded border px-1.5 py-0.5 text-[11px] capitalize"
            style={{ background: "var(--surface)", borderColor: "var(--line)", color: "var(--ink)" }}
          >
            {machine.machine_id}: {label}
          </div>
        </Html>
      )}
    </group>
  );
}

export default function Factory3D({
  machines,
  selectedId,
  onSelect,
}: {
  machines: Machine[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const colors = useThemeColors();
  return (
    <Canvas camera={{ position: [3, 24, 30], fov: 45 }} onPointerMissed={() => onSelect(null)}>
      <ambientLight intensity={1.1} />
      <directionalLight position={[10, 25, 12]} intensity={1.6} />
      {ZONES.map((zone) => (
        <group key={zone.id} position={[zone.x, 0, 0]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
            <planeGeometry args={[zone.width, 18]} />
            <meshStandardMaterial color={colors.floor || "#ccc"} />
          </mesh>
          <Html center position={[0, 0, 10]} zIndexRange={[5, 0]}>
            <div className="whitespace-nowrap text-[12px]" style={{ color: "var(--ink-2)" }}>
              {zone.name}
            </div>
          </Html>
        </group>
      ))}
      <Grid
        position={[3, 0, 0]}
        args={[60, 40]}
        cellColor={colors.line || "#999"}
        sectionColor={colors.line || "#999"}
        fadeDistance={80}
      />
      {machines.map((machine) => (
        <MachineMesh
          key={machine.machine_id}
          machine={machine}
          selected={machine.machine_id === selectedId}
          colors={colors}
          onSelect={() => onSelect(machine.machine_id)}
        />
      ))}
      <OrbitControls target={[3, 0, 0]} maxPolarAngle={Math.PI / 2.1} minDistance={8} maxDistance={70} />
    </Canvas>
  );
}
