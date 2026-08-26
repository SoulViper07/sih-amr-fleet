import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Box, Html, Text, RoundedBox } from '@react-three/drei';
import * as THREE from 'three';
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

const AmrMesh = React.memo(({ id, index, targetPosition, battery, priority }) => {
  const meshRef = useRef();
  const [hovered, setHovered] = useState(false);

  useFrame((state, delta) => {
    if (meshRef.current && targetPosition) {
      meshRef.current.position.lerp(new THREE.Vector3(...targetPosition), Math.min(delta * 8, 1));
    }
  });

  const color = robotColors[index % robotColors.length];

  return (
    <group ref={meshRef} position={targetPosition || [0, 0, 0]}>
      <Box
        args={[0.7, 0.7, 0.7]}
        position={[0, 0.35, 0]}
        castShadow
        receiveShadow
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <meshStandardMaterial 
          color={color} 
          metalness={0.3}
          roughness={0.4}
          emissive={color}
          emissiveIntensity={hovered ? 0.3 : 0.1}
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
          color: '#fde68a',
          textShadow: '0 0 10px rgba(251, 191, 36, 0.8)',
        }}
      >
        <div style={{ background: 'rgba(0,0,0,0.7)', padding: '2px 6px', borderRadius: '4px', border: `1px solid ${color}`, display: 'inline-block' }}>
          <div>{id}</div>
          <div style={{ fontSize: '10px', opacity: 0.8 }}>{battery}%</div>
        </div>
      </Html>
      <Box
        args={[0.5, 0.02, 0.5]}
        position={[0, 0.01, 0]}
        castShadow
      >
        <meshBasicMaterial color={color} transparent opacity={0.3} />
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
      
      <gridHelper args={[GRID_SIZE, GRID_SIZE, '#78350f', '#451a03']} position={[0, 0, 0]} />
      
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

  return (
    <div className="w-full h-full flex flex-col bg-neutral-900 border-l border-yellow-700/30 p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 border-b border-yellow-700/20 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-yellow-700/20 rounded-lg border border-yellow-700/30">
            <Radio className="w-5 h-5 text-yellow-500" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-yellow-300">EDGE-AI FLEET</h1>
            <p className="text-xs text-yellow-600 uppercase tracking-widest">COORDINATION SYSTEM</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-neutral-800 px-3 py-1.5 rounded-lg border border-yellow-700/30">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-xs font-medium ${isConnected ? 'text-yellow-400' : 'text-red-500'}`}>
              {isConnected ? 'LINK' : 'DOWN'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 bg-neutral-800 px-3 py-1.5 rounded-lg border border-yellow-700/30">
            <Clock className="w-3.5 h-3.5 text-yellow-600" />
            <span className="text-lg font-mono tabular-nums text-yellow-400">T+{String(time).padStart(3, '0')}</span>
          </div>
        </div>
      </div>

      {/* Commander Controls */}
      <div className="mb-4 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-sm">COMMANDER CONTROLS</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {['AMR-1', 'AMR-2', 'AMR-3', 'AMR-4'].map((agent) => (
            <button
              key={agent}
              onClick={() => setSelectedAgent(agent)}
              className={`px-3 py-2 rounded font-medium text-xs uppercase tracking-wide transition-all text-neutral-300 ${
                selectedAgent === agent
                  ? 'bg-yellow-600/20 border-2 border-yellow-500 text-yellow-300 shadow-[0_0_10px_rgba(234,179,8,0.3)]'
                  : 'bg-neutral-900 border border-neutral-700 hover:border-yellow-700/50 hover:bg-neutral-800'
              }`}
            >
              {agent}
            </button>
          ))}
        </div>
      </div>

      {/* Active Fleet Metric */}
      <div className="mb-4 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-4 h-4 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-sm">ACTIVE FLEET</h3>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-yellow-400 tabular-nums">{Object.keys(robots).length}</span>
          <span className="text-xs text-yellow-600">/ 4 UNITS</span>
        </div>
        <p className="text-xs text-yellow-600 mt-1">DECENTRALIZED NODES</p>
      </div>

      {/* Live Telemetry */}
      <div className="mb-4 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-4 flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="w-4 h-4 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-sm">LIVE TELEMETRY</h3>
        </div>
        <div className="space-y-2 max-h-[200px] overflow-y-auto">
          {Object.entries(robots).map(([id, pos]) => (
            <div key={id} className="bg-neutral-900 rounded border border-neutral-700 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-yellow-400 text-sm">{id}</span>
                <span className="text-xs text-yellow-600">({pos.x}, {pos.y})</span>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-shrink-0">{getBatteryIcon(pos.battery)}</div>
                <div className="flex-1 h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${getBatteryColor(pos.battery)}`}
                    style={{ width: `${pos.battery}%` }}
                  ></div>
                </div>
                <span className={`font-mono text-xs w-10 text-right ${pos.battery > 50 ? 'text-emerald-400' : pos.battery > 20 ? 'text-amber-400' : 'text-red-400'}`}>
                  {pos.battery}%
                </span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-yellow-600">
                <span className="flex items-center gap-1"><Wifi className="w-2.5 h-2.5" /> PRI: {pos.priority ?? 'N/A'}</span>
                <span className="flex items-center gap-1"><Shield className="w-2.5 h-2.5" /> BAT: {pos.battery}%</span>
                <span className="flex items-center gap-1"><Gauge className="w-2.5 h-2.5" /> POS: ({pos.x},{pos.y})</span>
              </div>
            </div>
          ))}
          {Object.keys(robots).length === 0 && (
            <div className="text-yellow-600 text-xs italic text-center py-8">NO TELEMETRY RECEIVED</div>
          )}
        </div>
      </div>

      {/* P2P Network Feed - takes remaining space */}
      <div className="flex-1 min-h-0 bg-neutral-800/50 rounded-lg border border-yellow-700/20 p-4 overflow-y-auto custom-scrollbar">
        <div className="flex items-center gap-2 mb-3">
          <Terminal className="w-4 h-4 text-yellow-500" />
          <h3 className="font-semibold text-yellow-300 text-sm">P2P NETWORK FEED</h3>
          <span className="ml-auto text-[10px] bg-yellow-700/20 text-yellow-500 px-1.5 py-0.5 rounded">ENCRYPTED</span>
        </div>
        <div className="text-xs text-neutral-300 leading-relaxed font-mono">
          {logs.length === 0 ? (
            <div className="text-neutral-500 italic">AWAITING YIELD EVENTS...</div>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} className="mb-1 pb-1 last:mb-0 border-b border-neutral-700/50">
                <span className="text-yellow-500">[FEED] </span>
                <span>{log}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
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
            [data.agent_id]: { x: data.x, y: data.y, battery: data.battery ?? 100, priority: data.priority }
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
      <div className="w-2/3 h-full relative">
        <Canvas
          camera={{ position: [0, 25, 0], fov: 50, lookAt: [0, 0, 0] }}
          shadows
          style={{ touchAction: 'none' }}
          onCreated={({ gl }) => { gl.setClearColor(0x0a0a0a, 1); }}
        >
          <Scene 
            robots={robots} 
            obstacles={obstacles} 
            onFloorClick={handleFloorClick} 
          />
          <OrbitControls 
            makeDefault 
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