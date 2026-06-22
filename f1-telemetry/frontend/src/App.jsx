import { useState, useEffect, useRef } from 'react'
import { api } from './api.js'

const TEAM_COLORS = {
  'Red Bull Racing': '#3671C6',
  'Ferrari':         '#E8002D',
  'Mercedes':        '#00D2BE',
  'McLaren':         '#FF8000',
  'Aston Martin':    '#229971',
  'Alpine':          '#FF87BC',
  'Williams':        '#64C4FF',
  'AlphaTauri':      '#6692FF',
  'Alfa Romeo':      '#C92D4B',
  'Haas F1 Team':    '#B6BABD',
}
const tc = name => TEAM_COLORS[name] || '#4b6080'

// Grafana base URL for the embedded metrics panels (override with VITE_GRAFANA_URL)
const GRAFANA_URL = import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3001'

function getRaceState(simStatus, stalled = false) {
  if (!simStatus) return 'idle'
  const pub  = Number(simStatus.events_published  ?? 0)
  const proc = Number(simStatus.events_processed ?? 0)
  if (simStatus.status === 'STOPPED')  return 'stopped'
  if (simStatus.status === 'FINISHED') return 'finished'
  if (simStatus.status === 'RUNNING') {
    if (pub > 0 && (proc >= pub || stalled)) return 'finished'
    if (proc > 0)                            return 'running'
    return 'starting'
  }
  return 'idle'
}

// ─── Login ───────────────────────────────────────────────────────────────────
function Login({ onLogin }) {
  const [u, setU] = useState('admin')
  const [p, setP] = useState('admin')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault(); setErr(''); setLoading(true)
    try {
      const data = await api.login(u, p)
      localStorage.setItem('f1_token', data.access_token)
      onLogin(u)
    } catch { setErr('Credenciales incorrectas') }
    finally { setLoading(false) }
  }

  return (
    <div className="login-wrap">
      <div className="login-box">
        <div className="login-logo">🏁</div>
        <h1 className="login-title">F1 TELEMETRY</h1>
        <form onSubmit={submit}>
          <div className="field"><label>Usuario</label><input value={u} onChange={e=>setU(e.target.value)} required /></div>
          <div className="field"><label>Contraseña</label><input type="password" value={p} onChange={e=>setP(e.target.value)} required /></div>
          {err && <div className="msg msg-error">{err}</div>}
          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>{loading?'…':'Ingresar'}</button>
        </form>
      </div>
    </div>
  )
}

