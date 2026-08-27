import React, { useState, useEffect, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Box, Text, Plane, Ring, Sphere, Cylinder, Billboard } from '@react-three/drei';
import * as THREE from 'three';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Cpu, Battery, Zap, Target, Terminal, Radio, Skull } from 'lucide-react';

const originalWarn = console.warn;
console.warn = (...args) => {
  if (typeof args[0] === 'string' && args[0].includes('has been deprecated')) return;
  originalWarn(...args);
};

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';
const GRID_SIZE = 30;
const GRID_HALF = GRID_SIZE / 2;

const DEFAULT_CHARGING_STATIONS = [
  [2, 0], [7, 0], [12, 0], [17, 0], [22, 0], [27, 0]
];

function gridToWorld(x, y) {
  return [x - GRID_HALF + 0.5, 0.5, y - GRID_HALF + 0.5];
}

const WarehouseRack = React.memo(({ x, y }) => {
  const [wx, , wz] = gridToWorld(x, y);
  return (
    <group position={[wx, 1.5, wz]}>
      <Box args={[0.9, 3, 0.9]}>
        <meshStandardMaterial color="#334155" metalness={0.65} roughness={0.35} />
      </Box>
      <Box args={[0.92, 0.04, 0.92]} position={[0, -0.75, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>
      <Box args={[0.92, 0.04, 0.92]} position={[0, 0, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>
      <Box args={[0.92, 0.04, 0.92]} position={[0, 0.75, 0]}>
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
      </Box>
      <Box args={[0.04, 3.02, 0.92]} position={[-0.44, 0, 0]}>
        <meshStandardMaterial color="#475569" metalness={0.9} roughness={0.2} />
      </Box>
      <Box args={[0.04, 3.02, 0.92]} position={[0.44, 0, 0]}>
        <meshStandardMaterial color="#475569" metalness={0.9} roughness={0.2} />
      </Box>
    </group>
  );
});

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
    <group position={[wx, 0, wz - 1]}>
      <Plane args={[0.85, 0.85]} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <meshStandardMaterial color="#06b6d4" emissive="#22d3ee" emissiveIntensity={2.5} toneMapped={false} transparent opacity={0.85} />
      </Plane>
      <Ring ref={ringRef} args={[0.36, 0.42, 4]} rotation={[-Math.PI / 2, 0, Math.PI / 4]} position={[0, 0.015, 0]}>
        <meshBasicMaterial color="#00ffff" transparent opacity={0.8} />
      </Ring>
      <Ring args={[0.08, 0.16, 16]} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <meshBasicMaterial color="#67e8f9" transparent opacity={0.95} />
      </Ring>
      <Billboard position={[0, 0.8, 0]}>
        <Text fontSize={0.4} color="#67e8f9" outlineWidth={0.02} outlineColor="#083344" anchorX="center" anchorY="middle">
          DOCK
        </Text>
      </Billboard>
    </group>
  );
});

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
      <Ring ref={ring1Ref} args={[0.2, 0.44, 32]} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0]}>
        <meshBasicMaterial color="#f59e0b" transparent opacity={0.65} side={THREE.DoubleSide} />
      </Ring>
      <Ring ref={ring2Ref} args={[0.06, 0.16, 32]} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.9} side={THREE.DoubleSide} />
      </Ring>
      <Cylinder args={[0.02, 0.06, 2.5, 16]} position={[0, 1.25, 0]}>
        <meshBasicMaterial color="#fbbf24" transparent opacity={0.25} />
      </Cylinder>
      <group ref={beaconRef} position={[0, 0.5, 0]}>
        <Sphere args={[0.15, 16, 16]}>
          <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={3.5} toneMapped={false} />
        </Sphere>
      </group>
      <Billboard position={[0, 2.5, 0]}>
        <Text fontSize={0.5} color="#fde68a" outlineWidth={0.03} outlineColor="#451a03" anchorX="center" anchorY="middle">
          {`TARGET (${x}, ${y})`}
        </Text>
      </Billboard>
    </group>
  );
});

