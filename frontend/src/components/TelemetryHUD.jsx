import React from 'react';
import {
  Activity,
  Gauge,
  CheckCircle2,
  ShieldCheck,
  Unlock,
  Cpu,
  HeartPulse,
  AlertTriangle,
} from 'lucide-react';

export const TelemetryHUD = React.memo(function TelemetryHUD({
  metrics,
  activeCount = 0,
  offlineCount = 0,
  isConnected = false,
}) {
  const utilizationNum = metrics?.fleet_utilization !== undefined ? Number(metrics.fleet_utilization) : null;
  const utilizationStr = utilizationNum !== null ? `${utilizationNum.toFixed(1)}%` : '--';

  const tasksCompleted = metrics?.tasks_completed !== undefined ? metrics.tasks_completed : '--';
  const successRate = metrics?.task_success_rate !== undefined
    ? `${Number(metrics.task_success_rate).toFixed(1)}%`
    : '--';

  const proactive = metrics?.proactive_conflicts_avoided ?? 0;
  const reactive = metrics?.reactive_stops_triggered ?? 0;
  const hasConflictMetrics =
    metrics?.proactive_conflicts_avoided !== undefined ||
    metrics?.reactive_stops_triggered !== undefined;
  const totalAvoided = hasConflictMetrics ? proactive + reactive : '--';

  const deadlocksResolved = metrics?.deadlocks_resolved ?? 0;
  const deadlocksDetected = metrics?.deadlocks_detected ?? 0;
  const hasDeadlockMetrics = metrics?.deadlocks_detected !== undefined;
  const deadlocksDisplay = hasDeadlockMetrics ? `${deadlocksResolved} / ${deadlocksDetected}` : '--';

  const planningLatency =
    metrics?.avg_planning_time_ms !== undefined
      ? `${Number(metrics.avg_planning_time_ms).toFixed(2)} ms`
      : '--';

  const silentFailures = metrics?.silent_failures_detected ?? 0;
  const tasksReassigned = metrics?.tasks_reassigned ?? 0;

  return (
    <aside
      aria-label="Telemetry HUD"
      className="absolute top-4 right-4 z-10 w-72 bg-zinc-950/85 backdrop-blur-md border border-zinc-800/80 rounded-xl p-3 text-xs font-mono shadow-2xl text-zinc-200 select-none pointer-events-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2.5">
        <div className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="font-bold tracking-wider text-[11px] text-zinc-100 uppercase">
            Telemetry HUD
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)] animate-pulse' : 'bg-rose-500'
            }`}
          />
          <span className="text-[10px] text-zinc-400 tracking-tight">
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Vitality Summary Bar */}
      <div className="mb-2.5 bg-zinc-900/90 border border-zinc-800/60 rounded-lg p-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <HeartPulse className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[10px] text-zinc-400 uppercase font-semibold">Vitality:</span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-emerald-400 font-bold">
            {activeCount} <span className="text-[9px] text-zinc-400 font-normal">Active</span>
          </span>
          <span className="text-zinc-600">|</span>
          <span
            className={`font-bold flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors ${
              offlineCount > 0
                ? 'bg-rose-950/70 text-rose-400 border border-rose-800/70 shadow-[0_0_8px_rgba(244,63,94,0.3)] animate-pulse'
                : 'text-zinc-500'
            }`}
          >
            {offlineCount > 0 && <AlertTriangle className="w-2.5 h-2.5 text-rose-400" />}
            <span>{offlineCount}</span>
            <span className="text-[9px] font-normal">Offline</span>
          </span>
        </div>
      </div>

      {/* Grid of Key Telemetry Metrics */}
      <div className="space-y-2">
        {/* Fleet Utilization */}
        <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-2">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Gauge className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[10px] uppercase">Fleet Utilization</span>
            </div>
            <span className="font-bold text-cyan-300 tabular-nums">{utilizationStr}</span>
          </div>
          <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, utilizationNum ?? 0))}%` }}
            />
          </div>
        </div>

        {/* 2-Column Metrics */}
        <div className="grid grid-cols-2 gap-1.5">
          {/* Tasks Completed */}
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-2 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-zinc-400 mb-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="text-[9px] uppercase tracking-tight">Tasks</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-bold text-emerald-300 tabular-nums">{tasksCompleted}</span>
              <span className="text-[9px] text-zinc-400 tabular-nums font-normal" title="Success Rate">
                {successRate}
              </span>
            </div>
          </div>

          {/* Conflicts Avoided */}
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-2 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-zinc-400 mb-1">
              <ShieldCheck className="w-3 h-3 text-amber-400" />
              <span className="text-[9px] uppercase tracking-tight">Conflicts</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-bold text-amber-300 tabular-nums">{totalAvoided}</span>
              <span className="text-[8px] text-zinc-400 tabular-nums" title="Proactive / Reactive">
                {hasConflictMetrics ? `${proactive}p/${reactive}r` : '--'}
              </span>
            </div>
          </div>

          {/* Deadlocks Cleared */}
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-2 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-zinc-400 mb-1">
              <Unlock className="w-3 h-3 text-violet-400" />
              <span className="text-[9px] uppercase tracking-tight">Deadlocks</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-bold text-violet-300 tabular-nums">
                {deadlocksDisplay}
              </span>
              <span className="text-[8px] text-zinc-500 uppercase">res/det</span>
            </div>
          </div>

          {/* Planning Latency */}
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-lg p-2 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-zinc-400 mb-1">
              <Cpu className="w-3 h-3 text-sky-400" />
              <span className="text-[9px] uppercase tracking-tight">Plan Latency</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-xs font-bold text-sky-300 tabular-nums">{planningLatency}</span>
            </div>
          </div>
        </div>

        {/* Fault Resilience Row (only when actual stranded robots exist) */}
        {(offlineCount > 0 && silentFailures > 0) && (
          <div className="bg-rose-950/30 border border-rose-900/40 rounded-lg p-1.5 flex items-center justify-between text-[10px]">
            <span className="text-rose-400 font-semibold flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Silent Failures:
            </span>
            <div className="flex items-center gap-2">
              <span className="text-rose-300 tabular-nums font-bold">{silentFailures} detected</span>
              <span className="text-zinc-600">•</span>
              <span className="text-amber-300 tabular-nums font-bold">{tasksReassigned} salvaged</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
});

export default TelemetryHUD;
