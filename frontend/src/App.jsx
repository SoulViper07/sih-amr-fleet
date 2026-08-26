import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Box, Html, Text, RoundedBox, Line } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  Clock, 
  Cpu, 
  Battery, 
  Zap, 
  MapPin, 
  Target, 
  Terminal, 
  Wifi, 
  Shield, 
  Gauge, 
  Radio,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';
const GRID_SIZE = 20;
const CELL_SIZE = 1;
const GRID_HALF = GRID_SIZE / 2;

function gridToWorld(x, y) {
  return [x - GRID_HALF + 0.5, 0.5, y - GRID_HALF + 0.5];
}

function worldToGrid(x, z) {
  const gx = Math.floor(x + GRID_HALF);
  const gy = Math.floor(z + GRID_HALF);
  return [Math.max(0, Math.min(GRID_SIZE - 1, gx)), Math.max(0, Math.min(GRID_SIZE - 1, gy))];
}

const robotColors = [
  '#fbbf24', // AMR-1 - amber
  '#f97316', // AMR-2 - orange
  '#eab308', // AMR-3 - yellow
  '#fde047', // AMR-4 - light yellow
];

const AmrMesh = React.memo(({ id, index, targetPosition, battery, priority, status }) => {
  const meshRef = useRef();
  const [hovered, setHovered] = useState(false);
  
  // Initialize position state safely to prevent NaN matrix crashes
  const [pos] = useState(() => {
    const initialPos = targetPosition && targetPosition.length === 3 && 
      targetPosition.every(v => typeof v === 'number' && !isNaN(v))
      ? new THREE.Vector3(targetPosition[0], targetPosition[1], targetPosition[2])
      : new THREE.Vector3(0, 0, 0);
    return initialPos;
  });

  useFrame((_, delta) => {
    if (meshRef.current && targetPosition && Array.isArray(targetPosition) && targetPosition.length === 3) {
      const target = new THREE.Vector3(targetPosition[0], targetPosition[1], targetPosition[2]);
      if (!isNaN(target.x) && !isNaN(target.y) && !isNaN(target.z)) {
        meshRef.current.position.lerp(target, Math.min(1, delta * 8));
      }
    }
  });

  const isMoving = targetPosition && 
    (Math.abs(meshRef.current?.position.x - targetPosition[0]) > 0.01 || Math.abs(meshRef.current?.position.z - targetPosition[2]) > 0.01);

  const isDead = status === "DEAD";

  return (
    <group ref={meshRef} position={pos}>
      <Box
        args={[0.7, 0.7, 0.7]}
        position={[0, 0.35, 0]}
        castShadow
        receiveShadow
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <meshStandardMaterial 
          color={isDead ? "#3f3f46" : "#d97706"} 
          emissive={isDead ? "#3f3f46" : "#f59e0b"} 
          emissiveIntensity={isDead ? 0.2 : 2} 
          toneMapped={false}
        />
      </Box>
      <Html
        position={[0, 1.2, 0]}
        style={{
          pointerEvents: 'none',
          textAlign: 'center',
          fontSize: '11px',
          fontFamily: 'monospace',
          fontWeight: 'bold',
          color: isDead ? '#71717a' : '#fde68a',
          textShadow: isDead ? 'none' : '0 0 10px rgba(251, 191, 36, 0.8)',
        }}
      >
        <div style={{ background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: '4px', border: `1px solid ${isDead ? '#52525b' : '#f59e0b'}`, display: 'inline-block' }}>
          <div>{id}</div>
          <div style={{ fontSize: '10px', opacity: 0.8 }}>{battery}%</div>
        </div>
      </Html>
      <Box
        args={[0.5, 0.02, 0.5]}
        position={[0, 0.01, 0]}
        castShadow
      >
        <meshBasicMaterial color={isDead ? "#52525b" : "#f59e0b"} transparent opacity={isDead ? 0.15 : 0.3} />
      </Box>
    </group>
  );
});

