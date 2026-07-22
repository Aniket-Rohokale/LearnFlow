const API_URL = 'http://localhost:8000'

const $ = id => document.getElementById(id)

async function getToken() {
  return new Promise(resolve => {
    chrome.storage.local.get('token', r => resolve(r.token ?? null))
  })
}

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

async function init() {
  const token = await getToken()
  const dot = $('status-dot')
  dot.classList.add(token ? 'signed-in' : 'signed-out')
  dot.title = token ? 'Signed in' : 'Not signed in — open the TrackAI dashboard first'

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  $('page-title').textContent = tab.title ?? tab.url

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
      const data = await ingest(token, tab.url, pageText)
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
}

init()
