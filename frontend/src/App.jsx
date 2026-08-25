import React, { useState, useEffect, useRef } from 'react';
import { Activity, Clock, Cpu, Battery, Zap, MapPin, Target, Terminal, Wifi, Shield, Gauge, Radio } from 'lucide-react';

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';

export default function App() {
  const [robots, setRobots] = useState({});
  const [time, setTime] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('AMR-1');
  const [gridSize, setGridSize] = useState({ w: 20, h: 20 });
  const [obstacles, setObstacles] = useState([]);
  const [logs, setLogs] = useState([]);
  const prevRobotPositions = useRef({});

  // Fetch grid config on mount
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
              const updated = [newLog, ...prevLogs].slice(0, 10);
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

  const handleCellClick = async (x, y) => {
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
  };

  const gridCells = Array.from({ length: gridSize.w * gridSize.h }, (_, i) => {
    const x = i % gridSize.w;
    const y = Math.floor(i / gridSize.w);
    return { x, y };
  });

  const getBatteryColor = (level) => {
    if (level > 50) return 'bg-green-500';
    if (level > 20) return 'bg-amber-500';
    return 'bg-red-500';
  };

  const getBatteryIcon = (level) => {
    if (level > 75) return <Battery className="w-4 h-4 text-green-500" />;
    if (level > 50) return <Battery className="w-4 h-4 text-green-400" />;
    if (level > 25) return <Battery className="w-4 h-4 text-amber-400" />;
    if (level > 10) return <Zap className="w-4 h-4 text-amber-500" />;
    return <Zap className="w-4 h-4 text-red-500 animate-pulse" />;
  };

  const isObstacleCell = (x, y) => {
    return obstacles.some(obs => obs[0] === x && obs[1] === y);
  };

  const cellWidthPercent = 100 / gridSize.w;
  const cellHeightPercent = 100 / gridSize.h;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#e8f5e9] p-6 font-mono">
      {/* Header */}
      <header className="flex justify-between items-center mb-6 border-b border-cyan-900/30 pb-4">
        <div className="flex items-center gap-4">
          <div className="p-2 bg-[#111] border border-cyan-900/50 rounded-lg">
            <Radio className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-cyan-300">AMR FLEET COMMAND</h1>
            <p className="text-xs text-cyan-600 uppercase tracking-widest">DECENTRALIZED COORDINATION SYSTEM</p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 bg-[#111] px-4 py-2 rounded-lg border border-cyan-900/50">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-cyan-400 animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-xs font-medium ${isConnected ? 'text-cyan-400' : 'text-red-500'}`}>
              {isConnected ? 'LINK ESTABLISHED' : 'LINK DOWN'}
            </span>
          </div>
          <div className="flex items-center gap-2 bg-[#111] px-4 py-2 rounded-lg border border-cyan-900/50">
            <Clock className="w-4 h-4 text-cyan-600" />
            <span className="text-lg font-mono tabular-nums text-amber-400">T+{String(time).padStart(3, '0')}</span>
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
        {/* Left Column: The Grid */}
        <div className="lg:col-span-2 panel-cyber p-4 rounded-xl">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2 text-cyan-300">
              <MapPin className="w-4 h-4" />
              TACTICAL GRID <span className="text-xs text-cyan-600">({gridSize.w}×{gridSize.h})</span>
            </h2>
            <div className="flex items-center gap-3 text-xs text-cyan-600">
              <Target className="w-3 h-3" />
              <span>SELECTED: <strong className="text-amber-400">{selectedAgent}</strong></span>
            </div>
          </div>
          
          <div className="relative aspect-square w-full max-w-4xl mx-auto tech-border rounded-[4px] overflow-hidden">
            {/* Static Grid Layer */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${gridSize.w}, 1fr)`,
                gridTemplateRows: `repeat(${gridSize.h}, 1fr)`,
                width: '100%',
                height: '100%',
              }}
              className="grid-cell"
            >
              {gridCells.map((cell) => {
                const isRobotHere = Object.entries(robots).find(([id, pos]) => pos.x === cell.x && pos.y === cell.y);
                const isObstacle = isObstacleCell(cell.x, cell.y);
                return (
                  <div
                    key={`${cell.x}-${cell.y}`}
                    onClick={() => !isRobotHere && !isObstacle && handleCellClick(cell.x, cell.y)}
                    className={`relative ${isObstacle ? 'obstacle' : ''} ${isRobotHere ? 'occupied' : ''}`}
                    style={{ userSelect: 'none' }}
                  >
                    {!isObstacle && !isRobotHere && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-1 h-1 rounded-full bg-cyan-900/30" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Dynamic Robot Layer - Absolute Positioning for Smooth Animation */}
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 10 }}>
              {Object.entries(robots).map(([id, pos]) => (
                <div
                  key={id}
                  style={{
                    position: 'absolute',
                    left: `${(pos.x / gridSize.w) * 100}%`,
                    top: `${(pos.y / gridSize.h) * 100}%`,
                    width: `${cellWidthPercent}%`,
                    height: `${cellHeightPercent}%`,
                    transition: 'left 0.8s cubic-bezier(0.4, 0, 0.2, 1), top 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  <div className="absolute inset-0 flex items-center justify-center robot-marker">
                    <div className="relative w-full h-full flex items-center justify-center">
                      {/* Outer glow ring */}
                      <div className="absolute inset-0 rounded-full border border-amber-400/30 animate-pulse" style={{ animationDuration: '2s' }} />
                      {/* Core marker */}
                      <div className="relative z-10 w-3/4 h-3/4 bg-amber-400 rounded-full shadow-[0_0_20px_rgba(251,191,36,1),0_0_40px_rgba(251,191,36,0.6)] border-2 border-white flex items-center justify-center font-bold text-black text-[10px] leading-none">
                        {id.split('-')[1]}
                      </div>
                      {/* Direction indicator */}
                      <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-cyan-400 rounded-full border-2 border-black opacity-80" />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Grid coordinate labels */}
            <div className="absolute bottom-1 right-1 text-[7px] text-cyan-900/50 font-mono pointer-events-none">
              {gridSize.w - 1},{gridSize.h - 1}
            </div>
          </div>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-cyan-600">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-cyan-900/30" />
              <span>FREE</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.8)] border border-white" />
              <span>AMR</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded obstacle" style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(8,145,178,0.3) 3px, rgba(8,145,178,0.3) 6px)' }} />
              <span>OBSTACLE</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-cyan-400" />
              <span>TARGET</span>
            </div>
          </div>
        </div>

        {/* Right Column: Metrics */}
        <div className="space-y-4">
          {/* Commander Controls */}
          <div className="panel-cyber p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-5 h-5 text-cyan-400" />
              <h3 className="font-semibold text-cyan-300">COMMANDER CONTROLS</h3>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {['AMR-1', 'AMR-2', 'AMR-3', 'AMR-4'].map((agent) => (
                <button
                  key={agent}
                  onClick={() => setSelectedAgent(agent)}
                  className={`btn-cyber px-3 py-2 rounded font-medium text-xs uppercase tracking-wide transition-all ${
                    selectedAgent === agent ? 'active' : ''
                  }`}
                >
                  {agent}
                </button>
              ))}
            </div>
          </div>

          {/* P2P Network Feed */}
          <div className="panel-cyber p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="w-5 h-5 text-green-400" />
              <h3 className="font-semibold text-green-400">P2P NETWORK FEED</h3>
              <span className="ml-auto text-[10px] bg-green-900/30 text-green-400 px-1.5 py-0.5 rounded">ENCRYPTED</span>
            </div>
            <div className="terminal-feed crt-scanline rounded p-3 h-56 overflow-y-auto text-[11px] text-green-300 leading-relaxed">
              {logs.length === 0 ? (
                <div className="text-green-600 italic">> AWAITING YIELD EVENTS...</div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="mb-1 border-b border-green-900/30 pb-1 last:border-0 animate-fade-in-up" style={{ animationDelay: `${idx * 0.05}s` }}>
                    <span className="text-green-500">[FEED] </span>
                    <span className="text-green-300">{log}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Active Fleet */}
          <div className="panel-cyber p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-5 h-5 text-cyan-400" />
              <h3 className="font-semibold text-cyan-300">ACTIVE FLEET</h3>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-amber-400 tabular-nums">{Object.keys(robots).length}</span>
              <span className="text-xs text-cyan-600">/ 4 UNITS</span>
            </div>
            <p className="text-xs text-cyan-600 mt-1">DECENTRALIZED NODES</p>
          </div>

          {/* Live Telemetry */}
          <div className="panel-cyber p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-5 h-5 text-cyan-400" />
              <h3 className="font-semibold text-cyan-300">LIVE TELEMETRY</h3>
            </div>
            <div className="space-y-3">
              {Object.entries(robots).map(([id, pos]) => (
                <div key={id} className="bg-[#0a0a0a] rounded border border-cyan-900/30 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-amber-400">{id}</span>
                    <span className="text-xs text-cyan-600">({pos.x}, {pos.y})</span>
                  </div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-shrink-0">{getBatteryIcon(pos.battery)}</div>
                    <div className="flex-1 h-1.5 bg-cyan-900/50 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${getBatteryColor(pos.battery)}`}
                        style={{ width: `${pos.battery}%`, boxShadow: `0 0 10px ${pos.battery > 50 ? 'rgba(34,197,94,0.8)' : pos.battery > 20 ? 'rgba(251,191,36,0.8)' : 'rgba(239,68,68,0.8)'}` }}
                      ></div>
                    </div>
                    <span className={`font-mono text-xs w-10 text-right ${pos.battery > 50 ? 'text-green-400' : pos.battery > 20 ? 'text-amber-400' : 'text-red-400'}`}>
                      {pos.battery}%
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-[10px] text-cyan-600">
                    <span className="flex items-center gap-1">
                      <Wifi className="w-2.5 h-2.5" />
                      PRI: {pos.priority ?? 'N/A'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Shield className="w-2.5 h-2.5" />
                      BAT: {pos.battery}%
                    </span>
                    <span className="flex items-center gap-1">
                      <Gauge className="w-2.5 h-2.5" />
                      POS: ({pos.x},{pos.y})
                    </span>
                  </div>
                </div>
              ))}
              {Object.keys(robots).length === 0 && (
                <div className="text-cyan-600 text-xs italic text-center py-8">> NO TELEMETRY RECEIVED</div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}