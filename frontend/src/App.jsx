import React, { useState, useEffect } from 'react';
import { Activity, Clock, Cpu, Battery, Zap, MapPin, Target } from 'lucide-react';

const WS_URL = 'ws://localhost:8000/ws';
const API_URL = 'http://localhost:8000';

export default function App() {
  const [robots, setRobots] = useState({});
  const [time, setTime] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('AMR-1');

  useEffect(() => {
    // Using standard Native WebSockets - bulletproof!
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
          setRobots(prev => ({
            ...prev,
            [data.agent_id]: { x: data.x, y: data.y, battery: data.battery ?? 100 }
          }));
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    return () => ws.close(); // Cleanup on unmount
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

  // 10x10 Grid generator
  const gridCells = Array.from({ length: 100 }, (_, i) => {
    const x = i % 10;
    const y = Math.floor(i / 10);
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

  return (
    <div className="min-h-screen bg-[#111111] text-[#FDFBF7] p-8 font-sans">
      {/* Header */}
      <header className="flex justify-between items-center mb-8 border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AMR Fleet Command</h1>
          <div className="flex items-center gap-2 mt-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className={`text-sm font-medium ${isConnected ? 'text-green-500' : 'text-red-500'}`}>
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-4 bg-zinc-900 px-6 py-3 rounded-lg border border-zinc-800">
          <Clock className="w-5 h-5 text-zinc-400" />
          <span className="text-xl font-mono text-amber-500">T = {time}</span>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: The Grid */}
        <div className="lg:col-span-2 bg-zinc-900 p-6 rounded-xl border border-zinc-800 shadow-2xl">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <MapPin className="w-5 h-5 text-amber-500" />
              Warehouse Grid (10×10) — Click to Dispatch
            </h2>
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <Target className="w-4 h-4 text-amber-500" />
              <span>Selected: <strong className="text-amber-400">{selectedAgent}</strong></span>
            </div>
          </div>
          <div className="aspect-square w-full max-w-2xl mx-auto">
            <div className="w-full h-full grid grid-cols-10 grid-rows-10 border border-zinc-700 bg-zinc-950">
              {gridCells.map((cell) => {
                const isRobotHere = Object.entries(robots).find(([id, pos]) => pos.x === cell.x && pos.y === cell.y);
                return (
                  <div
                    key={`${cell.x}-${cell.y}`}
                    onClick={() => !isRobotHere && handleCellClick(cell.x, cell.y)}
                    className={`border border-zinc-800/50 relative flex items-center justify-center cursor-pointer hover:bg-zinc-800 transition-colors ${isRobotHere ? 'cursor-default' : ''}`}
                    style={{ userSelect: 'none' }}
                  >
                    {isRobotHere && (
                      <div className="w-3/4 h-3/4 bg-amber-500 rounded-full shadow-[0_0_15px_rgba(245,158,11,0.6)] animate-pulse flex items-center justify-center">
                        <span className="text-[10px] font-bold text-zinc-900">
                          {isRobotHere[0].split('-')[1]}
                        </span>
                      </div>
                    )}
                    {!isRobotHere && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-2 h-2 rounded-full bg-zinc-700/50" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <div className="w-3 h-3 rounded-full bg-zinc-950 border border-zinc-800" />
              <span>Empty Cell (Clickable)</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <div className="w-3 h-3 rounded-full bg-amber-500/20 border-2 border-amber-400" />
              <span>AMR Position</span>
            </div>
          </div>
        </div>

        {/* Right Column: Metrics */}
        <div className="space-y-6">
          {/* Commander Controls */}
          <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
            <div className="flex items-center gap-3 mb-4">
              <Target className="w-6 h-6 text-amber-500" />
              <h2 className="text-xl font-semibold">Commander Controls</h2>
            </div>
            <div className="flex gap-2">
              {['AMR-1', 'AMR-2'].map((agent) => (
                <button
                  key={agent}
                  onClick={() => setSelectedAgent(agent)}
                  className={`flex-1 px-4 py-3 rounded-lg font-medium text-sm transition-all ${
                    selectedAgent === agent
                      ? 'bg-amber-500/20 border-2 border-amber-500 text-amber-300'
                      : 'bg-zinc-950 border border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-900'
                  }`}
                >
                  {agent}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
            <div className="flex items-center gap-3 mb-4">
              <Activity className="w-6 h-6 text-amber-500" />
              <h2 className="text-xl font-semibold">Active Fleet</h2>
            </div>
            <p className="text-4xl font-light mb-2">{Object.keys(robots).length}</p>
            <p className="text-sm text-zinc-400">AMRs currently connected</p>
          </div>

          <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-800">
            <div className="flex items-center gap-3 mb-4">
              <Cpu className="w-6 h-6 text-amber-500" />
              <h2 className="text-xl font-semibold">Live Telemetry</h2>
            </div>
            <div className="space-y-4">
              {Object.entries(robots).map(([id, pos]) => (
                <div key={id} className="bg-zinc-950 rounded-lg border border-zinc-800 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono font-medium text-amber-500">{id}</span>
                    <span className="font-mono text-zinc-300 text-sm">({pos.x}, {pos.y})</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-shrink-0">{getBatteryIcon(pos.battery)}</div>
                    <div className="flex-1 w-full bg-zinc-800 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-500 ${getBatteryColor(pos.battery)}`}
                        style={{ width: `${pos.battery}%` }}
                      ></div>
                    </div>
                    <span className={`font-mono text-sm w-12 text-right ${pos.battery > 50 ? 'text-green-400' : pos.battery > 20 ? 'text-amber-400' : 'text-red-400'}`}>
                      {pos.battery}%
                    </span>
                  </div>
                </div>
              ))}
              {Object.keys(robots).length === 0 && (
                <div className="text-zinc-500 text-sm italic">Waiting for telemetry...</div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}