// ── Supabase setup ──
const SUPABASE_URL = "https://mknmhnzmwyksjqbkgbbs.supabase.co"
const SUPABASE_ANON_KEY = "sb_publishable_5P1TNGaT6rkoZQxw1fz8fQ_jZFuBFSM"
const { createClient } = supabase
const sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const API_STREAM = "/chat/stream"
const API_SAVE   = "/chat/save"

let conversationHistory = []
let currentConversationId = null
let currentUser = null
let allConversations = []

// ── Auth ──
async function init() {
  const { data: { session } } = await sb.auth.getSession()
  if (session) {
    currentUser = session.user
    showAppLoggedIn()
  } else {
    showAppGuest()
  }

  sb.auth.onAuthStateChange((event, session) => {
    if (session) {
      currentUser = session.user
      showAppLoggedIn()
    } else {
      currentUser = null
      showAppGuest()
    }
  })
}

function showAppLoggedIn() {
  document.getElementById('auth-screen').style.display = 'none'
  document.getElementById('app').style.display = 'flex'
  document.getElementById('app').classList.remove('guest-mode')

  document.querySelector('.sidebar').style.display = 'flex'
  document.getElementById('guest-bar').style.display = 'none'
  document.getElementById('mobile-menu-btn').style.display = ''

  document.getElementById('user-email').textContent = currentUser.email
  loadConversations()
}

function showAppGuest() {
  document.getElementById('auth-screen').style.display = 'none'
  document.getElementById('app').style.display = 'flex'
  document.getElementById('app').classList.add('guest-mode')

  document.querySelector('.sidebar').style.display = 'none'
  document.getElementById('guest-bar').style.display = 'flex'
  document.getElementById('mobile-menu-btn').style.display = 'none'

  conversationHistory = []
  currentConversationId = null
  newChat()
}

function toggleMobileSidebar() {
  document.querySelector('.sidebar').classList.toggle('open')
  document.getElementById('sidebar-overlay').classList.toggle('visible')
}

function showAuth() {
  document.getElementById('auth-screen').style.display = 'flex'
  document.getElementById('app').style.display = 'none'
}

function openAuthModal(tab = 'login') {
  showAuth()
  switchTabByName(tab)
}

function switchTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'))
  event.target.classList.add('active')
  document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none'
  document.getElementById('signup-form').style.display = tab === 'signup' ? 'block' : 'none'
  hideAuthMessages()
}

function switchTabByName(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => {
    t.classList.remove('active')
    if (t.textContent.toLowerCase().includes(tab === 'login' ? 'sign in' : 'sign up')) {
      t.classList.add('active')
    }
  })
  document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none'
  document.getElementById('signup-form').style.display = tab === 'signup' ? 'block' : 'none'
  hideAuthMessages()
}

function showAuthError(msg) {
  const el = document.getElementById('auth-error')
  el.textContent = msg
  el.style.display = 'block'
  document.getElementById('auth-success').style.display = 'none'
}

function showAuthSuccess(msg) {
  const el = document.getElementById('auth-success')
  el.textContent = msg
  el.style.display = 'block'
  document.getElementById('auth-error').style.display = 'none'
}

function hideAuthMessages() {
  document.getElementById('auth-error').style.display = 'none'
  document.getElementById('auth-success').style.display = 'none'
}

async function handleLogin() {
  const email = document.getElementById('login-email').value.trim()
  const password = document.getElementById('login-password').value
  if (!email || !password) return showAuthError('Please fill in all fields.')
  const { error } = await sb.auth.signInWithPassword({ email, password })
  if (error) showAuthError(error.message)
}

async function handleSignup() {
  const email = document.getElementById('signup-email').value.trim()
  const password = document.getElementById('signup-password').value
  if (!email || !password) return showAuthError('Please fill in all fields.')
  if (password.length < 6) return showAuthError('Password must be at least 6 characters.')
  const { error } = await sb.auth.signUp({ email, password })
  if (error) showAuthError(error.message)
  else showAuthSuccess('Check your email to confirm your account!')
}

async function handleGoogleAuth() {
  const { error } = await sb.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin }
  })
  if (error) showAuthError(error.message)
}

async function handleSignOut() {
  conversationHistory = []
  currentConversationId = null
  newChat()
  await sb.auth.signOut()
}

// ── Chat History (logged-in only) ──
async function loadConversations() {
  const { data: { session } } = await sb.auth.getSession()
  if (!session) return

  const res = await fetch('/conversations', {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  })
  if (!res.ok) return
  const convs = await res.json()
  renderConversations(convs)
}

function renderConversations(convs) {
  allConversations = convs
  const container = document.getElementById('chatHistory')
  container.innerHTML = ''
  convs.forEach(conv => {
    const item = document.createElement('div')
    item.className = 'history-item' + (conv.id === currentConversationId ? ' active' : '')
    item.innerHTML = `
      <div class="history-title">${conv.title || 'Untitled'}</div>
      <div class="history-time">${formatTime(conv.created_at)}</div>
    `
    item.onclick = () => loadConversation(conv.id, conv.title)
    container.appendChild(item)
  })
}

