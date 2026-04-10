const RESPONSES = {
  deadline: {
    text: "For Fall 2025, Cal Poly Pomona's application period opens October 1 and closes November 30. Some impacted programs may have additional requirements.",
    source: { title: "Admissions", url: "https://www.cpp.edu/admissions/index.shtml" }
  },
  notfound: {
    text: "I wasn't able to find that in the CPP knowledge base.",
    source: null
  }

}

function getMock(msg) {
  const m = msg.toLowerCase()
  if (m.includes('deadline') || m.includes('when') || m.includes('date')) return RESPONSES.deadline

  return RESPONSES.notfound
}

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

function addMessage(response, userMsg) {
  hideWelcome()
  const messages = document.getElementById('messages')
  const isNotFound = response.source === null

  // user bubble
  const userRow = document.createElement('div')
  userRow.className = 'message-row user'
  userRow.innerHTML = `
    <div class="msg-avatar user">
      <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
        <circle cx="12" cy="7" r="4"/>
      </svg>
    </div>

    <div>
      <div class="bubble">${userMsg}</div>
      <div class="msg-time">${getTime()}</div>
    </div>
  `
  messages.appendChild(userRow)

  // ai bubble
  const aiRow = document.createElement('div')
  aiRow.className = `message-row ai${isNotFound ? ' not-found' : ''}`
  aiRow.innerHTML = `
    <div class="msg-avatar ai"><img src="cpp-logo.png" style="width: 20px; height: 20px; border-radius: 50%;"></div>
    <div>
      <div class="bubble">${response.text}</div>
      ${response.source
        ? `<a class="source-link" href="${response.source.url}" target="_blank">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            ${response.source.title}
           </a>`
        : `<div class="not-found-hint">Try visiting <a href="https://www.cpp.edu" target="_blank">cpp.edu</a> directly or contact the admissions office.</div>`
      }
      <div class="msg-time">${getTime()}</div>
    </div>
  `
  messages.appendChild(aiRow)
  messages.scrollTop = messages.scrollHeight
}
//    <div class="msg-avatar ai">P</div>

function showTyping() {
  const messages = document.getElementById('messages')
  const el = document.createElement('div')
  el.className = 'typing-indicator'
  el.id = 'typing'
  el.innerHTML = `
    <div class="msg-avatar ai"><img src="https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fcdn.usteamcolors.com%2Fimages%2Fncaa%2Fdivision-2%2Fcal-poly-pomona-broncos-logo.png&f=1&nofb=1&ipt=8b52cacffaf3c4a9861f6f8d3618cc0a776a726fce3790fb7f2f8b4e4ffce1fe" style="width: 20px; height: 20px; border-radius: 50%;"></div>
    <div class="typing-dots"><span></span><span></span><span></span></div>
  `
  messages.appendChild(el)
  messages.scrollTop = messages.scrollHeight
}

function hideTyping() {
  const el = document.getElementById('typing')
  if (el) el.remove()
}

async function handleSend() {
  const input = document.getElementById('user-input')
  const btn   = document.getElementById('send-btn')
  const msg   = input.value.trim()
  if (!msg) return

  input.value = ''
  input.style.height = 'auto'
  btn.disabled = true

  showTyping()

  // real API call
  let response
  try {
    const res = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history: [] })
    })
    const data = await res.json()
    response = {
      text: data.reply,
      source: data.sources && data.sources.length > 0
        ? { title: data.sources[0].title, url: data.sources[0].url }
        : null
    }
  } catch (err) {
    response = {
      text: "Could not connect to the server. Make sure the backend is running on localhost:8000.",
      source: null
    }
  }


  hideTyping()
  addMessage(response, msg)
  btn.disabled = false
  input.focus()
}

function sendChip(el) {
  document.getElementById('user-input').value = el.textContent
  handleSend()
}

function newChat() {
  document.getElementById('messages').innerHTML = `
    <div class="welcome" id="welcome">
      <div class="welcome-title">Hi, I'm your Campus Knowledge Agent!</div>
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

function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('collapsed')
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