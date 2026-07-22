const API_URL = 'https://learnflow-backend-o17z.onrender.com'

function normalizeUrl(raw) {
  const u = new URL(raw)
  u.search = ''
  u.hash = ''
  u.pathname = u.pathname.replace(/\/+$/, '') || '/'
  return u.href
}

const $ = id => document.getElementById(id)

// ---- Token -----------------------------------------------------------
async function getToken() {
  return new Promise(resolve => {
    chrome.storage.local.get('token', r => resolve(r.token ?? null))
  })
}

// ---- Capture ---------------------------------------------------------
async function getPageText(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => document.body.innerText,
  })
  return result ?? ''
}

async function ingest(token, url, pageText) {
  const res = await fetch(`${API_URL}/api/courses/ingest`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url, page_text: pageText }),
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

function setMessage(text, type = '') {
  const el = $('message')
  el.textContent = text
  el.className = `message ${type}`
}

// ---- Timer -----------------------------------------------------------
function fmtElapsed(startMs) {
  const sec = Math.round((Date.now() - startMs) / 1000)
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

async function timerPostSession(token, minutes) {
  const res = await fetch(`${API_URL}/api/activity`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_minutes: minutes, source: 'extension' }),
  })
  if (!res.ok) throw new Error('Failed to log session')
  return res.json()
}

let timerInterval = null

function timerStop(token, startMs) {
  clearInterval(timerInterval)
  timerInterval = null

  const elapsed = Math.round((Date.now() - startMs) / 60000) // whole minutes
  if (elapsed < 1) {
    chrome.storage.local.remove('sessionStart')
    $('timer-display').hidden = true
    $('timer-start-btn').hidden = false
    $('timer-stop-btn').hidden = true
    $('timer-message').textContent = 'Session too short (< 1 min) — discarded.'
    $('timer-message').className = 'message'
    return
  }

  timerPostSession(token, elapsed)
    .then(() => {
      chrome.storage.local.remove('sessionStart')
      $('timer-display').hidden = true
      $('timer-start-btn').hidden = false
      $('timer-stop-btn').hidden = true
      $('timer-message').textContent = `Logged ${elapsed} min study session ✓`
      $('timer-message').className = 'message success'
    })
    .catch(err => {
      $('timer-message').textContent = err.message
      $('timer-message').className = 'message error'
    })
}

function timerInit(token) {
  const startBtn = $('timer-start-btn')
  const stopBtn = $('timer-stop-btn')
  const display = $('timer-display')
  const tmsg = $('timer-message')

  // Check for an active session
  chrome.storage.local.get('sessionStart', ({ sessionStart }) => {
    if (sessionStart) {
      display.hidden = false
      display.textContent = fmtElapsed(sessionStart)
      startBtn.hidden = true
      stopBtn.hidden = false
      tmsg.textContent = ''

      timerInterval = setInterval(() => {
        display.textContent = fmtElapsed(sessionStart)
      }, 1000)
    }
  })

  startBtn.addEventListener('click', () => {
    const now = Date.now()
    chrome.storage.local.set({ sessionStart: now })
    display.hidden = false
    display.textContent = fmtElapsed(now)
    startBtn.hidden = true
    stopBtn.hidden = false
    tmsg.textContent = ''

    timerInterval = setInterval(() => {
      display.textContent = fmtElapsed(now)
    }, 1000)
  })

  stopBtn.addEventListener('click', async () => {
    const { sessionStart } = await chrome.storage.local.get('sessionStart')
    if (sessionStart) timerStop(token, sessionStart)
  })
}

// ---- Init ------------------------------------------------------------
async function init() {
  const token = await getToken()
  const dot = $('status-dot')
  dot.classList.add(token ? 'signed-in' : 'signed-out')
  dot.title = token ? 'Signed in' : 'Not signed in — open the TrackAI dashboard first'

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (tab) $('page-title').textContent = tab.title ?? tab.url

  const btn = $('capture-btn')

  if (!token) {
    btn.disabled = true
    setMessage('Open the TrackAI dashboard to sign in first.', 'error')
    return
  }

  btn.addEventListener('click', async () => {
    btn.disabled = true
    setMessage('Capturing…')
    try {
      const pageText = await getPageText(tab.id)
      const url = normalizeUrl(tab.url)
      const data = await ingest(token, url, pageText)
      $('result-title').textContent = data.title
      const ul = $('result-modules')
      ul.innerHTML = ''
      data.modules.slice(0, 8).forEach(m => {
        const li = document.createElement('li')
        li.textContent = m.title
        ul.appendChild(li)
      })
      if (data.modules.length > 8) {
        const li = document.createElement('li')
        li.textContent = `…and ${data.modules.length - 8} more`
        ul.appendChild(li)
      }
      $('result').hidden = false
      setMessage(data.created ? 'Course added!' : 'Course updated!', 'success')
    } catch (err) {
      setMessage(err.message, 'error')
      btn.disabled = false
    }
  })

  timerInit(token)
}

init()