async function loadConversation(id, title) {
  const { data: { session } } = await sb.auth.getSession()
  if (!session) return

  currentConversationId = id
  conversationHistory = []

  const res = await fetch(`/conversations/${id}/messages`, {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  })
  if (!res.ok) return
  const msgs = await res.json()

  const container = document.getElementById('messages')
  container.innerHTML = ''

  msgs.forEach(msg => {
    if (msg.role === 'user') {
      addUserMessage(msg.content, false)
    } else {
      addAIMessage({
        text: msg.content,
        sources: msg.sources && msg.sources.length > 0 ? msg.sources : [],
      }, false)
    }
    conversationHistory.push({ role: msg.role, content: msg.content })
  })

  document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'))
}

function formatTime(ts) {
  const date = new Date(ts)
  const now = new Date()
  const diff = now - date
  if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (diff < 172800000) return 'Yesterday'
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ── Chat UI helpers ──
function getTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function autoResize(el) {
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

function hideWelcome() {
  const w = document.getElementById('welcome')
  if (w) w.remove()
}

function addUserMessage(msg, scroll = true) {
  hideWelcome()
  const messages = document.getElementById('messages')
  const userRow = document.createElement('div')
  userRow.className = 'message-row user'
  userRow.innerHTML = `
    <div class="msg-avatar user">
      <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
    </div>
    <div class="bubble-wrap">
      <div class="bubble">${msg}</div>
      <div class="msg-time">${getTime()}</div>
    </div>
  `
  messages.appendChild(userRow)
  if (scroll) messages.scrollTop = messages.scrollHeight
}

/**
 * Creates the AI message bubble and returns a handle for streaming updates.
 */
function createAIMessageBubble() {
  const messages = document.getElementById('messages')
  const aiRow = document.createElement('div')
  aiRow.className = 'message-row ai'

  const bubbleDiv = document.createElement('div')
  bubbleDiv.className = 'bubble'

  const wrapDiv = document.createElement('div')
  wrapDiv.className = 'bubble-wrap'
  wrapDiv.appendChild(bubbleDiv)

  const avatarDiv = document.createElement('div')
  avatarDiv.className = 'msg-avatar ai'
  avatarDiv.innerHTML = `<img src="/static/cpp-logo.png" style="width:20px;height:20px;border-radius:50%;">`

  aiRow.appendChild(avatarDiv)
  aiRow.appendChild(wrapDiv)
  messages.appendChild(aiRow)
  messages.scrollTop = messages.scrollHeight

  return {
    appendToken(text) {
      bubbleDiv.dataset.raw = (bubbleDiv.dataset.raw || '') + text
      bubbleDiv.innerHTML = formatText(bubbleDiv.dataset.raw)
      messages.scrollTop = messages.scrollHeight
    },

    finalize(allSources = []) {
      // ── Source pills ──
      if (allSources.length > 0) {
        const sourceWrap = document.createElement('div')
        sourceWrap.className = 'source-links'

        allSources.slice(0, 3).forEach(src => {
          if (!src || !src.url) return
          const link = document.createElement('a')
          link.className = 'source-link'
          link.href = src.url
          link.target = '_blank'
          link.rel = 'noopener noreferrer'
          link.innerHTML = `
            <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span>${src.title || src.url}</span>
          `
          sourceWrap.appendChild(link)
        })

        wrapDiv.appendChild(sourceWrap)
      } else {
        const hint = document.createElement('div')
        hint.className = 'not-found-hint'
        hint.innerHTML = `Try visiting <a href="https://www.cpp.edu" target="_blank">cpp.edu</a> directly or contact the admissions office.`
        wrapDiv.appendChild(hint)
      }

      // ── Timestamp ──
      const timeDiv = document.createElement('div')
      timeDiv.className = 'msg-time'
      timeDiv.textContent = getTime()
      wrapDiv.appendChild(timeDiv)
    }
  }
}

// Used when replaying history (full text at once)
function addAIMessage(response, scroll = true) {
  const bubble = createAIMessageBubble()
  bubble.appendToken(response.text)
  bubble.finalize(response.sources || [])
  if (scroll) {
    const messages = document.getElementById('messages')
    messages.scrollTop = messages.scrollHeight
  }
}

function formatText(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

function showTyping() {
  const messages = document.getElementById('messages')
  const el = document.createElement('div')
  el.className = 'typing-indicator'
  el.id = 'typing'
  el.innerHTML = `
    <div class="msg-avatar ai">
      <img src="/static/cpp-logo.png" style="width:20px;height:20px;border-radius:50%;">
    </div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
  `
  messages.appendChild(el)
  messages.scrollTop = messages.scrollHeight
}

function hideTyping() {
  const el = document.getElementById('typing')
  if (el) el.remove()
}

// ── Core send + stream handler ────────────────────────────────────────────────

async function handleSend() {
  const input = document.getElementById('user-input')
  const btn   = document.getElementById('send-btn')
  const msg   = input.value.trim()
  if (!msg) return

  input.value = ''
  input.style.height = 'auto'
  btn.disabled = true

  addUserMessage(msg)
  showTyping()
  conversationHistory.push({ role: 'user', content: msg })

  const { data: { session } } = await sb.auth.getSession()
  const authHeader = session ? { 'Authorization': `Bearer ${session.access_token}` } : {}

  let fullReply = ''
  let sources   = []
  let bubble    = null

  try {
    const res = await fetch(API_STREAM, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({
        message: msg,
        history: conversationHistory,
        conversation_id: currentConversationId,
      }),
    })

    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let   buffer  = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data:')) continue
        const json = line.slice(5).trim()
        let ev
        try { ev = JSON.parse(json) } catch { continue }

        if (ev.type === 'sources') {
          sources = ev.sources || []
          hideTyping()
          bubble = createAIMessageBubble()

        } else if (ev.type === 'token') {
          fullReply += ev.text
          if (bubble) bubble.appendToken(ev.text)

        } else if (ev.type === 'done') {
          // Pass ALL sources to finalize so all pills are shown
          if (bubble) bubble.finalize(sources)

        } else if (ev.type === 'error') {
          hideTyping()
          if (!bubble) bubble = createAIMessageBubble()
          bubble.appendToken('Sorry, something went wrong. Please try again.')
          bubble.finalize([])
        }
      }
    }

  } catch (err) {
    hideTyping()
    if (!bubble) bubble = createAIMessageBubble()
    bubble.appendToken('Could not connect to the server. Please try again.')
    bubble.finalize([])
    fullReply = ''
  }

  if (fullReply) {
    conversationHistory.push({ role: 'assistant', content: fullReply })
  }

  // Persist to DB (fire-and-forget for logged-in users)
  if (fullReply && session) {
    fetch(API_SAVE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({
        message: msg,
        reply: fullReply,
        sources,
        conversation_id: currentConversationId,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.conversation_id && !currentConversationId) {
        currentConversationId = data.conversation_id
        loadConversations()
      }
    })
    .catch(() => {})
  }

  btn.disabled = false
  input.focus()
}