const AmrMesh = React.memo(({ id, robotsRef }) => {
  const meshRef = useRef();
  const [visualState, setVisualState] = useState({ status: 'ACTIVE', battery: 100 });
  const lastStateRef = useRef({ status: '', battery: 100 });

  useEffect(() => {
    const data = robotsRef.current[id];
    if (meshRef.current && data) {
      const [wx, wy, wz] = gridToWorld(data.x, data.y);
      meshRef.current.position.set(wx, wy, wz);
    }
  }, [id, robotsRef]);

  useFrame((state, delta) => {
    const data = robotsRef.current[id];
    if (!data || !meshRef.current) return;

    const [wx, wy, wz] = gridToWorld(data.x, data.y);
    const target = new THREE.Vector3(wx, wy, wz);
    meshRef.current.position.lerp(target, delta * 6);

    if (meshRef.current.position.distanceTo(target) > 0.01) {
      meshRef.current.lookAt(target.x, meshRef.current.position.y, target.z);
    }

    const currentStatus = (data.status || 'ACTIVE').toUpperCase();
    const currentBattery = data.battery ?? 100;
    if (lastStateRef.current.status !== currentStatus || Math.abs(lastStateRef.current.battery - currentBattery) >= 1) {
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

  let emissiveColor = "#f59e0b";
  let textColor = "#fde68a";
  let displayStatus = rawStatus === "IDLE" ? "DOCKED" : rawStatus;

  if (isDead) {
    emissiveColor = "#ef4444"; textColor = "#fca5a5";
  } else if (isBidding) {
    emissiveColor = "#06b6d4"; textColor = "#a5f3fc";
  } else if (isClaimed) {
    emissiveColor = "#eab308"; textColor = "#fef08a";
  } else if (isDocked) {
    emissiveColor = "#38bdf8"; textColor = "#bae6fd";
  } else if (isYielding) {
    emissiveColor = "#ea580c"; textColor = "#fed7aa";
  }

  return (
    <group ref={meshRef}>
      <group position={[0, 0.15, 0]}>
        {/* Main Chassis */}
        <Cylinder args={[0.45, 0.45, 0.3, 32]}>
          <meshStandardMaterial color="#222222" metalness={0.8} roughness={0.2} />
        </Cylinder>
        {/* Top LiDAR/Sensor Hub */}
        <Cylinder args={[0.2, 0.2, 0.15, 16]} position={[0, 0.2, 0]}>
          <meshStandardMaterial color="#111111" metalness={0.9} roughness={0.1} />
        </Cylinder>
        {/* Glowing Status LED Strip */}
        <Cylinder args={[0.46, 0.46, 0.05, 32]} position={[0, 0, 0]}>
          <meshBasicMaterial color={emissiveColor} transparent opacity={0.9} />
        </Cylinder>
      </group>
      {isDead && <pointLight position={[0, 1, 0]} intensity={5} distance={4} color="#ef4444" />}
      <Billboard position={[0, 1.2, 0]}>
        {isBidding && (
          <Text position={[0, 0.6, 0]} fontSize={0.25} color="#22d3ee" anchorX="center" anchorY="middle" outlineWidth={0.02} outlineColor="#083344">
            [AI: CALCULATING TRAFFIC COST]
          </Text>
        )}
        {isClaimed && (
          <Text position={[0, 0.6, 0]} fontSize={0.25} color="#fde047" anchorX="center" anchorY="middle" outlineWidth={0.02} outlineColor="#451a03">
            [AI: CONTRACT WON]
          </Text>
        )}
        {isYielding && (
          <Text position={[0, 0.6, 0]} fontSize={0.25} color="#fb923c" anchorX="center" anchorY="middle" outlineWidth={0.02} outlineColor="#431407">
            [AI: PROXIMITY YIELD]
          </Text>
        )}
        <Text fontSize={0.4} color={textColor} anchorX="center" anchorY="middle" outlineWidth={0.02} outlineColor="#000000">
          {`${id} [${displayStatus}]\n${visualState.battery}%`}
        </Text>
      </Billboard>
      {/* 0-GPU Blob Shadow */}
      <Plane args={[0.55, 0.55]} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.14, 0]}>
        <meshBasicMaterial color="#000000" transparent opacity={0.65} depthWrite={false} />
      </Plane>
    </group>
  );
});

const Scene = ({ robotIds, robotsRef, obstacles, chargingStations, targetBeacons, onFloorClick }) => {
  return (
    <>
      <ambientLight intensity={0.65} color="#fef3c7" />
      <directionalLight position={[15, 25, 15]} intensity={2.2} />
      <directionalLight position={[-12, 15, -12]} intensity={0.6} color="#93c5fd" />
      <gridHelper args={[GRID_SIZE, GRID_SIZE, '#475569', '#1e293b']} position={[0, 0, 0]} />
      
      {/* Industrial Transport Floors / Corridors */}
      <group position={[0, 0.005, 0]}>
        {[
          { x: -13, width: 3.8 },
          { x: -7,  width: 3.8 },
          { x: -1,  width: 3.8 },
          { x: 5,   width: 3.8 },
          { x: 12,  width: 5.8 }
        ].map((aisle, i) => (
          <Plane key={`v-aisle-${i}`} args={[aisle.width, 29.8]} position={[aisle.x, 0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <meshStandardMaterial 
              color="#0f2938" 
              emissive="#083344" 
              emissiveIntensity={0.6} 
              transparent 
              opacity={0.55} 
              roughness={0.4} 
              metalness={0.6} 
            />
          </Plane>
        ))}

        <Plane args={[29.8, 5.8]} position={[0, 0.001, -12]} rotation={[-Math.PI / 2, 0, 0]}>
          <meshStandardMaterial 
            color="#062e24" 
            emissive="#064e3b" 
            emissiveIntensity={0.5} 
            transparent 
            opacity={0.5} 
            roughness={0.4} 
            metalness={0.5} 
          />
        </Plane>
        <Plane args={[29.8, 4.8]} position={[0, 0.001, 12.5]} rotation={[-Math.PI / 2, 0, 0]}>
          <meshStandardMaterial 
            color="#062e24" 
            emissive="#064e3b" 
            emissiveIntensity={0.5} 
            transparent 
            opacity={0.5} 
            roughness={0.4} 
            metalness={0.5} 
          />
        </Plane>
      </group>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} onPointerDown={onFloorClick}>
        <planeGeometry args={[GRID_SIZE, GRID_SIZE]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
      {chargingStations.map((station, idx) => (
        <ChargingPad key={`dock-${idx}-${station[0]}-${station[1]}`} x={station[0]} y={station[1]} />
      ))}
      {obstacles.map((obs, i) => (
        <WarehouseRack key={`obs-${i}-${obs[0]}-${obs[1]}`} x={obs[0]} y={obs[1]} />
      ))}
      {targetBeacons.map((beacon) => (
        <TargetBeacon key={`beacon-${beacon.id}`} x={beacon.x} y={beacon.y} />
      ))}
      {robotIds.map((id) => (
        <AmrMesh key={id} id={id} robotsRef={robotsRef} />
      ))}
    </>
  );
};

const SimulationCanvas = React.memo(({ robotIds, robotsRef, obstacles, chargingStations, targetBeacons, onFloorClick }) => {
  return (
    <div className="w-3/4 h-full relative">
      <Canvas camera={{ position: [0, 24, 28], fov: 48 }} style={{ touchAction: 'none' }}>
        <color attach="background" args={['#120d0b']} />
        <fog attach="fog" args={['#120d0b', 15, 45]} />
        <Scene robotIds={robotIds} robotsRef={robotsRef} obstacles={obstacles} chargingStations={chargingStations} targetBeacons={targetBeacons} onFloorClick={onFloorClick} />
        <OrbitControls makeDefault target={[0, 0, 0]} enablePan={true} enableZoom={true} enableRotate={true} minPolarAngle={0} maxPolarAngle={Math.PI / 2 - 0.05} minZoom={5} maxZoom={60} />
      </Canvas>
      <div className="absolute top-4 left-4 text-[11px] font-mono text-[#f5f5dc] bg-[#1a1311]/90 px-3 py-1.5 rounded border border-[#d4af37]/30 backdrop-blur shadow-lg flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-[#d4af37] animate-pulse" />
        <span>Click floor to deploy • Drag to rotate • Scroll to zoom</span>
      </div>
    </div>
  );
});

const DashboardPanel = ({ robotIds, robots, time, isConnected, selectedAgent, setSelectedAgent, logs, onSabotage }) => {
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
    if (s === "DEAD") return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-red-950/70 text-red-400 border border-red-700/60 rounded shadow-[0_0_8px_rgba(239,68,68,0.3)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />DEAD</span>);
    if (s === "BIDDING") return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/70 rounded shadow-[0_0_8px_rgba(6,182,212,0.5)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />BIDDING</span>);
    if (s === "CLAIMED") return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-yellow-950/80 text-yellow-300 border border-yellow-500/70 rounded shadow-[0_0_8px_rgba(234,179,8,0.5)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />CLAIMED</span>);
    if (s === "DOCKED" || s === "IDLE") return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-sky-950/70 text-sky-300 border border-sky-600/60 rounded shadow-[0_0_8px_rgba(14,165,233,0.3)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-sky-400" />DOCKED</span>);
    if (s === "YIELDING") return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-950/70 text-amber-400 border border-amber-600/60 rounded shadow-[0_0_8px_rgba(245,158,11,0.3)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" />YIELDING</span>);
    return (<span className="px-1.5 py-0.5 text-[9px] font-bold bg-emerald-950/70 text-emerald-400 border border-emerald-600/60 rounded shadow-[0_0_8px_rgba(16,185,129,0.3)] flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />ACTIVE</span>);
  };

  const sortedRobotIds = [...robotIds].sort();

  return (
    <motion.div className="w-1/4 h-full flex flex-col p-4 bg-[#1a1311] border-l border-[#d4af37]/30 overflow-hidden" initial={{ x: '100%', opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ type: 'spring', damping: 20, stiffness: 100, delay: 0.2 }}>
      <div className="flex items-center justify-between mb-3 border-b border-[#d4af37]/20 pb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-[#1f1614] rounded-lg border border-[#d4af37]/30"><Radio className="w-4 h-4 text-[#d4af37]" /></div>
          <div><motion.h1 className="text-base font-bold tracking-tight text-[#d4af37]" initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>EDGE-AI FLEET</motion.h1><p className="text-[9px] text-[#f5f5dc]/70 uppercase tracking-widest">DECENTRALIZED SWARM</p></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-[#1f1614] px-2 py-1 rounded-lg border border-[#d4af37]/30">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-[#d4af37] animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-[10px] font-medium ${isConnected ? 'text-[#d4af37]' : 'text-red-500'}`}>{isConnected ? 'MESH ON' : 'DOWN'}</span>
          </div>
          <div className="flex items-center gap-1 bg-[#1f1614] px-2 py-1 rounded-lg border border-[#d4af37]/30">
            <Clock className="w-3 h-3 text-[#d4af37]" />
            <span className="text-sm font-mono tabular-nums text-[#fffff0]">T+{String(time).padStart(3, '0')}</span>
          </div>
        </div>
      </div>

      <div className="mb-3 bg-[#1f1614] rounded-lg border border-[#d4af37]/20 p-2.5 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-[#d4af37]" /><h3 className="font-semibold text-[#d4af37] text-xs">DISPATCH SELECTOR</h3></div>
          <span className="text-[9px] text-[#f5f5dc]/60">CLICK FLOOR TO DEPLOY</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {sortedRobotIds.map((agent) => {
            const agentStatus = (robots[agent]?.status || "ACTIVE").toUpperCase();
            return (
              <motion.button key={agent} onClick={() => setSelectedAgent(agent)} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} className={`px-2 py-1 rounded font-medium text-[10px] uppercase tracking-wide transition-all flex items-center justify-between ${selectedAgent === agent ? 'bg-[#d4af37]/25 border border-[#d4af37] text-[#fffff0] shadow-[0_0_10px_rgba(212,175,55,0.3)]' : 'bg-[#1a1311] border border-[#d4af37]/20 text-[#f5f5dc] hover:border-[#d4af37]/50 hover:bg-[#251b18]'}`}>
                <span>{agent}</span>
                <span className={`w-1.5 h-1.5 rounded-full ${agentStatus === "BIDDING" ? 'bg-cyan-400' : agentStatus === "CLAIMED" ? 'bg-yellow-400' : agentStatus === "DOCKED" || agentStatus === "IDLE" ? 'bg-sky-400' : agentStatus === "DEAD" ? 'bg-red-500' : agentStatus === "YIELDING" ? 'bg-orange-500' : 'bg-emerald-400'}`} />
              </motion.button>
            );
          })}
        </div>
      </div>

      <div className="mb-3 bg-[#1f1614] rounded-lg border border-[#d4af37]/20 p-2.5 flex-shrink-0">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5 text-[#d4af37]" /><h3 className="font-semibold text-[#d4af37] text-xs">SWARM TELEMETRY</h3></div>
          <span className="text-[9px] text-[#d4af37]/80">SABOTAGE CONTROLS</span>
        </div>
        <div className="space-y-1.5 max-h-[150px] overflow-y-auto custom-scrollbar pr-1">
          {sortedRobotIds.map((id) => {
            const pos = robots[id] || {};
            const displayStatus = (pos.status === "IDLE" || !pos.status) ? "DOCKED" : pos.status;
            const isDead = pos.status === "DEAD";

            return (
              <div key={id} className={`bg-[#1a1311] rounded border p-2 transition-all ${isDead ? 'border-red-800/60 bg-red-950/20' : 'border-[#d4af37]/20'}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`font-bold text-xs ${isDead ? 'text-red-400 line-through' : 'text-[#fffff0]'}`}>{id}</span>
                    <span className="text-[9px] text-[#f5f5dc]/60">({pos.x ?? 0}, {pos.y ?? 0})</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {getStatusBadge(displayStatus)}
                    <button onClick={(e) => { e.stopPropagation(); onSabotage(id); }} disabled={isDead} title={`Sabotage / Kill ${id}`} className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold flex items-center gap-1 transition-all ${isDead ? 'bg-neutral-800 text-neutral-600 border border-neutral-700 cursor-not-allowed opacity-50' : 'bg-red-600 hover:bg-red-500 text-white border border-red-400 shadow-[0_0_8px_rgba(239,68,68,0.7)] active:scale-95 cursor-pointer'}`}>
                      <Skull className="w-2.5 h-2.5" /><span>KILL</span>
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="flex-shrink-0">{getBatteryIcon(pos.battery ?? 100)}</div>
                  <div className="flex-1 h-1.5 bg-[#120d0b] rounded-full overflow-hidden border border-[#d4af37]/10">
                    <motion.div className={`h-full rounded-full ${getBatteryColor(pos.battery ?? 100)}`} initial={{ width: 0 }} animate={{ width: `${pos.battery ?? 100}%` }} transition={{ type: 'spring', damping: 20, stiffness: 100 }} />
                  </div>
                  <span className={`font-mono text-[9px] w-7 text-right ${(pos.battery ?? 100) > 50 ? 'text-emerald-400' : (pos.battery ?? 100) > 20 ? 'text-amber-400' : 'text-red-400'}`}>{pos.battery ?? 100}%</span>
                  <span className="text-[9px] text-[#d4af37] font-mono">PRI:{pos.priority ?? 1}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col bg-[#1f1614] p-2.5 border border-[#d4af37]/30 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between mb-2 flex-shrink-0">
          <div className="flex items-center gap-1.5"><Terminal className="w-3.5 h-3.5 text-[#d4af37]" /><h3 className="font-semibold text-[#d4af37] text-xs">P2P AUCTION TERMINAL</h3></div>
          <span className="text-[8px] bg-[#d4af37]/15 text-[#d4af37] px-1.5 py-0.5 rounded border border-[#d4af37]/30">DECENTRALIZED</span>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 pr-1 font-mono text-[10px]">
          <AnimatePresence initial={false}>
            {logs.map((log) => {
              if (typeof log === 'object' && log !== null) {
                const isBid = log.status === 'BIDDING' || log.type === 'AUCTION_BID';
                const isClaim = log.status === 'CLAIMED' || log.type === 'AUCTION_WIN';
                const isYield = log.status === 'YIELDING' || log.type === 'COLLISION_AVOID';
                const isDead = log.status === 'DEAD' || log.type === 'FAILURE';
                const isDispatch = log.type === 'DISPATCH';

                let containerStyle = 'bg-[#1a1311] border-[#d4af37]/20 text-[#f5f5dc]';
                let tagStyle = 'bg-[#120d0b] text-[#f5f5dc]/70 border-[#d4af37]/20';
                let tagText = log.status || log.type || 'INFO';

                if (isBid) { containerStyle = 'bg-cyan-950/50 border-cyan-500/60 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.2)]'; tagStyle = 'bg-cyan-500/20 text-cyan-300 border-cyan-400/50'; tagText = 'BIDDING'; }
                else if (isClaim) { containerStyle = 'bg-yellow-950/50 border-yellow-500/60 text-yellow-200 shadow-[0_0_10px_rgba(234,179,8,0.2)]'; tagStyle = 'bg-yellow-500/20 text-yellow-300 border-yellow-400/50'; tagText = 'CLAIMED'; }
                else if (isYield) { containerStyle = 'bg-amber-950/40 border-amber-600/50 text-amber-200'; tagStyle = 'bg-amber-500/20 text-amber-300 border-amber-500/50'; tagText = 'YIELD'; }
                else if (isDead) { containerStyle = 'bg-red-950/50 border-red-600/60 text-red-200 shadow-[0_0_10px_rgba(239,68,68,0.2)]'; tagStyle = 'bg-red-500/20 text-red-300 border-red-500/50'; tagText = 'FAILURE'; }
                else if (isDispatch) { containerStyle = 'bg-purple-950/40 border-purple-500/50 text-purple-200'; tagStyle = 'bg-purple-500/20 text-purple-300 border-purple-400/50'; tagText = 'DISPATCH'; }

                return (
                  <motion.div key={log.id} initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }} transition={{ duration: 0.2 }} className={`p-1.5 rounded border text-[9.5px] leading-tight ${containerStyle}`}>
                    <div className="flex items-center justify-between mb-0.5 text-[8px] opacity-90 font-bold">
                      <span>[T+{log.time ?? time}] {log.agentId ? `AGENT ${log.agentId}` : 'SWARM_EVENT'}</span>
                      <span className={`px-1 py-0.2 rounded border font-mono ${tagStyle}`}>{tagText}</span>
                    </div>
                    <div className="font-mono">{log.message}</div>
                  </motion.div>
                );
              }
              return null;
            })}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
};

export default function App() {
  const wsRef = useRef(null);
  const robotsRef = useRef({});
  const lastRenderTime = useRef(0);
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

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then(res => res.json())
      .then(data => {
        if (data.obstacles) setObstacles(data.obstacles);
        if (data.warehouse?.charging_stations) setChargingStations(data.warehouse.charging_stations);
        else if (data.charging_stations) setChargingStations(data.charging_stations);
      })
      .catch(err => console.error('Failed to fetch config:', err));
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setTargetBeacons(prev => prev.filter(b => now - b.id < 6000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSabotage = async (agentId) => {
    try {
      await fetch(`http://localhost:8000/api/sabotage/${agentId}`, { method: 'POST' });
      if (robotsRef.current[agentId]) robotsRef.current[agentId].status = 'DEAD';
      setTelemetryRobots({ ...robotsRef.current });
      setLogs(prev => [{ id: `${Date.now()}-${agentId}-sabotage`, time: robotsRef.current[agentId]?.time ?? 0, agentId: agentId, status: "DEAD", type: "FAILURE", message: `[SABOTAGE] ⚠️ Manual override: ${agentId} neutralized -> Dynamic obstacle active on grid`, color: "red" }, ...prev].slice(0, 25));
    } catch {
      // ignore
    }
  };

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
        
        if (data.agent_id && data.x !== undefined && data.y !== undefined) {
          const prev = prevRobotPositions.current[data.agent_id];
          const prevStatus = prev?.status;
          let status = data.status ?? "ACTIVE";
          if (status === "IDLE") status = "DOCKED";

          robotsRef.current[data.agent_id] = {
            ...prev, ...data, status,
            battery: data.battery ?? prev?.battery ?? 100,
            priority: data.priority ?? prev?.priority ?? 1,
          };

          setRobotIds(prevIds => (prevIds.includes(data.agent_id) ? prevIds : [...prevIds, data.agent_id]));

          const rawStatus = (data.status || "").toUpperCase();
          if (rawStatus !== "MOVING" && rawStatus !== "IDLE" && status !== prevStatus) {
            if (status === "BIDDING") {
              setLogs(prevLogs => [{ id: `${simTime}-${data.agent_id}-bid-${Date.now()}`, time: simTime, agentId: data.agent_id, status: "BIDDING", type: "AUCTION_BID", message: `[${data.agent_id}] ⚡ BROADCAST BID: Estimating dynamic time-space cost`, color: "cyan" }, ...prevLogs].slice(0, 25));
            } else if (status === "CLAIMED") {
              setLogs(prevLogs => [{ id: `${simTime}-${data.agent_id}-claim-${Date.now()}`, time: simTime, agentId: data.agent_id, status: "CLAIMED", type: "AUCTION_WIN", message: `[${data.agent_id}] 🏆 AUCTION WON: Task claimed`, color: "gold" }, ...prevLogs].slice(0, 25));
            } else if (status === "YIELDING" && !activeYields.current.has(data.agent_id)) {
              activeYields.current.add(data.agent_id);
              setLogs(prevLogs => [{ id: `${simTime}-${data.agent_id}-yield-${Date.now()}`, time: simTime, agentId: data.agent_id, status: "YIELDING", type: "COLLISION_AVOID", message: `[${data.agent_id}] Yielding right-of-way to higher-priority node`, color: "orange" }, ...prevLogs].slice(0, 25));
            } else if (status === "DEAD") {
              setLogs(prevLogs => [{ id: `${simTime}-${data.agent_id}-dead-${Date.now()}`, time: simTime, agentId: data.agent_id, status: "DEAD", type: "FAILURE", message: `[${data.agent_id}] ⚠️ CRITICAL FAILURE: Node offline`, color: "red" }, ...prevLogs].slice(0, 25));
            } else if (status === "DOCKED" && prevStatus && prevStatus !== "DOCKED") {
              setLogs(prevLogs => [{ id: `${simTime}-${data.agent_id}-dock-${Date.now()}`, time: simTime, agentId: data.agent_id, status: "DOCKED", type: "DOCKING", message: `[${data.agent_id}] 🔌 DOCKED at charging pad`, color: "sky" }, ...prevLogs].slice(0, 25));
            }
          }

          if (status !== "YIELDING" && activeYields.current.has(data.agent_id)) {
            activeYields.current.delete(data.agent_id);
          }
          prevRobotPositions.current[data.agent_id] = { x: data.x, y: data.y, time: simTime, status };
        }

        // Dashboard Render Throttle (150ms limit)
        if (data.time !== undefined) {
          const now = Date.now();
          if (now - lastRenderTime.current > 150) {
            setTime(prevTime => Math.max(prevTime, data.time));
            setTelemetryRobots({ ...robotsRef.current });
            lastRenderTime.current = now;
          }
        }
      } catch {
        // ignore
      }
    };

    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleFloorClick = async (event) => {
    if (event.stopPropagation) event.stopPropagation();
    
    const gx = Math.floor(event.point.x + GRID_HALF);
    const gy = Math.floor(event.point.z + GRID_HALF);
    const clampedX = Math.max(0, Math.min(GRID_SIZE - 1, gx));
    const clampedY = Math.max(0, Math.min(GRID_SIZE - 1, gy));

    if (obstacles.some(obs => obs[0] === clampedX && obs[1] === clampedY)) return;

    const beaconId = Date.now();
    setTargetBeacons(prev => [...prev.filter(b => Date.now() - b.id < 5000), { x: clampedX, y: clampedY, id: beaconId }]);
    setLogs(prev => [{ id: `${beaconId}-dispatch`, time: time, agentId: selectedAgent, status: "DISPATCH", type: "DISPATCH", message: `[OPERATOR] Dispatched task target @ (${clampedX}, ${clampedY})`, color: "purple" }, ...prev].slice(0, 25));

    try { await axios.post('http://localhost:8000/api/tasks', { x: clampedX, y: clampedY }); } catch { /* ignore */ }
    try {
      await fetch(`${API_URL}/api/dispatch/${selectedAgent}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ x: clampedX, y: clampedY }) });
      if (robotsRef.current[selectedAgent]) {
        robotsRef.current[selectedAgent].target_x = clampedX;
        robotsRef.current[selectedAgent].target_y = clampedY;
      }
    } catch {
      // ignore
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#120d0b] text-[#f5f5dc] flex">
      <SimulationCanvas robotIds={robotIds} robotsRef={robotsRef} obstacles={obstacles} chargingStations={chargingStations} targetBeacons={targetBeacons} onFloorClick={handleFloorClick} />
      <DashboardPanel robotIds={robotIds} robots={telemetryRobots} time={time} isConnected={isConnected} selectedAgent={selectedAgent} setSelectedAgent={setSelectedAgent} logs={logs} onSabotage={handleSabotage} />
    </div>
  );
}