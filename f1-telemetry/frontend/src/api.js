const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'

function getToken() {
  return localStorage.getItem('f1_token')
}

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw { status: res.status, ...data }
  return data
}

export const api = {
  login: (username, password) =>
    request('POST', '/login', { username, password }),

  getSessions: () => request('GET', '/sessions'),

  ingestSession: (sessionKey, force = false) =>
    request('POST', `/sessions/${sessionKey}/ingest`, force ? { force: true } : {}),

  getDrivers: (sessionKey) =>
    request('GET', `/sessions/${sessionKey}/drivers`),

  getDriverSummary: (sessionKey, driverId) =>
    request('GET', `/sessions/${sessionKey}/drivers/${driverId}/summary`),

  getDriverLaps: (sessionKey, driverId) =>
    request('GET', `/sessions/${sessionKey}/drivers/${driverId}/laps`),

  startSimulation: (sessionKey, durationSeconds) =>
    request('POST', '/start-simulation', { session_key: sessionKey, duration_seconds: durationSeconds }),

  stopSimulation: (sessionKey) =>
    request('POST', '/stop-simulation', { session_key: sessionKey }),

  getDriverLive: (sessionKey, driverId) =>
    request('GET', `/sessions/${sessionKey}/drivers/${driverId}/live`),

  getSimulationStatus: (sessionKey) =>
    request('GET', `/sessions/${sessionKey}/simulation/status`),

  getSimulationLive: (sessionKey) =>
    request('GET', `/sessions/${sessionKey}/simulation/live`),
}
