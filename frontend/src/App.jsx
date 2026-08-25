import React, { useState, useEffect, useMemo } from 'react';
import { useWebSocket } from 'react-use-websocket';
import { Activity, Cpu, Clock, Bot, MapPin, Radio } from 'lucide-react';

const GRID_SIZE = 10;
const CELL_SIZE = 40;

function App() {
  const [robots, setRobots] = useState({});
  const [time, setTime] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  const { lastJsonMessage, readyState } = useWebSocket('ws://localhost:8000/ws', {
    shouldReconnect: () => true,
    reconnectInterval: 3000,
    onOpen: () => setConnectionStatus('connected'),
    onClose: () => setConnectionStatus('disconnected'),
    onError: () => setConnectionStatus('error'),
  });

  useEffect(() => {
    if (lastJsonMessage) {
      const msg = lastJsonMessage;
      if (typeof msg.time === 'number' && !msg.agent_id) {
        setTime(msg.time);
      } else if (msg.agent_id && typeof msg.x === 'number' && typeof msg.y === 'number') {
        setRobots(prev => ({
          ...prev,
          [msg.agent_id]: { x: msg.x, y: msg.y, time: msg.time }
        }));
      }
    }
  }, [lastJsonMessage]);

  const robotEntries = useMemo(() => Object.entries(robots), [robots]);
  const activeRobots = robotEntries.length;

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <Radio className="w-4 h-4 text-green-400" />;
      case 'connecting': return <Activity className="w-4 h-4 text-amber-400 animate-pulse" />;
      case 'error': return <Activity className="w-4 h-4 text-red-400" />;
      default: return <Activity className="w-4 h-4 text-zinc-500" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#111111] text-[#FDFBF7] p-6">
      <header className="flex items-center justify-between mb-8 px-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-zinc-900 rounded-xl border border-zinc-800">
            <Cpu className="w-8 h-8 text-amber-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AMR Fleet Command</h1>
            <p className="text-zinc-400 text-sm">Real-time Multi-Robot Coordination</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-lg border border-zinc-800">
            {getConnectionIcon()}
            <span className="text-sm font-medium capitalize">{connectionStatus}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-lg border border-zinc-800">
            <Clock className="w-4 h-4 text-amber-400" />
            <span className="font-mono text-lg tabular-nums">T+{time}</span>
          </div>
        </div>
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6 max-w-7xl mx-auto">
        <section className="bg-zinc-900/50 rounded-2xl border border-zinc-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <MapPin className="w-5 h-5 text-amber-400" />
              Warehouse Grid (10×10)
            </h2>
            <span className="text-zinc-400 text-sm">{activeRobots} robots active</span>
          </div>
          <div className="relative overflow-auto">
            <div
              className="grid gap-0.5"
              style={{
                gridTemplateColumns: `repeat(${GRID_SIZE}, ${CELL_SIZE}px)`,
                gridTemplateRows: `repeat(${GRID_SIZE}, ${CELL_SIZE}px)`,
                width: 'fit-content'
              }}
            >
              {Array.from({ length: GRID_SIZE * GRID_SIZE }, (_, i) => {
                const x = i % GRID_SIZE;
                const y = Math.floor(i / GRID_SIZE);
                const robotAtCell = robotEntries.find(([_, pos]) => pos.x === x && pos.y === GRID_SIZE - 1 - y);
                return (
                  <div
                    key={`${x}-${y}`}
                    className="relative border border-zinc-800 bg-zinc-950 transition-colors hover:border-zinc-700"
                    style={{ width: CELL_SIZE, height: CELL_SIZE }}
                  >
                    {robotAtCell && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-8 h-8 rounded-full bg-amber-400/20 border-2 border-amber-400 flex items-center justify-center animate-pulse">
                          <Bot className="w-4 h-4 text-amber-300" />
                        </div>
                      </div>
                    )}
                    <div className="absolute bottom-0 right-0 text-[8px] text-zinc-700 pr-1 pb-0.5 font-mono">
                      {x},{GRID_SIZE - 1 - y}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <div className="w-3 h-3 rounded-full bg-zinc-950 border border-zinc-800" />
              <span>Empty Cell</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <div className="w-3 h-3 rounded-full bg-amber-400/20 border-2 border-amber-400" />
              <span>AMR Position</span>
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="bg-zinc-900/50 rounded-2xl border border-zinc-800 p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Bot className="w-5 h-5 text-amber-400" />
              Robot Registry
            </h2>
            <div className="space-y-3 max-h-64 overflow-y-auto">
              {robotEntries.length === 0 ? (
                <p className="text-zinc-500 text-center py-8">No robots connected</p>
              ) : (
                robotEntries.map(([id, pos]) => (
                  <div
                    key={id}
                    className="flex items-center justify-between p-3 bg-zinc-950 rounded-xl border border-zinc-800 hover:border-zinc-700 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-amber-400/10 border border-amber-400/30 flex items-center justify-center">
                        <Bot className="w-5 h-5 text-amber-400" />
                      </div>
                      <div>
                        <p className="font-mono font-medium">{id}</p>
                        <p className="text-xs text-zinc-400">Pos: ({pos.x}, {pos.y})</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-zinc-500">Last Update</p>
                      <p className="font-mono text-sm text-amber-300">T+{pos.time ?? time}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="bg-zinc-900/50 rounded-2xl border border-zinc-800 p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-amber-400" />
              System Metrics
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <MetricCard
                label="Active Robots"
                value={activeRobots}
                icon={<Bot className="w-5 h-5" />}
                color="amber"
              />
              <MetricCard
                label="Grid Coverage"
                value={`${((activeRobots / (GRID_SIZE * GRID_SIZE)) * 100).toFixed(1)}%`}
                icon={<MapPin className="w-5 h-5" />}
                color="emerald"
              />
              <MetricCard
                label="Time Tick"
                value={time}
                icon={<Clock className="w-5 h-5" />}
                color="sky"
              />
              <MetricCard
                label="Connection"
                value={connectionStatus === 'connected' ? 'Live' : 'Offline'}
                icon={<Radio className="w-5 h-5" />}
                color={connectionStatus === 'connected' ? 'green' : 'red'}
              />
            </div>
          </section>

          <section className="bg-zinc-900/50 rounded-2xl border border-zinc-800 p-6">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Radio className="w-5 h-5 text-amber-400" />
              Message Log
            </h2>
            <div className="h-40 overflow-y-auto bg-zinc-950 rounded-xl border border-zinc-800 p-3 font-mono text-xs text-zinc-300">
              {lastJsonMessage ? (
                <pre className="whitespace-pre-wrap">{JSON.stringify(lastJsonMessage, null, 2)}</pre>
              ) : (
                <p className="text-zinc-500">Waiting for telemetry...</p>
              )}
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}

function MetricCard({ label, value, icon, color }) {
  const colors = {
    amber: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    emerald: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    sky: 'bg-sky-500/10 border-sky-500/30 text-sky-400',
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
  };

  return (
    <div className={`p-4 rounded-xl border ${colors[color] || colors.amber}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-zinc-400 uppercase tracking-wide">{label}</span>
        <div className="p-1.5 bg-white/5 rounded-lg">{icon}</div>
      </div>
      <p className="text-2xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

export default App;