const Scene = ({ robots, obstacles, onFloorClick }) => {
  return (
    <>
      <ambientLight intensity={0.6} color="#fef3c7" />
      <directionalLight 
        position={[15, 20, 15]} 
        intensity={2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.1}
        shadow-camera-far={50}
        shadow-camera-left={-20}
        shadow-camera-right={20}
        shadow-camera-top={20}
        shadow-camera-bottom={-20}
      />
      <directionalLight position={[-10, 10, -10]} intensity={0.5} color="#fef3c7" />
      
      <gridHelper args={[GRID_SIZE, GRID_SIZE, '#333333', '#111111']} position={[0, 0, 0]} />
      
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0, 0]}
        onPointerDown={onFloorClick}
      >
        <planeGeometry args={[GRID_SIZE, GRID_SIZE]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>

      {obstacles.map((obs, i) => {
        const [wx, , wz] = gridToWorld(obs[0], obs[1]);
        return (
          <Box
            key={`obs-${i}`}
            position={[wx, 0.5, wz]}
            args={[0.9, 1, 0.9]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color="#18181b" metalness={0.1} roughness={0.9} />
          </Box>
        );
      })}

      {/* Trajectory lines in world space - rendered once per robot */}
      {Object.entries(robots).map(([id, data]) => {
        const hasTarget = data.target_x !== undefined && data.target_y !== undefined;
        const isMoving = hasTarget && (data.x !== data.target_x || data.y !== data.target_y);
        if (!isMoving) return null;
        
        const startX = data.x - GRID_HALF + 0.5;
        const startZ = data.y - GRID_HALF + 0.5;
        const targetX = data.target_x - GRID_HALF + 0.5;
        const targetZ = data.target_y - GRID_HALF + 0.5;
        
        return (
          <Line
            key={`path-${id}`}
            points={[
              [startX, 0.05, startZ],
              [targetX, 0.05, targetZ]
            ]}
            color="#eab308"
            lineWidth={1.5}
            dashed
            dashSize={0.4}
            gapSize={0.2}
          />
        );
      })}

      {Object.entries(robots).map(([id, pos], idx) => {
        const targetPos = gridToWorld(pos.x, pos.y);
        return (
          <AmrMesh
            key={id}
            id={id}
            index={idx}
            targetPosition={targetPos}
            battery={pos.battery}
            priority={pos.priority}
            status={pos.status}
          />
        );
      })}
    </>
  );
};

