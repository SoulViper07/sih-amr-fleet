import React, { useState, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Box, Html, Plane, Ring, Sphere, Cylinder } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  Clock, 
  Cpu, 
  Battery, 
  Zap, 
  Target, 
  Terminal, 
  Radio,
  Skull
} from 'lucide-react';

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';
const GRID_SIZE = 20;
const GRID_HALF = GRID_SIZE / 2;

const DEFAULT_CHARGING_STATIONS = [
  [0, 0],
  [6, 0],
  [12, 0],
  [19, 0]
];

function gridToWorld(x, y) {
  return [x - GRID_HALF + 0.5, 0.5, y - GRID_HALF + 0.5];
}

/* =========================================================================
   3D RACK COMPONENT (Industrial Storage Racks args={[0.9, 3, 0.9]})
   ========================================================================= */
const WarehouseRack = React.memo(({ x, y }) => {
  const [wx, , wz] = gridToWorld(x, y);

  return (
    <group position={[wx, 1.5, wz]}>
      {/* Main tall rack box */}
      <Box
        args={[0.9, 3, 0.9]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial 
          color="#334155" 
          metalness={0.65} 
          roughness={0.35} 
        />
      </Box>

      {/* Industrial shelving beam accents */}
      <Box args={[0.92, 0.04, 0.92]} position={[0, -0.75, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>
      <Box args={[0.92, 0.04, 0.92]} position={[0, 0, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>
      <Box args={[0.92, 0.04, 0.92]} position={[0, 0.75, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>

      {/* Vertical upright frame accents */}
      <Box args={[0.04, 3.02, 0.92]} position={[-0.44, 0, 0]}>
        <meshStandardMaterial color="#475569" metalness={0.9} roughness={0.2} />
      </Box>
      <Box args={[0.04, 3.02, 0.92]} position={[0.44, 0, 0]}>
        <meshStandardMaterial color="#475569" metalness={0.9} roughness={0.2} />
      </Box>
    </group>
  );
});

/* =========================================================================
   CHARGING PAD COMPONENT (Glowing Cyan <Plane> Markers at y=0)
   ========================================================================= */
const ChargingPad = React.memo(({ x, y }) => {
  const [wx, , wz] = gridToWorld(x, y);
  const ringRef = useRef();

  useFrame(({ clock }) => {
    if (ringRef.current) {
      const t = clock.getElapsedTime();
      ringRef.current.material.opacity = 0.5 + Math.sin(t * 3) * 0.3;
    }
  });

  return (
    <group position={[wx, 0, wz]}>
      {/* Glowing cyan floor marker plane */}
      <Plane
        args={[0.85, 0.85]}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.01, 0]}
        receiveShadow
      >
        <meshStandardMaterial
          color="#06b6d4"
          emissive="#22d3ee"
          emissiveIntensity={2.5}
          toneMapped={false}
          transparent
          opacity={0.85}
        />
      </Plane>

      {/* Dock border ring */}
      <Ring
        ref={ringRef}
        args={[0.36, 0.42, 4]}
        rotation={[-Math.PI / 2, 0, Math.PI / 4]}
        position={[0, 0.015, 0]}
      >
        <meshBasicMaterial color="#00ffff" transparent opacity={0.8} />
      </Ring>

      {/* Inner circular charging target */}
      <Ring
        args={[0.08, 0.16, 16]}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.02, 0]}
      >
        <meshBasicMaterial color="#67e8f9" transparent opacity={0.95} />
      </Ring>

      <Html position={[0, 0.05, 0]} center style={{ pointerEvents: 'none' }}>
        <div className="text-[7px] font-mono font-black text-cyan-300 tracking-wider select-none opacity-90 drop-shadow-[0_0_4px_rgba(6,182,212,0.8)]">
          DOCK
        </div>
      </Html>
    </group>
  );
});

/* =========================================================================
   TARGET BEACON COMPONENT (Temporary Glowing Pulsing Sphere & Rings)
   ========================================================================= */
const TargetBeacon = React.memo(({ x, y }) => {
  const beaconRef = useRef();
  const ring1Ref = useRef();
  const ring2Ref = useRef();
  const [wx, , wz] = gridToWorld(x, y);

  useFrame(({ clock }) => {
    const elapsed = clock.getElapsedTime();
    if (beaconRef.current) {
      beaconRef.current.position.y = 0.5 + Math.sin(elapsed * 5) * 0.15;
      beaconRef.current.rotation.y = elapsed * 3;
    }
    if (ring1Ref.current) {
      const scale = 1 + (Math.sin(elapsed * 4) + 1) * 0.35;
      ring1Ref.current.scale.set(scale, scale, 1);
    }
    if (ring2Ref.current) {
      const scale2 = 1 + (Math.cos(elapsed * 4) + 1) * 0.25;
      ring2Ref.current.scale.set(scale2, scale2, 1);
    }
  });

  return (
    <group position={[wx, 0, wz]}>
      {/* Pulsing ground rings */}
      <Ring
        ref={ring1Ref}
        args={[0.2, 0.44, 32]}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.025, 0]}
      >
        <meshBasicMaterial color="#f59e0b" transparent opacity={0.65} side={THREE.DoubleSide} />
      </Ring>
      <Ring
        ref={ring2Ref}
        args={[0.06, 0.16, 32]}
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.03, 0]}
      >
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.9} side={THREE.DoubleSide} />
      </Ring>

      {/* Vertical light beam */}
      <Cylinder args={[0.02, 0.06, 2.5, 16]} position={[0, 1.25, 0]}>
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.25} />
      </Cylinder>

      {/* Floating pulsing beacon sphere */}
      <group ref={beaconRef} position={[0, 0.5, 0]}>
        <Sphere args={[0.15, 16, 16]}>
          <meshStandardMaterial
            color="#fbbf24"
            emissive="#f59e0b"
            emissiveIntensity={3.5}
            toneMapped={false}
          />
        </Sphere>
      </group>

      <Html position={[0, 1.6, 0]} center style={{ pointerEvents: 'none' }}>
        <div className="bg-amber-950/90 text-amber-300 font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border border-amber-500/70 shadow-[0_0_12px_rgba(245,158,11,0.6)] whitespace-nowrap animate-pulse">
          TARGET ({x}, {y})
        </div>
      </Html>
    </group>
  );
});

