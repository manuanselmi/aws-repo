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

function getRaceState(simStatus, stalled = false) {
  if (!simStatus) return 'idle'
  const pub  = Number(simStatus.events_published  ?? 0)
  const proc = Number(simStatus.events_processed ?? 0)
  if (simStatus.status === 'STOPPED') return 'stopped'
  if (simStatus.status === 'RUNNING') {
    if (pub > 0 && (proc >= pub || stalled)) return 'finished'
    if (proc > 0)                            return 'running'
    return 'starting'
  }
  return 'idle'
}

// Re-rank a live snapshot into a consistent classification so positions are
// always sequential 1..N (no duplicates/gaps, which happen because drivers are
// at different laps at the same wall-clock moment):
//   • active drivers ordered by their on-track position
//   • retired drivers (fell >2 laps behind the leader) sent to the back, ordered
//     by laps completed — mirrors how real DNFs are classified
function rankStates(states) {
  const laps = states.map(d => (d.current_lap != null ? Math.round(Number(d.current_lap)) : 0))
  const leaderLap = laps.length ? Math.max(...laps, 0) : 0
  const enriched = states.map(d => {
    const lap = d.current_lap != null ? Math.round(Number(d.current_lap)) : 0
    const hasPos = d.position != null
    const retired = leaderLap > 3 && (lap < leaderLap - 2 || !hasPos)
    return { d, lap, pos: hasPos ? Math.round(Number(d.position)) : 999, retired }
  })
  const active = enriched.filter(e => !e.retired)
    .sort((a, b) => a.pos - b.pos || a.d.driver_number - b.d.driver_number)
  const out = enriched.filter(e => e.retired)
    .sort((a, b) => b.lap - a.lap || a.d.driver_number - b.d.driver_number)
  const ordered = [...active, ...out].map((e, i) => ({
    ...e.d, position: i + 1, retired: e.retired, current_lap: e.lap,
  }))
  return { ordered, leaderLap }
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

// ─── Position-by-lap chart ─────────────────────────────────────────────────────
// posHistory shape: { [driver_id]: { [lap:number]: position } }. The x-axis is
// the lap number (race progress), NOT poll ticks — that keeps the lines clean and
// meaningful instead of jagged with flat runs and sudden multi-lap jumps.
function PositionChart({ posHistory, drivers, selectedId }) {
  const containerRef = useRef(null)
  const [size, setSize] = useState({ w: 900, h: 220 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => {
      const { width, height } = el.getBoundingClientRect()
      if (width > 10 && height > 10) setSize({ w: Math.round(width), h: Math.round(height) })
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const { w: VW, h: VH } = size
  const PAD = { t: 14, r: 52, b: 22, l: 32 }
  const W = VW - PAD.l - PAD.r
  const H = VH - PAD.t - PAD.b
  const N = Math.max(drivers.length, 2)

  // Highest lap recorded across all drivers defines the x domain.
  let maxLap = 1
  for (const m of Object.values(posHistory)) {
    for (const l of Object.keys(m)) { const n = +l; if (n > maxLap) maxLap = n }
  }

  const xOf = lap => PAD.l + ((lap - 1) / Math.max(maxLap - 1, 1)) * W
  const yOf = pos => PAD.t + ((pos - 1) / (N - 1)) * H

  const gridPositions = [1, 5, 10, 15, 20].filter(p => p <= N)

  const driverLines = drivers.map(d => {
    const m = posHistory[d.driver_id] || {}
    const laps = Object.keys(m).map(Number).sort((a, b) => a - b)
    if (!laps.length) return null
    const lastLap = laps[laps.length - 1]
    const lastPos = m[lastLap]
    const pts = laps.map(l => [xOf(l), yOf(m[l])])
    // Retirement comes straight from the ranked live data (single source of truth).
    const out = !!d.retired
    return {
      driver: d, color: tc(d.team_name), pts, lastLap, lastPos, out,
      endX: xOf(lastLap), endY: yOf(lastPos),
    }
  }).filter(Boolean)

  // Right-edge labels only for drivers still running at the end. Retired drivers
  // get a marker at the lap they dropped out (rendered below), so their label
  // never floats disconnected from where the line actually ends.
  const finishers = driverLines.filter(d => !d.out).sort((a, b) => a.lastPos - b.lastPos)
  let prevY = -999
  const labels = finishers.map(d => {
    const y = Math.max(yOf(d.lastPos), prevY + 12)
    prevY = y
    return { driver: d.driver, color: d.color, y }
  })

  const isEmpty = driverLines.length === 0
  const lapTicks = isEmpty
    ? []
    : [1, Math.round(maxLap / 2), maxLap].filter((v, i, a) => a.indexOf(v) === i && v >= 1)

  return (
    <div ref={containerRef} className="chart-plot">
      <svg width={VW} height={VH} style={{ display: 'block' }}>
        {/* Position grid lines */}
        {gridPositions.map(p => {
          const y = yOf(p)
          return (
            <g key={p}>
              <line
                x1={PAD.l} y1={y} x2={PAD.l + W} y2={y}
                stroke={p === 1 ? '#2a3f5f' : '#141d30'}
                strokeWidth={p === 1 ? 1.2 : 0.7}
              />
              <text x={PAD.l - 6} y={y + 3.5} textAnchor="end" fill="#3a4d6e" fontSize="9.5">P{p}</text>
            </g>
          )
        })}

        {/* Left axis border */}
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={PAD.t + H} stroke="#243350" strokeWidth="1" />

        {isEmpty ? (
          <text x={PAD.l + W / 2} y={PAD.t + H / 2 + 5} textAnchor="middle" fill="#344560" fontSize="13">
            Esperando posiciones…
          </text>
        ) : (
          <>
            {/* Lap axis ticks */}
            {lapTicks.map(l => (
              <text key={l} x={xOf(l)} y={PAD.t + H + 15} textAnchor="middle" fill="#3a4d6e" fontSize="9.5">
                V{l}
              </text>
            ))}

            {/* Driver lines — all solid; selected highlighted, retired dimmed */}
            {driverLines.map(({ driver, color, pts, out }) => {
              const sel = driver.driver_id === selectedId
              const op = selectedId == null ? (out ? 0.4 : 0.9) : (sel ? 1 : 0.18)
              return (
                <polyline
                  key={driver.driver_id}
                  points={pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')}
                  fill="none"
                  stroke={color}
                  strokeWidth={sel ? 3 : 1.8}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  opacity={op}
                />
              )
            })}

            {/* Retired drivers: hollow marker + OUT tag at the lap they dropped out */}
            {driverLines.filter(d => d.out).map(({ driver, color, endX, endY }) => (
              <g key={`out-${driver.driver_id}`}
                 opacity={selectedId == null || selectedId === driver.driver_id ? 1 : 0.3}>
                <circle cx={endX} cy={endY} r="3.2" fill="#06080f" stroke={color} strokeWidth="1.4" />
                <text x={endX + 6} y={endY + 3.3} fill={color} fontSize="9" fontWeight="700">
                  {driver.name_acronym}
                </text>
                <text x={endX + 6} y={endY + 12} fill="#5a6b86" fontSize="7.5" fontWeight="700" letterSpacing="0.5">
                  OUT
                </text>
              </g>
            ))}

            {/* Finishers: dot + de-overlapped label at the right edge */}
            {labels.map(({ driver, color, y }) => (
              <g key={driver.driver_id}>
                <circle cx={PAD.l + W} cy={y} r="3" fill={color} stroke="#06080f" strokeWidth="0.8" />
                <text x={PAD.l + W + 7} y={y + 3.5} fill={color} fontSize="9.5" fontWeight="700">
                  {driver.name_acronym}
                </text>
              </g>
            ))}
          </>
        )}
      </svg>
    </div>
  )
}

// ─── Stats panel ─────────────────────────────────────────────────────────────
function StatsPanel({ liveData, raceState, selectedDriver, driverDetail }) {
  const drivers = liveData?.live_states ?? []
  const leader  = drivers.find(d => d.position != null)

  const topSpeeds = [...drivers]
    .filter(d => d.speed != null)
    .sort((a, b) => b.speed - a.speed)
    .slice(0, 5)

  const fastestLap = [...drivers]
    .filter(d => d.lap_duration_sec != null)
    .sort((a, b) => a.lap_duration_sec - b.lap_duration_sec)[0] ?? null

  return (
    <div className="stats-panel">
      {leader && (
        <div className="scard">
          <div className="scard-title">LIDER</div>
          <div className="leader-main">
            <span className="leader-pos">1</span>
            <span className="team-dot" style={{ background: tc(leader.team_name), width: 9, height: 9 }} />
            <span className="leader-name">{leader.name_acronym ?? leader.full_name?.split(' ').pop()}</span>
            <span className="leader-num">#{leader.driver_number}</span>
          </div>
          <div className="leader-meta">
            <span>{leader.team_name}</span>
            {leader.speed != null && <span className="leader-speed">{Math.round(leader.speed)} km/h</span>}
          </div>
        </div>
      )}

      {topSpeeds.length > 0 && (
        <div className="scard">
          <div className="scard-title">TOP VELOCIDADES</div>
          {topSpeeds.map((d, i) => (
            <div key={d.driver_id} className="speed-row">
              <span className="speed-rank">{i + 1}</span>
              <span className="team-dot" style={{ background: tc(d.team_name) }} />
              <span className="speed-driver">{d.name_acronym ?? '—'}</span>
              <span style={{ fontSize: '.7rem', color: 'var(--muted)', marginLeft: 2 }}>#{d.driver_number}</span>
              <span className="speed-val">{Math.round(d.speed)}</span>
              <span className="speed-unit">km/h</span>
            </div>
          ))}
        </div>
      )}

      {fastestLap && (
        <div className="scard">
          <div className="scard-title">VUELTA MAS RAPIDA</div>
          <div className="fl-row">
            <span className="team-dot" style={{ background: tc(fastestLap.team_name) }} />
            <span className="fl-name">{fastestLap.name_acronym}</span>
            <span style={{ fontSize: '.7rem', color: 'var(--muted)' }}>#{fastestLap.driver_number}</span>
            <span className="fl-time">{fastestLap.lap_duration_sec?.toFixed(3)}s</span>
          </div>
        </div>
      )}

      {selectedDriver && driverDetail && (
        <div className="scard">
          <div className="scard-title">PILOTO SELECCIONADO</div>
          <div className="ddrv-header">
            <span className="team-dot" style={{ background: tc(selectedDriver.team_name), width: 9, height: 9 }} />
            <span className="ddrv-name">{driverDetail.full_name}</span>
            <span style={{ fontSize: '.75rem', color: 'var(--muted)', marginLeft: 4 }}>#{selectedDriver.driver_number}</span>
          </div>
          <div className="ddrv-grid">
            <div className="ddrv-stat">
              <div className="ddrv-val">{driverDetail.best_lap_duration_sec?.toFixed(3) ?? '—'}</div>
              <div className="ddrv-lbl">Mejor vuelta (s)</div>
            </div>
            <div className="ddrv-stat">
              <div className="ddrv-val">{driverDetail.max_speed_kmh?.toFixed(0) ?? '—'}</div>
              <div className="ddrv-lbl">Vel. máx km/h</div>
            </div>
            <div className="ddrv-stat">
              <div className="ddrv-val">{driverDetail.avg_speed_kmh?.toFixed(1) ?? '—'}</div>
              <div className="ddrv-lbl">Vel. media</div>
            </div>
            <div className="ddrv-stat">
              <div className="ddrv-val">{selectedDriver.position != null ? `P${Math.round(selectedDriver.position)}` : '—'}</div>
              <div className="ddrv-lbl">Posición live</div>
            </div>
          </div>
        </div>
      )}

      {!leader && (raceState === 'idle' || raceState === 'stopped') && (
        <div className="empty" style={{ height: 'auto', paddingTop: 30 }}>
          <div className="empty-icon" style={{ fontSize: '2rem', opacity: .3 }}>🏎</div>
          <p>Iniciá la simulación para ver estadísticas</p>
        </div>
      )}
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
  const [liveData, setLiveData]     = useState(null)
  const [simLoading, setSimLoading] = useState(false)
  const [simError, setSimError]     = useState('')
  const [lastTick, setLastTick]     = useState(null)

  const [selDriverId, setSelDriverId]   = useState(null)
  const [driverDetail, setDriverDetail] = useState(null)

  const [posChanges, setPosChanges] = useState({})
  const [toast, setToast]           = useState(null)

  // Position history: { driver_id: { lap: position } } — keyed by lap, not tick
  const posHistRef      = useRef({})

  const prevPos        = useRef({})
  const flashRef       = useRef(null)
  const toastTimer     = useRef(null)
  const prevRaceState  = useRef('idle')
  const lastProgress   = useRef({ count: -1, time: 0 })
  const isStartingRef  = useRef(false)  // true while handleStart API call is in-flight
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
  useEffect(() => {
    if (!session) return
    let alive = true
    async function loop() {
      while (alive) {
        try {
          const [sRes, lRes] = await Promise.allSettled([
            api.getSimulationStatus(session.session_key),
            api.getSimulationLive(session.session_key),
          ])
          if (!alive) break
          // Derive fresh status directly from API response — avoids stale closure
          const freshStatus  = sRes.status === 'fulfilled' ? sRes.value : null
          const freshProc    = Number(freshStatus?.events_processed ?? 0)
          const freshRunning = freshStatus?.status === 'RUNNING'
          const freshStopped = freshStatus?.status === 'STOPPED'

          if (sRes.status === 'fulfilled') setSimStatus(sRes.value)

          if (lRes.status === 'fulfilled') {
            const nd     = lRes.value
            const states = nd.live_states || []

            // Block while handleStart() API call is still in-flight, so the chart
            // isn't seeded with stale DynamoDB data from the previous simulation
            // before the backend has written the new state.
            if (isStartingRef.current) {
              // waiting for start API to finish
            } else if (freshRunning && freshProc > 0) {
              // ── Active simulation with confirmed events ──────────────────────
              const { ordered, leaderLap } = rankStates(states)

              const changes = {}
              ordered.forEach(d => {
                const prev = prevPos.current[d.driver_id]
                const curr = d.position
                if (prev != null && curr != null && prev !== curr)
                  changes[d.driver_id] = curr < prev ? 'up' : 'dn'
                prevPos.current[d.driver_id] = curr
              })
              if (Object.keys(changes).length) {
                setPosChanges(changes)
                clearTimeout(flashRef.current)
                flashRef.current = setTimeout(() => setPosChanges({}), 700)
              }

              // Record each driver's consistent position against the current race
              // progress (leader lap). Using a shared x-grid for all drivers keeps
              // every line continuous/smooth even when the sim skips laps between
              // polls; retired drivers stop being recorded so their line ends where
              // they dropped out.
              if (leaderLap >= 1) {
                ordered.forEach(d => {
                  if (!d.retired) {
                    const m = posHistRef.current[d.driver_id] || (posHistRef.current[d.driver_id] = {})
                    m[leaderLap] = d.position
                  }
                })
              }

              setLiveData({ ...nd, live_states: ordered })
              setLastTick(new Date())

            } else if (freshStopped) {
              // ── Simulation stopped — clear stale display data ────────────────
              setLiveData(null)
            }
          }
        } catch {}
        await new Promise(r => setTimeout(r, 800))
      }
    }
    loop()
    return () => { alive = false; clearTimeout(flashRef.current) }
  }, [session])

  // ── Driver detail ──
  useEffect(() => {
    if (!session || !selDriverId) { setDriverDetail(null); return }
    api.getDriverSummary(session.session_key, selDriverId)
      .then(setDriverDetail).catch(() => setDriverDetail(null))
  }, [session, selDriverId])

  function resetRaceState() {
    prevPos.current = {}
    posHistRef.current = {}
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
    setLiveData(null); setSimStatus(null)
    resetRaceState()
    // Block the polling loop from seeding the chart with stale data while the
    // API call is in-flight (the backend hasn't written the new state yet).
    isStartingRef.current = true
    try { await api.startSimulation(session.session_key, Number(duration)) }
    catch (e) { setSimError(e.error || 'Error iniciando') }
    finally {
      setSimLoading(false)
      isStartingRef.current = false
    }
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
    setSession(s || null); setSelDriverId(null); setDriverDetail(null)
    setSimStatus(null); setLiveData(null)
    resetRaceState()
  }

  const isRunning     = simStatus?.status === 'RUNNING'
  const drivers       = liveData?.live_states ?? []
  const hasLive       = drivers.some(d => d.position != null)
  const selDriverInfo = drivers.find(d => d.driver_id === selDriverId)

  // Leader's current lap (max among all drivers)
  const leaderLap = drivers.length > 0
    ? Math.round(Math.max(...drivers.map(d => d.current_lap ?? 0)))
    : 0

  const stateLabel = {
    idle: 'SIN SIMULACIÓN', starting: 'INICIANDO…',
    running: 'EN CARRERA',  finished: 'FINALIZADA', stopped: 'DETENIDA',
  }

  return (
    <div className="dashboard">

      {/* ── Topbar ── */}
      <div className="topbar">
        <span className="brand">🏁 F1</span>
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

      {/* ── Status bar ── */}
      <div className="statusbar">
        <span className={`sbadge ${
          raceState === 'running'  ? 'run' :
          raceState === 'finished' ? 'finished' :
          raceState === 'starting' ? 'starting' : 'stop'
        }`}>
          {stateLabel[raceState]}
        </span>
        {session && (
          <span className="sb-detail">{session.session_name} · {session.country_name} {session.year}</span>
        )}
        {lastTick && <span className="sb-time">{lastTick.toLocaleTimeString()}</span>}
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

      {/* ── Content ── */}
      <div className="content">

        {/* Left: position chart (top) + table (bottom) */}
        <div className="lb-panel">

          {/* Position time-series chart */}
          <div className="chart-section">
            <div className="chart-header">
              <span>POSICIONES EN CARRERA</span>
              {leaderLap > 0 && (raceState === 'running' || raceState === 'finished') && (
                <span className="lap-counter">VUELTA {leaderLap}</span>
              )}
            </div>
            {raceState === 'idle' || raceState === 'stopped' ? (
              <div className="tower-empty">
                {raceState === 'stopped' ? 'Simulación detenida' : 'Iniciá la simulación para ver el gráfico'}
              </div>
            ) : raceState === 'starting' ? (
              <div className="tower-empty tower-starting">
                <span className="starting-dot" />
                Esperando primeros eventos…
              </div>
            ) : (
              <PositionChart posHistory={posHistRef.current} drivers={drivers} selectedId={selDriverId} />
            )}
          </div>

          {/* Leaderboard table */}
          <div className="table-section">
            {!session ? (
              <div className="empty">
                <div className="empty-icon">🏎</div>
                <p>Ingestá una sesión para comenzar</p>
              </div>
            ) : !hasLive ? (
              <div className="empty">
                <div className="empty-icon">⏱</div>
                <p>{raceState === 'starting' ? 'Esperando primeros datos…' : 'Presioná ▶ Iniciar para arrancar'}</p>
              </div>
            ) : (
              <table className="lb-table">
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>POS</th>
                    <th style={{ width: 42 }}>#</th>
                    <th>PILOTO</th>
                    <th>EQUIPO</th>
                    <th style={{ width: 90, textAlign: 'right' }}>VEL km/h</th>
                  </tr>
                </thead>
                <tbody>
                  {drivers.map(d => {
                    const flash = posChanges[d.driver_id]
                    const isSel = d.driver_id === selDriverId
                    const last  = d.full_name?.split(' ').pop() ?? d.name_acronym ?? '—'
                    const first = d.full_name?.split(' ').slice(0, -1).join(' ') ?? ''
                    const pos   = d.position != null ? Math.round(d.position) : null
                    const pcls  = pos === 1 ? 'p1' : pos === 2 ? 'p2' : pos === 3 ? 'p3' : 'pn'
                    return (
                      <tr
                        key={d.driver_id}
                        className={[
                          d.position == null ? 'nodata' : '',
                          d.retired ? 'dnf-row' : '',
                          flash === 'up' ? 'up' : flash === 'dn' ? 'dn' : '',
                          isSel ? 'sel' : '',
                        ].filter(Boolean).join(' ')}
                        onClick={() => setSelDriverId(isSel ? null : d.driver_id)}
                      >
                        <td style={{ borderLeftColor: tc(d.team_name) }}>
                          <span className={`pos-badge ${d.retired ? 'pn' : pcls}`}>{pos ?? '—'}</span>
                        </td>
                        <td><span className="num-badge">{d.driver_number}</span></td>
                        <td>
                          <span className="drv-name">{last}</span>
                          <span className="drv-first">{first}</span>
                          {d.retired && <span className="dnf-tag">DNF</span>}
                        </td>
                        <td className="team-txt">
                          <span className="team-dot" style={{ background: tc(d.team_name) }} />
                          {d.team_name}
                        </td>
                        <td className="spd-txt">
                          {d.speed != null
                            ? <span>{Math.round(d.speed)}</span>
                            : <span className="spd-none">—</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right: stats */}
        <StatsPanel
          liveData={liveData}
          raceState={raceState}
          selectedDriver={selDriverInfo}
          driverDetail={driverDetail}
        />
      </div>
    </div>
  )
}