const DashboardPanel = ({ 
  robots, 
  time, 
  isConnected, 
  selectedAgent, 
  setSelectedAgent, 
  logs,
  handleDispatch 
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
    if (status === "DEAD") return <span className="px-1.5 py-0.5 text-[9px] font-medium bg-red-900/50 text-red-400 border border-red-700/50 rounded">DEAD</span>;
    if (status === "YIELDING") return <span className="px-1.5 py-0.5 text-[9px] font-medium bg-amber-900/50 text-amber-400 border border-amber-700/50 rounded">YIELDING</span>;
    return <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-900/50 text-emerald-400 border border-emerald-700/50 rounded">ACTIVE</span>;
  };

  const robotIds = Object.keys(robots).sort();

  return (
    <motion.div
      className="w-1/4 h-full flex flex-col p-4 bg-neutral-900 border-l border-yellow-700/30"
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', damping: 20, stiffness: 100, delay: 0.2 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4 border-b border-yellow-700/20 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-yellow-700/20 rounded-lg border border-yellow-700/30">
            <Radio className="w-4 h-4 text-yellow-500" />
          </div>
          <div>
            <motion.h1
              className="text-lg font-bold tracking-tight text-yellow-300"
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              EDGE-AI FLEET
            </motion.h1>
            <p className="text-[10px] text-yellow-600 uppercase tracking-widest">COORDINATION SYSTEM</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-neutral-800 px-2 py-1 rounded-lg border border-yellow-700/30">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-[10px] font-medium ${isConnected ? 'text-yellow-400' : 'text-red-500'}`}>
              {isConnected ? 'LINK' : 'DOWN'}
            </span>
          </div>
          <div className="flex items-center gap-1 bg-neutral-800 px-2 py-1 rounded-lg border border-yellow-700/30">
            <Clock className="w-3 h-3 text-yellow-600" />
            <span className="text-base font-mono tabular-nums text-yellow-400">T+{String(time).padStart(3, '0')}</span>
          </div>
        </div>
      </div>

      {/* Commander Controls - Dynamic grid based on active robots */}
      <div className="mb-3 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-3">
        <div className="flex items-center gap-1.5 mb-2">
          <Target className="w-3.5 h-3.5 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-xs">COMMANDER CONTROLS</h3>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {robotIds.map((agent) => (
            <motion.button
              key={agent}
              onClick={() => setSelectedAgent(agent)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-2 py-1.5 rounded font-medium text-[10px] uppercase tracking-wide transition-all text-neutral-300 ${
                selectedAgent === agent
                  ? 'bg-yellow-600/20 border-2 border-yellow-500 text-yellow-300 shadow-[0_0_10px_rgba(234,179,8,0.3)]'
                  : 'bg-neutral-900 border border-neutral-700 hover:border-yellow-700/50 hover:bg-neutral-800'
              }`}
            >
              {agent}
            </motion.button>
          ))}
        </div>
      </div>

      {/* Active Fleet Metric */}
      <div className="mb-3 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Activity className="w-3.5 h-3.5 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-xs">ACTIVE FLEET</h3>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-yellow-400 tabular-nums">{robotIds.length}</span>
          <span className="text-[10px] text-yellow-600">/ {robotIds.length} UNITS</span>
        </div>
        <p className="text-[10px] text-yellow-600 mt-0.5">DECENTRALIZED NODES</p>
      </div>

      {/* Live Telemetry - Dynamic with status badges */}
      <div className="mb-3 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-3 flex-shrink-0">
        <div className="flex items-center gap-1.5 mb-2">
          <Cpu className="w-3.5 h-3.5 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-xs">LIVE TELEMETRY</h3>
        </div>
        <div className="space-y-1.5 max-h-[180px] overflow-y-auto">
          {robotIds.map((id) => {
            const pos = robots[id];
            return (
              <div key={id} className="bg-neutral-900 rounded border border-neutral-700 p-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-medium text-yellow-400 text-xs">{id}</span>
                  <span className="text-[10px] text-yellow-600">({pos.x}, {pos.y})</span>
                </div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <div className="flex-shrink-0">{getBatteryIcon(pos.battery)}</div>
                  <div className="flex-1 h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${getBatteryColor(pos.battery)}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${pos.battery}%` }}
                      transition={{ type: 'spring', damping: 20, stiffness: 100 }}
                    />
                  </div>
                  <span className={`font-mono text-[10px] w-8 text-right ${pos.battery > 50 ? 'text-emerald-400' : pos.battery > 20 ? 'text-amber-400' : 'text-red-400'}`}>
                    {pos.battery}%
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[9px]">
                  <span className="flex items-center gap-0.5">{getStatusBadge(pos.status)}</span>
                  <span className="flex items-center gap-0.5 text-yellow-600"><Wifi className="w-2 h-2" /> PRI: {pos.priority ?? 'N/A'}</span>
                  <span className="flex items-center gap-0.5 text-yellow-600"><Shield className="w-2 h-2" /> BAT: {pos.battery}%</span>
                  <span className="flex items-center gap-0.5 text-yellow-600"><Gauge className="w-2 h-2" /> POS: ({pos.x},{pos.y})</span>
                </div>
              </div>
            );
          })}
          {robotIds.length === 0 && (
            <div className="text-yellow-600 text-[10px] italic text-center py-4">NO TELEMETRY RECEIVED</div>
          )}
        </div>
      </div>

      {/* P2P Network Feed - takes remaining space */}
      <div className="flex-1 min-h-0 overflow-y-auto mt-4 bg-black p-3 border border-yellow-700/50 rounded">
        <div className="flex items-center gap-1.5 mb-2">
          <Terminal className="w-3.5 h-3.5 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-xs">P2P NETWORK FEED</h3>
          <span className="ml-auto text-[9px] bg-yellow-700/20 text-yellow-500 px-1.5 py-0.5 rounded">ENCRYPTED</span>
        </div>
        <div className="text-[10px] text-neutral-300 leading-relaxed font-mono">
          {logs.length === 0 ? (
            <div className="text-neutral-500 italic">AWAITING YIELD EVENTS...</div>
          ) : (
            <AnimatePresence>
            {logs.map((log, index) => (
              <motion.div 
                key={index}
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.3 }}
                className="mb-1.5 text-yellow-100/80 font-mono text-[10px]"
              >
                {log}
              </motion.div>
            ))}
          </AnimatePresence>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default function App() {
  const [robots, setRobots] = useState({});
  const [time, setTime] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('AMR-1');
  const [gridSize, setGridSize] = useState({ w: 20, h: 20 });
  const [obstacles, setObstacles] = useState([]);
  const [logs, setLogs] = useState([]);
  const prevRobotPositions = useRef({});

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then(res => res.json())
      .then(data => {
        setGridSize({ w: data.grid_size[0], h: data.grid_size[1] });
        setObstacles(data.obstacles);
      })
      .catch(err => console.error('Failed to fetch config:', err));
  }, []);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.time !== undefined) {
          setTime(data.time);
        }
        if (data.agent_id && data.x !== undefined && data.y !== undefined) {
          const prev = prevRobotPositions.current[data.agent_id];
          if (prev && prev.x === data.x && prev.y === data.y && prev.time !== data.time) {
            setLogs(prevLogs => {
              const newLog = `[${data.time}] ${data.agent_id} (Pri ${data.priority}) yielding right-of-way.`;
              const updated = [newLog, ...prevLogs].slice(0, 12);
              return updated;
            });
          }
          prevRobotPositions.current[data.agent_id] = { x: data.x, y: data.y, time: data.time };
          
          setRobots(prev => ({
            ...prev,
            [data.agent_id]: { 
              x: data.x, 
              y: data.y, 
              battery: data.battery ?? 100, 
              priority: data.priority,
              status: data.status ?? "ACTIVE",
              // Preserve existing target if present
              target_x: prev[data.agent_id]?.target_x,
              target_y: prev[data.agent_id]?.target_y,
            }
          }));
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    return () => ws.close();
  }, []);

  const handleDispatch = useMemo(() => async (x, y) => {
    try {
      const response = await fetch(`${API_URL}/api/dispatch/${selectedAgent}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y })
      });
      if (!response.ok) {
        const error = await response.json();
        console.error(`Dispatch failed: ${error.detail || response.statusText}`);
      }
      // Update local state with target for trajectory line
      setRobots(prev => ({
        ...prev,
        [selectedAgent]: {
          ...prev[selectedAgent],
          target_x: x,
          target_y: y,
        }
      }));
    } catch (err) {
      console.error("Failed to dispatch command:", err);
    }
  }, [selectedAgent]);

  const handleFloorClick = (event) => {
    const x = Math.floor(event.point.x + GRID_HALF);
    const z = Math.floor(event.point.z + GRID_HALF);
    const clampedX = Math.max(0, Math.min(GRID_SIZE - 1, x));
    const clampedZ = Math.max(0, Math.min(GRID_SIZE - 1, z));
    const isObstacle = obstacles.some(obs => obs[0] === clampedX && obs[1] === clampedZ);
    if (!isObstacle) {
      handleDispatch(clampedX, clampedZ);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-neutral-950 text-amber-50 flex">
      <div className="w-3/4 h-full relative">
        <Canvas
          camera={{ position: [0, 25, 30], fov: 50 }}
          shadows
          style={{ touchAction: 'none' }}
        >
          <color attach="background" args={['#050505']} />
          <Scene 
            robots={robots} 
            obstacles={obstacles} 
            onFloorClick={handleFloorClick} 
          />
          <EffectComposer disableNormalPass>
            <Bloom luminanceThreshold={1} mipmapBlur intensity={1.5} />
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
        <div className="absolute bottom-4 left-4 right-4 flex flex-wrap justify-center gap-4 text-xs text-neutral-400 pointer-events-none">
          <div className="flex items-center gap-1.5 bg-neutral-900/80 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2 h-2 rounded bg-yellow-700/30 border border-yellow-600" />
            <span>FREE CELL</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/80 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2 h-2 rounded bg-yellow-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
            <span>AMR UNIT</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/80 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2 h-2 rounded bg-neutral-800 border border-neutral-600" />
            <span>OBSTACLE</span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-900/80 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur">
            <div className="w-2 h-2 rounded bg-yellow-500" />
            <span>DISPATCH TARGET</span>
          </div>
        </div>

        {/* Camera Hint */}
        <div className="absolute top-4 left-4 text-xs text-neutral-500 bg-neutral-900/80 px-3 py-1.5 rounded border border-neutral-700 backdrop-blur">
          Drag to rotate • Scroll to zoom • Click floor to dispatch
        </div>
      </div>

      <DashboardPanel
        robots={robots}
        time={time}
        isConnected={isConnected}
        selectedAgent={selectedAgent}
        setSelectedAgent={setSelectedAgent}
        logs={logs}
        handleDispatch={handleDispatch}
      />
    </div>
  );
}