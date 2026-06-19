import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './index.css'

// Types
interface Metrics {
  ts: string
  latency_ms: number
  packet_loss_pct: number
  jitter_ms: number
  tcp_latency_ms: number
  bandwidth_utilization_pct: number
  interfaces: Record<string, any>
  netstat: Record<string, number>
  routes: Array<any>
  sensor_health: Record<string, boolean>
}

interface HealthPing {
  state: string
  trigger_streak: number
  dry_run: boolean
}

// API Client
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 5000,
})

async function rpcCall(method: string, params: any = {}, token: string = 'local-dev-token') {
  try {
    // Simulate Unix socket RPC via HTTP for UI
    const response = await api.post('/api/rpc', {
      id: '1',
      method,
      params,
      session_token: token,
    })
    return response.data
  } catch (error) {
    console.error('RPC Error:', error)
    return null
  }
}

// Components
function Header({ state, healthScore }: { state: string; healthScore: number }) {
  const stateColor = state === 'MONITORING' ? '#00cc00' : state === 'TRIGGERED' ? '#ffaa00' : '#cc0000'

  return (
    <div className="header">
      <div className="header-title">⚡ JFP PARADOX</div>
      <div className="header-status">
        <div className={`status-indicator ${state === 'MONITORING' ? '' : 'warning'}`}></div>
        <div className="status-text">State: {state} | Health: {healthScore}/100</div>
      </div>
    </div>
  )
}

function MetricsPanel({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) return <div className="panel">Loading...</div>

  const getHealthColor = (score: number) => {
    if (score >= 70) return '#00cc00'
    if (score >= 40) return '#ffaa00'
    return '#cc0000'
  }

  const healthScore = metrics.latency_ms > 300 ? 20 : metrics.latency_ms > 200 ? 40 : 100

  return (
    <div className="panel">
      <div className="panel-header">📊 Network Metrics</div>
      <div className="panel-content">
        <div className="metric-row">
          <span className="metric-label">Latency:</span>
          <span className="metric-value">{metrics.latency_ms.toFixed(1)}<span className="metric-unit">ms</span></span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Packet Loss:</span>
          <span className="metric-value">{metrics.packet_loss_pct.toFixed(2)}<span className="metric-unit">%</span></span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Jitter:</span>
          <span className="metric-value">{metrics.jitter_ms.toFixed(1)}<span className="metric-unit">ms</span></span>
        </div>
        <div className="metric-row">
          <span className="metric-label">TCP Latency:</span>
          <span className="metric-value">{metrics.tcp_latency_ms.toFixed(1)}<span className="metric-unit">ms</span></span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Bandwidth:</span>
          <span className="metric-value">{metrics.bandwidth_utilization_pct.toFixed(1)}<span className="metric-unit">%</span></span>
        </div>
      </div>
    </div>
  )
}

function StatePanel({ state, healthScore }: { state: string; healthScore: number }) {
  const getBadgeClass = (s: string) => {
    if (s === 'MONITORING') return 'monitoring'
    if (s === 'TRIGGERED') return 'triggered'
    if (s === 'INTERVENTION') return 'intervention'
    if (s === 'COOLDOWN') return 'cooldown'
    return ''
  }

  return (
    <div className="panel">
      <div className="panel-header">🔄 System State</div>
      <div className="panel-content">
        <div style={{ marginBottom: '16px' }}>
          <div className="metric-label">Current State</div>
          <div className={`state-badge ${getBadgeClass(state)}`}>{state}</div>
        </div>
        <div>
          <div className="metric-label">Health Score</div>
          <div className="health-gauge">
            <div className="health-gauge-inner">{healthScore}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ControlPanel({ onPanic }: { onPanic: () => void }) {
  return (
    <div className="panel">
      <div className="panel-header">🎮 Controls</div>
      <div className="panel-content">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button onClick={() => alert('Benchmark started (DRY-RUN)')}>▶️ Start Benchmark</button>
          <button onClick={() => alert('Profile set to performance')} style={{ backgroundColor: '#0066cc' }}>⚙️ Set Profile</button>
          <button onClick={onPanic} className="danger">🛑 Panic Stop</button>
        </div>
      </div>
    </div>
  )
}

function EventLog({ events }: { events: any[] }) {
  return (
    <div className="panel">
      <div className="panel-header">📋 Event Log</div>
      <div className="event-log">
        {events.length === 0 ? (
          <div className="event-item">
            <span className="event-detail">No events yet...</span>
          </div>
        ) : (
          events.map((event, i) => (
            <div key={i} className="event-item">
              <span className="event-time">{event.ts?.slice(11, 19) || '??:??:??'}</span>
              <span className="event-type">{event.event}</span>
              <span className="event-detail">
                {event.state && `state=${event.state}`}
                {event.health_score && ` health=${event.health_score}`}
                {event.reason && ` ${event.reason}`}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Main App
export default function App() {
  const [state, setState] = useState('MONITORING')
  const [healthScore, setHealthScore] = useState(100)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [events, setEvents] = useState<any[]>([])

  // Fetch data periodically
  useEffect(() => {
    const interval = setInterval(async () => {
      // Simulate data fetching (in real app, would call RPC)
      const newMetrics = {
        ts: new Date().toISOString(),
        latency_ms: Math.random() * 200,
        packet_loss_pct: Math.random() * 2,
        jitter_ms: Math.random() * 10,
        tcp_latency_ms: Math.random() * 250,
        bandwidth_utilization_pct: 30 + Math.random() * 50,
        interfaces: {},
        netstat: {},
        routes: [],
        sensor_health: { ping_ok: true, tcp_ok: true, interfaces_ok: true, routes_ok: true },
      }

      setMetrics(newMetrics)

      // Simulate state changes
      if (newMetrics.latency_ms > 150) {
        setState('TRIGGERED')
        setHealthScore(40)
      } else {
        setState('MONITORING')
        setHealthScore(100)
      }

      // Add event
      setEvents(prev => [...prev.slice(-9), {
        ts: newMetrics.ts,
        event: newMetrics.latency_ms > 150 ? 'TRIGGERED' : 'MONITORING',
        state: newMetrics.latency_ms > 150 ? 'TRIGGERED' : 'MONITORING',
        health_score: newMetrics.latency_ms > 150 ? 40 : 100,
      }])
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Header state={state} healthScore={healthScore} />
      <div className="grid-container" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        <StatePanel state={state} healthScore={healthScore} />
        <MetricsPanel metrics={metrics} />
        <ControlPanel onPanic={() => alert('Panic stop executed (DRY-RUN)')} />
        <EventLog events={events} />
      </div>
    </div>
  )
}