// ─── Race view (embedded Grafana panels) ──────────────────────────────────────
// Renders the same Grafana dashboard panels inside the app via Grafana's
// "d-solo" embed URLs (one panel per iframe). Prometheus is the data source, so
// these update live (refresh=5s) alongside the race.
function RaceView({ grafanaUrl, simStatus, sessionKey }) {
  // Anchor the panels' time window to the START of the current run instead of a
  // rolling "now-30m". Prometheus keeps history across runs, so a fixed window
  // would pile up every past simulation (and any stale series). Using
  // `from=<started_at>` makes every panel show ONLY the current race, and it
  // resets automatically when a new run writes a fresh started_at.
  const running   = simStatus?.status === 'RUNNING'
  const startedMs = simStatus?.started_at ? Date.parse(simStatus.started_at) : null
  const endMs     = simStatus?.updated_at ? Date.parse(simStatus.updated_at) : null
  const from = startedMs ? startedMs - 5000 : 'now-5m'
  // While running, track "now" and auto-refresh. Once the race is over
  // (FINISHED/STOPPED) freeze the window just past the last update so the panels
  // stop scrolling. The buffer must exceed Prometheus' scrape interval (10s):
  // the final laps are processed in the last seconds, so the scrape capturing the
  // final count lands AFTER updated_at — a too-small buffer would freeze the
  // panel on an earlier scrape (e.g. showing 1117 instead of the full 1364).
  const to      = running ? 'now' : (endMs ? endMs + 20000 : 'now')
  const refresh = running ? '&refresh=5s' : ''
  // Scope every panel to the current session, otherwise Prometheus series from
  // other sessions you've run show up too (duplicated drivers/positions).
  const sessionVar = sessionKey != null ? `&var-session=${sessionKey}` : ''
  const base =
    `${grafanaUrl}/d-solo/f1-telemetry-main/f1-telemetry` +
    `?orgId=1&theme=dark&from=${from}&to=${to}${refresh}${sessionVar}`

  const panels = [
    { id: 1, label: 'Estado simulación',        cls: 'm-sm' },
    { id: 2, label: 'Eventos publicados',       cls: 'm-sm' },
    { id: 3, label: 'Eventos procesados',       cls: 'm-sm' },
    { id: 7, label: 'Posiciones en la carrera', cls: 'm-chart' },
    { id: 5, label: 'Clasificación',            cls: 'm-table' },
    { id: 6, label: 'Velocidad en el tiempo',   cls: 'm-lg' },
    { id: 4, label: 'Velocidad pilotos',        cls: 'm-md' },
  ]

  return (
    <div className="metrics-view">
      <div className="metrics-grid">
        {panels.map(p => (
          <div key={p.id} className={`metric-card ${p.cls}`}>
            <iframe title={p.label} src={`${base}&panelId=${p.id}`} />
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── App root ────────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(() => localStorage.getItem('f1_user'))
  function handleLogin(u) { localStorage.setItem('f1_user', u); setUser(u) }
  function handleLogout() {
    localStorage.removeItem('f1_token'); localStorage.removeItem('f1_user'); setUser(null)
  }
  if (!user) return <Login onLogin={handleLogin} />
  return <Dashboard user={user} onLogout={handleLogout} />
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
function Dashboard({ user, onLogout }) {
  const [sessions, setSessions]           = useState([])
  const [session, setSession]             = useState(null)
  const [ingestKey, setIngestKey]         = useState('')
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestMsg, setIngestMsg]         = useState(null)

  const [duration, setDuration]     = useState('120')
  const [simStatus, setSimStatus]   = useState(null)
  const [simLoading, setSimLoading] = useState(false)
  const [simError, setSimError]     = useState('')
  const [toast, setToast]           = useState(null)

  const toastTimer     = useRef(null)
  const prevRaceState  = useRef('idle')
  const lastProgress   = useRef({ count: -1, time: 0 })
  const finishedRef    = useRef(false)  // sticky: once finished, don't bounce back

  const proc = Number(simStatus?.events_processed ?? 0)
  if (simStatus?.status === 'RUNNING' && proc !== lastProgress.current.count) {
    lastProgress.current = { count: proc, time: Date.now() }
  }
  const stalledMs = simStatus?.status === 'RUNNING' && lastProgress.current.count > 0
    ? Date.now() - lastProgress.current.time
    : 0
  const stalled = stalledMs > 15000

  let raceState = getRaceState(simStatus, stalled)
  // Finish is sticky: near the end the gaps between laps grow, so progress can
  // stall and then resume, which would bounce running⇄finished and re-fire the
  // toast. Once finished, stay finished until the next run resets it.
  if (raceState === 'finished') finishedRef.current = true
  else if (finishedRef.current && simStatus?.status === 'RUNNING') raceState = 'finished'

  // ── Race state transitions ──
  useEffect(() => {
    const prev = prevRaceState.current
    if (prev === raceState) return
    prevRaceState.current = raceState
    clearTimeout(toastTimer.current)
    if (raceState === 'running' && prev !== 'running') {
      setToast({ type: 'start', msg: 'CARRERA EN CURSO' })
      toastTimer.current = setTimeout(() => setToast(null), 3500)
    } else if (raceState === 'finished') {
      setToast({ type: 'finish', msg: 'CARRERA FINALIZADA' })
    } else if (raceState === 'stopped' && prev === 'running') {
      setToast({ type: 'stop', msg: 'SIMULACION DETENIDA' })
      toastTimer.current = setTimeout(() => setToast(null), 2500)
    }
  }, [raceState])

  // ── Load sessions ──
  useEffect(() => {
    api.getSessions()
      .then(d => {
        const list = d.sessions || []
        setSessions(list)
        if (list.length) setSession(list[0])
      })
      .catch(() => {})
  }, [])

  // ── Polling loop ──
  // Only the simulation status is needed now (status badge + toasts). All the
  // live telemetry visualisation lives in the embedded Grafana panels, which
  // read straight from Prometheus.
  useEffect(() => {
    if (!session) return
    let alive = true
    async function loop() {
      while (alive) {
        try {
          const sRes = await api.getSimulationStatus(session.session_key)
          if (!alive) break
          setSimStatus(sRes)
        } catch { /* 404 before the first run is expected */ }
        await new Promise(r => setTimeout(r, 1500))
      }
    }
    loop()
    return () => { alive = false }
  }, [session])

  function resetRaceState() {
    finishedRef.current = false
    lastProgress.current = { count: -1, time: 0 }
    setToast(null)
    clearTimeout(toastTimer.current)
    prevRaceState.current = 'idle'
  }

  // ── Handlers ──
  async function handleIngest() {
    if (!ingestKey) return
    setIngestMsg(null); setIngestLoading(true)
    try {
      const data = await api.ingestSession(Number(ingestKey), false)
      setIngestMsg({ type: 'success', text: `Sesión ${ingestKey} ingestada — ${data.drivers_count} pilotos, ${data.laps_count} vueltas` })
      const updated = await api.getSessions()
      const list = updated.sessions || []
      setSessions(list)
      const found = list.find(s => s.session_key === Number(ingestKey))
      if (found) { setSession(found); setIngestKey('') }
    } catch (e) {
      setIngestMsg({ type: e.status === 409 ? 'info' : 'error', text: e.error || (e.status === 409 ? 'La sesión ya existe.' : 'Error ingestando') })
    } finally { setIngestLoading(false) }
  }

  async function handleStart() {
    if (!session) return
    setSimError(''); setSimLoading(true)
    setSimStatus(null)
    resetRaceState()
    try { await api.startSimulation(session.session_key, Number(duration)) }
    catch (e) { setSimError(e.error || 'Error iniciando') }
    finally { setSimLoading(false) }
  }

  async function handleStop() {
    if (!session) return
    setSimError('')
    try {
      await api.stopSimulation(session.session_key)
      setSimStatus(p => p ? { ...p, status: 'STOPPED' } : null)
    } catch (e) { setSimError(e.error || 'Error deteniendo') }
  }

  function changeSession(e) {
    const sk = Number(e.target.value)
    const s = sessions.find(x => x.session_key === sk)
    setSession(s || null)
    setSimStatus(null)
    resetRaceState()
  }

  const isRunning = simStatus?.status === 'RUNNING'

  return (
    <div className="dashboard">

      {/* ── Topbar ── */}
      <div className="topbar">
        <span className="brand">🏁 F1 · CARRERA EN VIVO</span>
        <div className="sep" />

        {sessions.length > 0
          ? <select className="session-select" value={session?.session_key ?? ''} onChange={changeSession}>
              {sessions.map(s => (
                <option key={s.session_key} value={s.session_key}>
                  {s.session_name} · {s.country_name} {s.year}
                </option>
              ))}
            </select>
          : <span style={{ fontSize: '.75rem', color: 'var(--muted)' }}>Sin sesiones</span>
        }

        <input
          className="ingest-input" type="number" placeholder="Session key"
          value={ingestKey} onChange={e => setIngestKey(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleIngest()}
        />
        <button className="btn btn-icon" onClick={handleIngest} disabled={ingestLoading || !ingestKey}>
          {ingestLoading ? '…' : '+ Ingestar'}
        </button>

        <div className="sep" />

        <span className="dur-label">Duración</span>
        <input
          className="dur-input" type="number" min="10" value={duration}
          onChange={e => setDuration(e.target.value)} disabled={isRunning}
        />
        <span className="dur-label">s</span>
        <button className="btn btn-success" onClick={handleStart} disabled={simLoading || isRunning || !session}>
          {simLoading ? '…' : '▶ Iniciar'}
        </button>
        <button className="btn btn-danger" onClick={handleStop} disabled={!isRunning}>
          ⏹ Detener
        </button>

        {simError && <span className="topbar-err">{simError}</span>}
        <button className="topbar-user" onClick={onLogout}>{user} · Salir</button>
      </div>

      {/* ── Ingest message ── */}
      {ingestMsg && (
        <div className="ingest-bar">
          <span className={`msg msg-${ingestMsg.type}`} style={{ margin: 0 }}>{ingestMsg.text}</span>
          <button className="btn btn-icon" style={{ marginLeft: 'auto' }} onClick={() => setIngestMsg(null)}>✕</button>
        </div>
      )}

      {/* ── Race toast ── */}
      {toast && (
        <div className={`race-toast toast-${toast.type}`}>
          {toast.type === 'start' ? '🏁' : toast.type === 'finish' ? '🏆' : '⏹'}&nbsp;{toast.msg}
          {(toast.type === 'finish' || toast.type === 'stop') && (
            <button className="toast-close" onClick={() => setToast(null)}>✕</button>
          )}
        </div>
      )}

      {/* ── Content (embedded Grafana) ── */}
      <RaceView grafanaUrl={GRAFANA_URL} simStatus={simStatus} sessionKey={session?.session_key} />
    </div>
  )
}