function sendChip(el) {
  document.getElementById('user-input').value = el.textContent
  handleSend()
}

function newChat() {
  conversationHistory = []
  currentConversationId = null
  document.getElementById('messages').innerHTML = `
    <div class="welcome" id="welcome">
      <div class="welcome-title">Hi, I'm BroncoGPT!</div>
      <div class="suggestion-chips">
        <div class="chip" onclick="sendChip(this)">When is the application deadline?</div>
        <div class="chip" onclick="sendChip(this)">What majors are offered?</div>
        <div class="chip" onclick="sendChip(this)">Where is the financial aid office?</div>
        <div class="chip" onclick="sendChip(this)">What are the on campus dining options?</div>
      </div>
    </div>
  `
  document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'))
}

function openSearch() {
  document.getElementById('search-overlay').classList.add('open')
  document.getElementById('search-input').focus()
}

function closeSearch() {
  document.getElementById('search-overlay').classList.remove('open')
}

document.getElementById('search-overlay').addEventListener('click', function(e) {
  if (e.target === this) closeSearch()
})

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeSearch()
})

// ── Voice input ──
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
let isListening = false

if (!SpeechRecognition) {
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('mic-btn')
    if (btn) btn.style.display = 'none'
  })
}

function toggleVoice() {
  if (!SpeechRecognition) return

  if (isListening) {
    isListening = false
    document.getElementById('mic-btn').classList.remove('listening')
    return
  }

  const recognition = new SpeechRecognition()
  recognition.continuous = false
  recognition.interimResults = true
  recognition.lang = navigator.language || 'en-US'

  recognition.onstart = () => {
    isListening = true
    document.getElementById('mic-btn').classList.add('listening')
  }

  recognition.onresult = (e) => {
    const transcript = Array.from(e.results)
      .map(r => r[0].transcript)
      .join('')
    document.getElementById('user-input').value = transcript
    autoResize(document.getElementById('user-input'))
  }

  recognition.onend = () => {
    isListening = false
    document.getElementById('mic-btn').classList.remove('listening')
    const val = document.getElementById('user-input').value.trim()
    if (val) handleSend()
  }

  recognition.onerror = (e) => {
    isListening = false
    document.getElementById('mic-btn').classList.remove('listening')
    console.error('speech error:', e.error)
  }

  recognition.start()
}

document.getElementById('search-input').addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase().trim()
  const container = document.getElementById('search-results')

  if (!query) {
    container.innerHTML = ''
    return
  }

  const filtered = allConversations.filter(c =>
    c.title.toLowerCase().includes(query)
  )

  if (filtered.length === 0) {
    container.innerHTML = `<div style="padding:16px;color:var(--text-muted);font-size:14px;text-align:center;">No conversations found</div>`
    return
  }

  container.innerHTML = filtered.map(c => `
    <div class="history-item" onclick="loadConversation('${c.id}', '${c.title}'); closeSearch()" style="padding:12px 14px;">
      <div class="history-title" style="color:var(--text)">${c.title}</div>
      <div class="history-time" style="color:var(--text-muted)">${formatTime(c.created_at)}</div>
    </div>
  `).join('')
})

// ── Start ──
init()