/* =========================================================================
   AMR MESH COMPONENT (High-performance 60fps useFrame lerp via robotsRef)
   ========================================================================= */
const AmrMesh = React.memo(({ id, robotsRef }) => {
  const meshRef = useRef();
  const [visualState, setVisualState] = useState({
    status: 'ACTIVE',
    battery: 100,
  });
  const lastStateRef = useRef({ status: '', battery: 100 });

  useFrame((state, delta) => {
    const data = robotsRef.current[id];
    if (!data) return;

    // Construct the target vector
    const target = new THREE.Vector3(data.x - 10, 0.5, data.y - 10);
    if (meshRef.current) {
      // Interpolate smoothly
      meshRef.current.position.lerp(target, Math.min(1, delta * 10));
    }

    // Update visual state only when status or battery changes significantly
    const currentStatus = (data.status || 'ACTIVE').toUpperCase();
    const currentBattery = data.battery ?? 100;
    if (
      lastStateRef.current.status !== currentStatus ||
      Math.abs(lastStateRef.current.battery - currentBattery) >= 1
    ) {
      lastStateRef.current = { status: currentStatus, battery: currentBattery };
      setVisualState({ status: currentStatus, battery: currentBattery });
    }
  });

  const rawStatus = (visualState.status || "ACTIVE").toUpperCase();
  const isDead = rawStatus === "DEAD";
  const isBidding = rawStatus === "BIDDING";
  const isClaimed = rawStatus === "CLAIMED";
  const isDocked = rawStatus === "DOCKED" || rawStatus === "IDLE";
  const isYielding = rawStatus === "YIELDING";

  let meshColor = "#d97706";
  let emissiveColor = "#f59e0b";
  let emissiveIntensity = 2;
  let borderColor = "#f59e0b";
  let textColor = "#fde68a";
  let shadowGlow = "rgba(251, 191, 36, 0.8)";
  let displayStatus = rawStatus === "IDLE" ? "DOCKED" : rawStatus;

  if (isDead) {
    meshColor = "#ef4444";
    emissiveColor = "#ef4444";
    emissiveIntensity = 3.5;
    borderColor = "#ef4444";
    textColor = "#fca5a5";
    shadowGlow = "rgba(239, 68, 68, 1)";
  } else if (isBidding) {
    meshColor = "#0891b2";
    emissiveColor = "#06b6d4";
    emissiveIntensity = 3.2;
    borderColor = "#06b6d4";
    textColor = "#a5f3fc";
    shadowGlow = "rgba(6, 182, 212, 0.9)";
  } else if (isClaimed) {
    meshColor = "#ca8a04";
    emissiveColor = "#eab308";
    emissiveIntensity = 3.5;
    borderColor = "#eab308";
    textColor = "#fef08a";
    shadowGlow = "rgba(234, 179, 8, 1)";
  } else if (isDocked) {
    meshColor = "#0284c7";
    emissiveColor = "#38bdf8";
    emissiveIntensity = 1.8;
    borderColor = "#0284c7";
    textColor = "#bae6fd";
    shadowGlow = "rgba(56, 189, 248, 0.8)";
  } else if (isYielding) {
    meshColor = "#c2410c";
    emissiveColor = "#ea580c";
    emissiveIntensity = 2.2;
    borderColor = "#ea580c";
    textColor = "#fed7aa";
    shadowGlow = "rgba(234, 88, 12, 0.8)";
  }

  return (
    <group ref={meshRef} position={[0, 0.5, 0]}>
      <Box
        args={[0.7, 0.7, 0.7]}
        position={[0, 0.35, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial 
          color={meshColor} 
          emissive={emissiveColor} 
          emissiveIntensity={emissiveIntensity} 
          toneMapped={false}
        />
      </Box>

      {/* Red Hazard Point Light when DEAD directly above robot */}
      {isDead && (
        <pointLight
          position={[0, 1, 0]}
          intensity={5}
          distance={4}
          color="#ef4444"
        />
      )}

      {/* Top Tag */}
      <Html
        position={[0, 1.25, 0]}
        style={{
          pointerEvents: 'none',
          textAlign: 'center',
          fontSize: '11px',
          fontFamily: 'monospace',
          fontWeight: 'bold',
          color: textColor,
          textShadow: shadowGlow === 'none' ? 'none' : `0 0 10px ${shadowGlow}`,
        }}
      >
        <div style={{ background: isDead ? 'rgba(40,0,0,0.9)' : 'rgba(0,0,0,0.85)', padding: '2px 6px', borderRadius: '4px', border: `1px solid ${borderColor}`, display: 'inline-block' }}>
          <div>{id} <span style={{ fontSize: '9px', opacity: 0.9 }}>[{displayStatus}]</span></div>
          <div style={{ fontSize: '10px', opacity: 0.85 }}>{visualState.battery}%</div>
        </div>
      </Html>

      {/* Ground projection shadow/glow */}
      <Box
        args={[0.5, 0.02, 0.5]}
        position={[0, 0.01, 0]}
        castShadow
      >
        <meshBasicMaterial color={emissiveColor} transparent opacity={isDead ? 0.6 : 0.4} />
      </Box>
    </group>
  );
});

/* =========================================================================
   3D SCENE COMPONENT (Maps over robotIds and passes robotsRef)
   ========================================================================= */
const Scene = ({ robotIds, robotsRef, obstacles, chargingStations, targetBeacons, onFloorClick }) => {
  return (
    <>
      <ambientLight intensity={0.65} color="#fef3c7" />
      <directionalLight 
        position={[15, 25, 15]} 
        intensity={2.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.1}
        shadow-camera-far={60}
        shadow-camera-left={-20}
        shadow-camera-right={20}
        shadow-camera-top={20}
        shadow-camera-bottom={-20}
      />
      <directionalLight position={[-12, 15, -12]} intensity={0.6} color="#93c5fd" />
      
      {/* Grid Floor */}
      <gridHelper args={[GRID_SIZE, GRID_SIZE, '#475569', '#1e293b']} position={[0, 0, 0]} />
      
      {/* Raycast Clickable Floor Plane */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0, 0]}
        onPointerDown={onFloorClick}
      >
        <planeGeometry args={[GRID_SIZE, GRID_SIZE]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>

      {/* Charging Pads / Docks (Glowing Cyan) */}
      {chargingStations.map((station, idx) => (
        <ChargingPad key={`dock-${idx}-${station[0]}-${station[1]}`} x={station[0]} y={station[1]} />
      ))}

      {/* 3D Obstacle Racks (Tall 3D Boxes args={[0.9, 3, 0.9]}) */}
      {obstacles.map((obs, i) => (
        <WarehouseRack key={`obs-${i}-${obs[0]}-${obs[1]}`} x={obs[0]} y={obs[1]} />
      ))}

      {/* Active Target Beacons */}
      {targetBeacons.map((beacon) => (
        <TargetBeacon key={`beacon-${beacon.id}`} x={beacon.x} y={beacon.y} />
      ))}

      {/* AMR Units */}
      {robotIds.map((id) => (
        <AmrMesh
          key={id}
          id={id}
          robotsRef={robotsRef}
        />
      ))}
    </>
  );
};

/* =========================================================================
   DASHBOARD PANEL (Edge-AI UI, P2P Terminal, & Sabotage Controls)
   ========================================================================= */
const DashboardPanel = ({ 
  robotIds,
  robots, 
  time, 
  isConnected, 
  selectedAgent, 
  setSelectedAgent, 
  logs,
  onSabotage
}) => {

  const getBatteryColor = (level) => {
    if (level > 50) return 'bg-emerald-500';
    if (level > 20) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const getBatteryIcon = (level) => {
    if (level > 75) return <Battery className="w-4 h-4 text-emerald-500" />;
    if (level > 50) return <Battery className="w-4 h-4 text-emerald-400" />;
    if (level > 25) return <Battery className="w-4 h-4 text-amber-400" />;
    if (level > 10) return <Zap className="w-4 h-4 text-amber-500" />;
    return <Zap className="w-4 h-4 text-red-500 animate-pulse" />;
  };

  const getStatusBadge = (status) => {
    const s = (status || "ACTIVE").toUpperCase();
    if (s === "DEAD") {
      return (
        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-red-950/70 text-red-400 border border-red-700/60 rounded shadow-[0_0_8px_rgba(239,68,68,0.3)] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
          DEAD
        </span>
      );
    }
    if (s === "BIDDING") {
      return (
        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/70 rounded shadow-[0_0_8px_rgba(6,182,212,0.5)] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          BIDDING
        </span>
      );
    }
    if (s === "CLAIMED") {
      return (
        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-yellow-950/80 text-yellow-300 border border-yellow-500/70 rounded shadow-[0_0_8px_rgba(234,179,8,0.5)] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
          CLAIMED
        </span>
      );
    }
    if (s === "DOCKED" || s === "IDLE") {
      return (
        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-sky-950/70 text-sky-300 border border-sky-600/60 rounded shadow-[0_0_8px_rgba(14,165,233,0.3)] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
          DOCKED
        </span>
      );
    }
    if (s === "YIELDING") {
      return (
        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-950/70 text-amber-400 border border-amber-600/60 rounded shadow-[0_0_8px_rgba(245,158,11,0.3)] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" />
          YIELDING
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 text-[9px] font-bold bg-emerald-950/70 text-emerald-400 border border-emerald-600/60 rounded shadow-[0_0_8px_rgba(16,185,129,0.3)] flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        ACTIVE
      </span>
    );
  };

  const sortedRobotIds = [...robotIds].sort();

  // Swarm Status Metrics
  const biddingCount = sortedRobotIds.filter(id => (robots[id]?.status || "").toUpperCase() === "BIDDING").length;
  const claimedCount = sortedRobotIds.filter(id => (robots[id]?.status || "").toUpperCase() === "CLAIMED").length;
  const dockedCount = sortedRobotIds.filter(id => {
    const s = (robots[id]?.status || "").toUpperCase();
    return s === "DOCKED" || s === "IDLE";
  }).length;

  return (
    <motion.div
      className="w-1/4 h-full flex flex-col p-4 bg-neutral-900 border-l border-yellow-700/30 overflow-hidden"
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', damping: 20, stiffness: 100, delay: 0.2 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3 border-b border-yellow-700/20 pb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-yellow-700/20 rounded-lg border border-yellow-700/30">
            <Radio className="w-4 h-4 text-yellow-500" />
          </div>
          <div>
            <motion.h1
              className="text-base font-bold tracking-tight text-yellow-300"
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              EDGE-AI FLEET
            </motion.h1>
            <p className="text-[9px] text-yellow-600 uppercase tracking-widest">DECENTRALIZED SWARM</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-neutral-800 px-2 py-1 rounded-lg border border-yellow-700/30">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-[10px] font-medium ${isConnected ? 'text-yellow-400' : 'text-red-500'}`}>
              {isConnected ? 'MESH ON' : 'DOWN'}
            </span>
          </div>
          <div className="flex items-center gap-1 bg-neutral-800 px-2 py-1 rounded-lg border border-yellow-700/30">
            <Clock className="w-3 h-3 text-yellow-600" />
            <span className="text-sm font-mono tabular-nums text-yellow-400">T+{String(time).padStart(3, '0')}</span>
          </div>
        </div>
      </div>

      {/* Commander Controls */}
      <div className="mb-3 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-2.5 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Target className="w-3.5 h-3.5 text-yellow-500" />
            <h3 className="font-semibold text-yellow-300 text-xs">DISPATCH SELECTOR</h3>
          </div>
          <span className="text-[9px] text-neutral-400">CLICK FLOOR TO DEPLOY</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {sortedRobotIds.map((agent) => {
            const agentStatus = (robots[agent]?.status || "ACTIVE").toUpperCase();
            return (
              <motion.button
                key={agent}
                onClick={() => setSelectedAgent(agent)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className={`px-2 py-1 rounded font-medium text-[10px] uppercase tracking-wide transition-all text-neutral-300 flex items-center justify-between ${
                  selectedAgent === agent
                    ? 'bg-yellow-600/25 border border-yellow-500 text-yellow-300 shadow-[0_0_10px_rgba(234,179,8,0.3)]'
                    : 'bg-neutral-900 border border-neutral-700 hover:border-yellow-700/50 hover:bg-neutral-800'
                }`}
              >
                <span>{agent}</span>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  agentStatus === "BIDDING" ? 'bg-cyan-400' :
                  agentStatus === "CLAIMED" ? 'bg-yellow-400' :
                  agentStatus === "DOCKED" || agentStatus === "IDLE" ? 'bg-sky-400' :
                  agentStatus === "DEAD" ? 'bg-red-500' :
                  agentStatus === "YIELDING" ? 'bg-orange-500' : 'bg-emerald-400'
                }`} />
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Auction & Swarm Status Summary */}
      <div className="mb-3 grid grid-cols-4 gap-1.5 flex-shrink-0">
        <div className="bg-neutral-800/40 border border-neutral-700/50 rounded-lg p-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-[8px] text-neutral-400 uppercase">
            <Activity className="w-2.5 h-2.5 text-yellow-500" />
            <span>FLEET</span>
          </div>
          <div className="text-sm font-bold text-yellow-400">{sortedRobotIds.length}</div>
        </div>
        <div className="bg-cyan-950/30 border border-cyan-700/40 rounded-lg p-1.5 text-center">
          <div className="text-[8px] text-cyan-400 uppercase">BIDDING</div>
          <div className="text-sm font-bold text-cyan-300">{biddingCount}</div>
        </div>
        <div className="bg-yellow-950/30 border border-yellow-700/40 rounded-lg p-1.5 text-center">
          <div className="text-[8px] text-yellow-400 uppercase">CLAIMED</div>
          <div className="text-sm font-bold text-yellow-300">{claimedCount}</div>
        </div>
        <div className="bg-sky-950/30 border border-sky-700/40 rounded-lg p-1.5 text-center">
          <div className="text-[8px] text-sky-400 uppercase">DOCKED</div>
          <div className="text-sm font-bold text-sky-300">{dockedCount}</div>
        </div>
      </div>

      {/* Live Telemetry with Red Sabotage/Kill Trigger */}
      <div className="mb-3 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-2.5 flex-shrink-0">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-yellow-500" />
            <h3 className="font-semibold text-yellow-300 text-xs">SWARM TELEMETRY</h3>
          </div>
          <span className="text-[9px] text-yellow-600">SABOTAGE CONTROLS</span>
        </div>
        <div className="space-y-1.5 max-h-[150px] overflow-y-auto custom-scrollbar pr-1">
          {sortedRobotIds.map((id) => {
            const pos = robots[id] || {};
            const displayStatus = (pos.status === "IDLE" || !pos.status) ? "DOCKED" : pos.status;
            const isDead = pos.status === "DEAD";

            return (
              <div key={id} className={`bg-neutral-900 rounded border p-2 transition-all ${isDead ? 'border-red-800/60 bg-red-950/20' : 'border-neutral-700/80'}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`font-bold text-xs ${isDead ? 'text-red-400 line-through' : 'text-yellow-400'}`}>{id}</span>
                    <span className="text-[9px] text-neutral-400">({pos.x ?? 0}, {pos.y ?? 0})</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {getStatusBadge(displayStatus)}
                    {/* Small High-Contrast Red Sabotage / Kill Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSabotage(id);
                      }}
                      disabled={isDead}
                      title={`Sabotage / Kill ${id}`}
                      className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold flex items-center gap-1 transition-all ${
                        isDead
                          ? 'bg-neutral-800 text-neutral-600 border border-neutral-700 cursor-not-allowed opacity-50'
                          : 'bg-red-600 hover:bg-red-500 text-white border border-red-400 shadow-[0_0_8px_rgba(239,68,68,0.7)] active:scale-95 cursor-pointer'
                      }`}
                    >
                      <Skull className="w-2.5 h-2.5" />
                      <span>KILL</span>
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="flex-shrink-0">{getBatteryIcon(pos.battery ?? 100)}</div>
                  <div className="flex-1 h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${getBatteryColor(pos.battery ?? 100)}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${pos.battery ?? 100}%` }}
                      transition={{ type: 'spring', damping: 20, stiffness: 100 }}
                    />
                  </div>
                  <span className={`font-mono text-[9px] w-7 text-right ${(pos.battery ?? 100) > 50 ? 'text-emerald-400' : (pos.battery ?? 100) > 20 ? 'text-amber-400' : 'text-red-400'}`}>
                    {pos.battery ?? 100}%
                  </span>
                  <span className="text-[9px] text-neutral-400 font-mono">PRI:{pos.priority ?? 1}</span>
                </div>
              </div>
            );
          })}
          {sortedRobotIds.length === 0 && (
            <div className="text-yellow-600 text-[10px] italic text-center py-2">NO TELEMETRY RECEIVED</div>
          )}
        </div>
      </div>

      {/* P2P Terminal (Auction & Consensus Feed) */}
      <div className="flex-1 min-h-0 flex flex-col bg-black p-2.5 border border-yellow-700/50 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-yellow-500" />
            <h3 className="font-semibold text-yellow-300 text-xs">P2P AUCTION TERMINAL</h3>
          </div>
          <span className="text-[8px] bg-yellow-700/20 text-yellow-400 px-1.5 py-0.5 rounded border border-yellow-700/40">
            DECENTRALIZED
          </span>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 pr-1 font-mono text-[10px]">
          {logs.length === 0 ? (
            <div className="text-neutral-500 italic text-center py-4">AWAITING TASK DISPATCH & P2P AUCTION EVENTS...</div>
          ) : (
            <AnimatePresence initial={false}>
              {logs.map((log) => {
                if (typeof log === 'object' && log !== null) {
                  const isBid = log.status === 'BIDDING' || log.type === 'AUCTION_BID';
                  const isClaim = log.status === 'CLAIMED' || log.type === 'AUCTION_WIN';
                  const isYield = log.status === 'YIELDING' || log.type === 'COLLISION_AVOID';
                  const isDead = log.status === 'DEAD' || log.type === 'FAILURE';
                  const isDispatch = log.type === 'DISPATCH';

                  let containerStyle = 'bg-neutral-900 border-neutral-700 text-neutral-300';
                  let tagStyle = 'bg-neutral-800 text-neutral-400 border-neutral-600';
                  let tagText = log.status || log.type || 'INFO';

                  if (isBid) {
                    containerStyle = 'bg-cyan-950/50 border-cyan-500/60 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.2)]';
                    tagStyle = 'bg-cyan-500/20 text-cyan-300 border-cyan-400/50';
                    tagText = 'BIDDING';
                  } else if (isClaim) {
                    containerStyle = 'bg-yellow-950/50 border-yellow-500/60 text-yellow-200 shadow-[0_0_10px_rgba(234,179,8,0.2)]';
                    tagStyle = 'bg-yellow-500/20 text-yellow-300 border-yellow-400/50';
                    tagText = 'CLAIMED';
                  } else if (isYield) {
                    containerStyle = 'bg-amber-950/40 border-amber-600/50 text-amber-200';
                    tagStyle = 'bg-amber-500/20 text-amber-300 border-amber-500/50';
                    tagText = 'YIELD';
                  } else if (isDead) {
                    containerStyle = 'bg-red-950/50 border-red-600/60 text-red-200 shadow-[0_0_10px_rgba(239,68,68,0.2)]';
                    tagStyle = 'bg-red-500/20 text-red-300 border-red-500/50';
                    tagText = 'FAILURE';
                  } else if (isDispatch) {
                    containerStyle = 'bg-purple-950/40 border-purple-500/50 text-purple-200';
                    tagStyle = 'bg-purple-500/20 text-purple-300 border-purple-400/50';
                    tagText = 'DISPATCH';
                  }

                  return (
                    <motion.div
                      key={log.id}
                      initial={{ opacity: 0, y: -6, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      transition={{ duration: 0.2 }}
                      className={`p-1.5 rounded border text-[9.5px] leading-tight ${containerStyle}`}
                    >
                      <div className="flex items-center justify-between mb-0.5 text-[8px] opacity-90 font-bold">
                        <span>[T+{log.time ?? time}] {log.agentId ? `AGENT ${log.agentId}` : 'SWARM_EVENT'}</span>
                        <span className={`px-1 py-0.2 rounded border font-mono ${tagStyle}`}>
                          {tagText}
                        </span>
                      </div>
                      <div className="font-mono">{log.message}</div>
                    </motion.div>
                  );
                }

                // Fallback string logs
                const isBidString = String(log).includes('BID') || String(log).includes('BIDDING');
                const isClaimString = String(log).includes('CLAIM') || String(log).includes('CLAIMED');
                const isDeadString = String(log).includes('DEAD') || String(log).includes('FAILURE') || String(log).includes('SABOTAGE');
                
                return (
                  <motion.div
                    key={String(log)}
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`p-1 rounded font-mono text-[9.5px] ${
                      isDeadString ? 'text-red-300 bg-red-950/30 border border-red-800/40' :
                      isBidString ? 'text-cyan-300 bg-cyan-950/30 border border-cyan-800/40' :
                      isClaimString ? 'text-yellow-300 bg-yellow-950/30 border border-yellow-800/40' :
                      'text-yellow-100/80'
                    }`}
                  >
                    {log}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>
      </div>
    </motion.div>
  );
};

/* =========================================================================
   MAIN APP COMPONENT (WebSocket Singleton & Render Decoupling)
   ========================================================================= */
export default function App() {
  const wsRef = useRef(null);
  const robotsRef = useRef({});
  const [robotIds, setRobotIds] = useState([]);
  const [telemetryRobots, setTelemetryRobots] = useState({});
  const [time, setTime] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('AMR-1');
  const [obstacles, setObstacles] = useState([]);
  const [chargingStations, setChargingStations] = useState(DEFAULT_CHARGING_STATIONS);
  const [logs, setLogs] = useState([]);
  const [targetBeacons, setTargetBeacons] = useState([]);
  
  const prevRobotPositions = useRef({});
  const activeYields = useRef(new Set());

  // Fetch initial config from backend
  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then(res => res.json())
      .then(data => {
        if (data.obstacles) {
          setObstacles(data.obstacles);
        }
        if (data.warehouse?.charging_stations) {
          setChargingStations(data.warehouse.charging_stations);
        } else if (data.charging_stations) {
          setChargingStations(data.charging_stations);
        }
      })
      .catch(err => console.error('Failed to fetch config:', err));
  }, []);

  // Clean expired target beacons
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setTargetBeacons(prev => prev.filter(b => now - b.id < 6000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Sabotage / Kill handler
  const handleSabotage = async (agentId) => {
    try {
      await fetch(`http://localhost:8000/api/sabotage/${agentId}`, { method: 'POST' });
      if (robotsRef.current[agentId]) {
        robotsRef.current[agentId].status = 'DEAD';
      }
      setTelemetryRobots({ ...robotsRef.current });
      setLogs(prev => [{
        id: `${Date.now()}-${agentId}-sabotage`,
        time: robotsRef.current[agentId]?.time ?? 0,
        agentId: agentId,
        status: "DEAD",
        type: "FAILURE",
        message: `[SABOTAGE] ⚠️ Manual override: ${agentId} neutralized -> Dynamic obstacle active on grid`,
        color: "red"
      }, ...prev].slice(0, 25));
    } catch (err) {
      console.error(`Failed to sabotage ${agentId}:`, err);
    }
  };

  // WebSocket Singleton isolated from React render cycle
  useEffect(() => {
    if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
      wsRef.current = new WebSocket(WS_URL);
    }
    const ws = wsRef.current;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const simTime = data.time ?? 0;
        if (data.time !== undefined) {
          setTime(data.time);
          setTelemetryRobots({ ...robotsRef.current });
        }

        if (data.agent_id && data.x !== undefined && data.y !== undefined) {
          const prev = prevRobotPositions.current[data.agent_id];
          const prevStatus = prev?.status;
          
          let status = data.status ?? "ACTIVE";
          if (status === "IDLE") {
            status = "DOCKED";
          }

          // Update the ref directly without calling state setter for position
          robotsRef.current[data.agent_id] = {
            ...prev,
            ...data,
            status,
            battery: data.battery ?? prev?.battery ?? 100,
            priority: data.priority ?? prev?.priority ?? 1,
          };

          // Prevent Array Thrashing: Update setRobotIds only if ID is genuinely missing
          setRobotIds(prev => (prev.includes(data.agent_id) ? prev : [...prev, data.agent_id]));

          // Throttle P2P feed logs: Only append to setLogs if data.status !== "MOVING" and data.status !== "IDLE"
          const rawStatus = (data.status || "").toUpperCase();
          if (rawStatus !== "MOVING" && rawStatus !== "IDLE" && status !== prevStatus) {
            if (status === "BIDDING") {
              setLogs(prevLogs => [{
                id: `${simTime}-${data.agent_id}-bid-${Date.now()}`,
                time: simTime,
                agentId: data.agent_id,
                status: "BIDDING",
                type: "AUCTION_BID",
                message: `[${data.agent_id}] ⚡ BROADCAST BID: Estimating dynamic time-space cost (Priority ${data.priority ?? 1})`,
                color: "cyan"
              }, ...prevLogs].slice(0, 25));
            } else if (status === "CLAIMED") {
              setLogs(prevLogs => [{
                id: `${simTime}-${data.agent_id}-claim-${Date.now()}`,
                time: simTime,
                agentId: data.agent_id,
                status: "CLAIMED",
                type: "AUCTION_WIN",
                message: `[${data.agent_id}] 🏆 AUCTION WON: Task claimed & committed to decentralized P2P intent mesh`,
                color: "gold"
              }, ...prevLogs].slice(0, 25));
            } else if (status === "YIELDING" && !activeYields.current.has(data.agent_id)) {
              activeYields.current.add(data.agent_id);
              setLogs(prevLogs => [{
                id: `${simTime}-${data.agent_id}-yield-${Date.now()}`,
                time: simTime,
                agentId: data.agent_id,
                status: "YIELDING",
                type: "COLLISION_AVOID",
                message: `[${data.agent_id}] (Pri ${data.priority ?? 1}) Yielding right-of-way to higher-priority node`,
                color: "orange"
              }, ...prevLogs].slice(0, 25));
            } else if (status === "DEAD") {
              setLogs(prevLogs => [{
                id: `${simTime}-${data.agent_id}-dead-${Date.now()}`,
                time: simTime,
                agentId: data.agent_id,
                status: "DEAD",
                type: "FAILURE",
                message: `[${data.agent_id}] ⚠️ CRITICAL FAILURE: Node offline - treating position (${data.x}, ${data.y}) as dynamic obstacle`,
                color: "red"
              }, ...prevLogs].slice(0, 25));
            } else if (status === "DOCKED" && prevStatus && prevStatus !== "DOCKED") {
              setLogs(prevLogs => [{
                id: `${simTime}-${data.agent_id}-dock-${Date.now()}`,
                time: simTime,
                agentId: data.agent_id,
                status: "DOCKED",
                type: "DOCKING",
                message: `[${data.agent_id}] 🔌 DOCKED at charging pad (${data.x}, ${data.y})`,
                color: "sky"
              }, ...prevLogs].slice(0, 25));
            }
          }

          if (status !== "YIELDING" && activeYields.current.has(data.agent_id)) {
            activeYields.current.delete(data.agent_id);
          }
          
          prevRobotPositions.current[data.agent_id] = { x: data.x, y: data.y, time: simTime, status };
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
    };
  }, []);

  // Raycasting Click-to-Deploy on floor plane
  const handleFloorClick = async (event) => {
    if (event.stopPropagation) {
      event.stopPropagation();
    }
    
    // Extract intersected X, Z coordinates and round to nearest grid cell
    const rawX = event.point.x;
    const rawZ = event.point.z;
    const gx = Math.floor(rawX + GRID_HALF);
    const gy = Math.floor(rawZ + GRID_HALF);
    const clampedX = Math.max(0, Math.min(GRID_SIZE - 1, gx));
    const clampedY = Math.max(0, Math.min(GRID_SIZE - 1, gy));

    const isObstacle = obstacles.some(obs => obs[0] === clampedX && obs[1] === clampedY);
    if (isObstacle) {
      return;
    }

    // Add temporary glowing Target Beacon at the clicked coordinate
    const beaconId = Date.now();
    setTargetBeacons(prev => [...prev.filter(b => Date.now() - b.id < 5000), { x: clampedX, y: clampedY, id: beaconId }]);

    // Log user dispatch event in P2P Terminal
    setLogs(prev => [{
      id: `${beaconId}-dispatch`,
      time: time,
      agentId: selectedAgent,
      status: "DISPATCH",
      type: "DISPATCH",
      message: `[OPERATOR] Dispatched task target @ (${clampedX}, ${clampedY}) -> Initializing decentralized auction`,
      color: "purple"
    }, ...prev].slice(0, 25));

    // Execute axios.post to /api/tasks and dispatch
    try {
      await axios.post('http://localhost:8000/api/tasks', { x: clampedX, y: clampedY });
    } catch (err) {
      console.log("axios.post to /api/tasks completed:", err.message);
    }

    // Also trigger agent dispatch
    try {
      await fetch(`${API_URL}/api/dispatch/${selectedAgent}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x: clampedX, y: clampedY })
      });
      if (robotsRef.current[selectedAgent]) {
        robotsRef.current[selectedAgent].target_x = clampedX;
        robotsRef.current[selectedAgent].target_y = clampedY;
      }
    } catch (dispatchErr) {
      console.error("Dispatch call error:", dispatchErr);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-neutral-950 text-amber-50 flex">
      <div className="w-3/4 h-full relative">
        <Canvas
          camera={{ position: [0, 24, 28], fov: 48 }}
          shadows
          style={{ touchAction: 'none' }}
        >
          <color attach="background" args={['#030712']} />
          <Scene 
            robotIds={robotIds} 
            robotsRef={robotsRef} 
            obstacles={obstacles} 
            chargingStations={chargingStations}
            targetBeacons={targetBeacons}
            onFloorClick={handleFloorClick} 
          />
          <EffectComposer disableNormalPass>
            <Bloom luminanceThreshold={0.9} mipmapBlur intensity={1.6} />
          </EffectComposer>
          <OrbitControls 
            makeDefault 
            target={[0, 0, 0]}
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            minPolarAngle={0}
            maxPolarAngle={Math.PI / 2 - 0.05}
            minZoom={5}
            maxZoom={60}
          />
        </Canvas>
        
        {/* Grid Legend Overlay */}
        <div className="absolute bottom-4 left-4 right-4 flex flex-wrap justify-center gap-3 text-[11px] text-neutral-300 pointer-events-none">
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <span className="font-mono">CHARGING DOCK</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-slate-600 border border-slate-400" />
            <span className="font-mono">3D RACK (OBSTACLE)</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-cyan-400 shadow-[0_0_6px_rgba(6,182,212,0.9)]" />
            <span className="font-mono">BIDDING</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-yellow-400 shadow-[0_0_6px_rgba(234,179,8,0.9)]" />
            <span className="font-mono">CLAIMED</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.9)] animate-pulse" />
            <span className="font-mono">DEAD (HAZARD)</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/90 px-2.5 py-1 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2.5 h-2.5 rounded bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)] animate-pulse" />
            <span className="font-mono">TARGET BEACON</span>
          </div>
        </div>

        {/* Camera Hint */}
        <div className="absolute top-4 left-4 text-[11px] font-mono text-neutral-400 bg-neutral-900/85 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur shadow-lg flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Click floor to deploy • Drag to rotate • Scroll to zoom</span>
        </div>
      </div>

      <DashboardPanel
        robotIds={robotIds}
        robots={telemetryRobots}
        time={time}
        isConnected={isConnected}
        selectedAgent={selectedAgent}
        setSelectedAgent={setSelectedAgent}
        logs={logs}
        onSabotage={handleSabotage}
      />
    </div>
  );
}