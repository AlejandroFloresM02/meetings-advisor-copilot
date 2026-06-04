import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

// Sage does not retain chat history — every visit is a fresh conversation.
// Context comes from RAG over meeting transcripts & documents, not prior turns.
// A new thread id is minted on each entry (see AgentChat) so the backend keeps
// no memory between sessions.
function newThreadId() {
  return `web-${Math.random().toString(36).slice(2)}`
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

// The Calderon group conversation is loaded dynamically from a JSON file in
// public/ (see GroupChat). Each message there carries org metadata
// (user, reports_to, position, team, content, hour); the chat only renders the
// user name, the message, and the hour. The rest is kept for future use
// (e.g. RAG context). Edit the conversation by editing the JSON — no rebuild.
const GROUP_CONVERSATION_URL = '/calderon-conversation.json'

// Stable avatar colors for the known teammates; anyone else gets a color
// derived deterministically from their name.
const NAME_COLORS = {
  'Diane Okafor': '#d4694f',
  'Gregory Tanaka': '#4f6dd4',
  'Marcus Hale': '#3f9a8a',
  'Sofia Marchetti': '#b8569e',
  'Janet Osei': '#c79a3a',
}

function colorFor(name) {
  if (NAME_COLORS[name]) return NAME_COLORS[name]
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return `hsl(${hash % 360}, 45%, 50%)`
}

const CHATS = [
  {
    id: 'agent',
    kind: 'agent',
    name: 'Sage Agent',
    // No last-message preview or timestamp: Sage starts a new session each
    // visit, so the sidebar shows a static descriptor instead.
    // subtitle: 'New session each visit · grounded in meetings & documents',
    avatar: { label: 'AI', color: 'var(--accent)' },
  },
  {
    id: 'group',
    kind: 'group',
    name: "Calderon Teachers' — Deal War Room",
    subtitle: '5 members',
    avatar: { label: '👥', color: '#4f6dd4' },
    preview: 'Diane: Perfect. Let’s reconvene Thursday. Thanks all 🙏',
    time: '9:21 AM',
  },
]

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function initials(name) {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}

function Avatar({ label, color, size = 36 }) {
  return (
    <span
      className="avatar"
      style={{ background: color, width: size, height: size, fontSize: size * 0.38 }}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Sidebar (chat list)
// ---------------------------------------------------------------------------

function Sidebar({ chats, activeId, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h2>Chat</h2>
      </div>
      <ul className="chat-list">
        {chats.map((c) => (
          <li
            key={c.id}
            className={`chat-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            <Avatar label={c.avatar.label} color={c.avatar.color} size={44} />
            <div className="chat-item-body">
              <div className="chat-item-top">
                <span className="chat-item-name">{c.name}</span>
                {c.time && <span className="chat-item-time">{c.time}</span>}
              </div>
              <div className="chat-item-preview">{c.preview ?? c.subtitle}</div>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Agent chat — the advisor agent (talks to the FastAPI backend)
// ---------------------------------------------------------------------------

function AgentChat() {
  // Fresh thread per visit — no history is carried over between sessions.
  const threadId = useRef(newThreadId())
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Hi! I’m Sage, your advisor agent. Ask me anything — I can also tell the time and do math.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, loading])

  async function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    setMessages((m) => [...m, { role: 'user', content: text }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId.current }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Request failed (${res.status})`)
      }
      const data = await res.json()
      setMessages((m) => [...m, { role: 'assistant', content: data.reply }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', content: `⚠️ ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="conversation">
      <header className="conv-head">
        <Avatar label="AI" color="var(--accent)" />
        <div className="conv-head-text">
          <h1>Sage Agent</h1>
          <span className="model">poolside/laguna-m.1:free</span>
        </div>
      </header>

      <main className="chat" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="msg assistant">
            <div className="bubble typing">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </main>

      <form className="composer" onSubmit={sendMessage}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Group chat — simulated multi-person conversation loaded from JSON
// ---------------------------------------------------------------------------

// A floating profile card shown when hovering a user's name. It overlaps the
// chat (position: fixed) and lists the info we have for that person in the JSON.
function UserHoverCard({ name, profile, pos, onMouseEnter, onMouseLeave }) {
  const aum =
    profile.direct_aum_mm >= 1000
      ? `$${(profile.direct_aum_mm / 1000).toFixed(2)}B`
      : `$${profile.direct_aum_mm}mm`

  return (
    <div
      className="hovercard"
      role="dialog"
      style={{
        left: pos.x,
        top: pos.y,
        transform: pos.above ? 'translateY(-100%)' : 'none',
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="hovercard-head">
        <Avatar label={initials(name)} color={colorFor(name)} size={42} />
        <div className="hovercard-id">
          <span className="hovercard-name">{name}</span>
          {profile.position && <span className="hovercard-position">{profile.position}</span>}
        </div>
      </div>
      <dl className="hovercard-rows">
        {profile.team && (
          <>
            <dt>Team</dt>
            <dd>{profile.team}</dd>
          </>
        )}
        {profile.reports_to && (
          <>
            <dt>Reports to</dt>
            <dd>{profile.reports_to}</dd>
          </>
        )}
        {profile.location && (
          <>
            <dt>Location</dt>
            <dd>{profile.location}</dd>
          </>
        )}
        {profile.email && (
          <>
            <dt>Email</dt>
            <dd>
              <a href={`mailto:${profile.email}`}>{profile.email}</a>
            </dd>
          </>
        )}
        {profile.phone && (
          <>
            <dt>Phone</dt>
            <dd>{profile.phone}</dd>
          </>
        )}
        {profile.direct_accounts > 0 && (
          <>
            <dt>Book</dt>
            <dd>
              {profile.direct_accounts} accounts · {aum} AUM
            </dd>
          </>
        )}
      </dl>
    </div>
  )
}

// Briefing side panel — a compact Sage sub-interface that answers questions
// about the group conversation. The whole conversation is sent along as context
// (the backend's use of that context is not wired up yet).
function BriefingAgent({ conversation, onClose }) {
  const threadId = useRef(newThreadId())
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        "I've got this conversation as context. Ask me anything about it — owners, risks, next steps, key dates…",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, loading])

  async function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    setMessages((m) => [...m, { role: 'user', content: text }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // The conversation rides along as grounding context for the answer.
        body: JSON.stringify({
          message: text,
          thread_id: threadId.current,
          context: conversation,
        }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Request failed (${res.status})`)
      }
      const data = await res.json()
      setMessages((m) => [...m, { role: 'assistant', content: data.reply }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', content: `⚠️ ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <aside className="briefing">
      <header className="briefing-head">
        <Avatar label="AI" color="var(--accent)" size={30} />
        <div className="briefing-title">
          <strong>Briefing</strong>
          <span>Sage · grounded in this chat</span>
        </div>
        <button className="briefing-close" onClick={onClose} aria-label="Close briefing">
          ×
        </button>
      </header>

      <main className="chat briefing-chat" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="msg assistant">
            <div className="bubble typing">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </main>

      <form className="composer briefing-composer" onSubmit={sendMessage}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this conversation…"
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  )
}

function GroupChat({ chat }) {
  const [messages, setMessages] = useState([])
  const [participants, setParticipants] = useState({})
  const [error, setError] = useState(null)
  const [card, setCard] = useState(null) // { user, x, y, above }
  const [briefingOpen, setBriefingOpen] = useState(false)
  const hideTimer = useRef(null)

  // Load the conversation dynamically from the JSON file on mount.
  useEffect(() => {
    let cancelled = false
    fetch(GROUP_CONVERSATION_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load conversation (${res.status})`)
        return res.json()
      })
      .then((data) => {
        if (cancelled) return
        // Accept either a bare array of messages or { participants, messages }.
        setMessages(Array.isArray(data) ? data : data.messages || [])
        setParticipants((!Array.isArray(data) && data.participants) || {})
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Clear any pending hide timer when the component unmounts.
  useEffect(() => () => clearTimeout(hideTimer.current), [])

  // Unique participants, in order of first appearance — drives the header.
  const members = useMemo(() => {
    const seen = []
    for (const m of messages) if (!seen.includes(m.user)) seen.push(m.user)
    return seen
  }, [messages])

  // Stack consecutive messages from the same user (hide repeated name/avatar).
  const rows = useMemo(
    () =>
      messages.map((m, i) => ({
        ...m,
        stacked: i > 0 && messages[i - 1].user === m.user,
      })),
    [messages],
  )

  // Profile for the hovercard: the participant directory entry, falling back to
  // the fields carried on the message itself.
  function profileFor(user) {
    const fromMsg = messages.find((m) => m.user === user) || {}
    return {
      position: fromMsg.position,
      team: fromMsg.team,
      reports_to: fromMsg.reports_to,
      ...(participants[user] || {}),
    }
  }

  function openCard(user, el) {
    clearTimeout(hideTimer.current)
    const r = el.getBoundingClientRect()
    const above = r.bottom > window.innerHeight - 240
    setCard({
      user,
      x: Math.min(r.left, window.innerWidth - 300),
      y: above ? r.top - 6 : r.bottom + 6,
      above,
    })
  }
  // Small delay so the cursor can travel from the name onto the card itself.
  function scheduleHide() {
    clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setCard(null), 140)
  }
  function keepCard() {
    clearTimeout(hideTimer.current)
  }

  return (
    <section className="conversation">
      <header className="conv-head">
        <Avatar label="👥" color="#4f6dd4" />
        <div className="conv-head-text">
          <h1>{chat.name}</h1>
          <span className="members">{members.join(' · ')}</span>
        </div>
        <button
          className={`briefing-btn ${briefingOpen ? 'active' : ''}`}
          onClick={() => setBriefingOpen((v) => !v)}
        >
          Conversation Briefing
        </button>
      </header>

      <div className="conv-body">
        <div className="conv-main">
          <main className="chat group">
            {error && <div className="msg error"><div className="bubble">⚠️ {error}</div></div>}
            {rows.map((m, i) => (
              <div key={i} className={`group-row ${m.stacked ? 'stacked' : ''}`}>
                <div className="group-avatar-col">
                  {!m.stacked && (
                    <Avatar label={initials(m.user)} color={colorFor(m.user)} size={34} />
                  )}
                </div>
                <div className="group-msg-col">
                  {!m.stacked && (
                    <div className="group-meta">
                      <span
                        className="group-name"
                        onMouseEnter={(e) => openCard(m.user, e.currentTarget)}
                        onMouseLeave={scheduleHide}
                      >
                        {m.user}
                      </span>
                      <span className="group-time">{m.hour}</span>
                    </div>
                  )}
                  <div className="group-bubble">{m.content}</div>
                </div>
              </div>
            ))}
          </main>

          <form className="composer" onSubmit={(e) => e.preventDefault()}>
            <input type="text" placeholder="This is a mockup conversation — read only" disabled />
            <button type="submit" disabled>
              Send
            </button>
          </form>
        </div>

        {briefingOpen && (
          <BriefingAgent conversation={messages} onClose={() => setBriefingOpen(false)} />
        )}
      </div>

      {card && (
        <UserHoverCard
          name={card.user}
          profile={profileFor(card.user)}
          pos={{ x: card.x, y: card.y, above: card.above }}
          onMouseEnter={keepCard}
          onMouseLeave={scheduleHide}
        />
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------

export default function App() {
  const [activeId, setActiveId] = useState('agent')
  const activeChat = CHATS.find((c) => c.id === activeId)

  return (
    <div className="workspace">
      <Sidebar chats={CHATS} activeId={activeId} onSelect={setActiveId} />
      {activeChat.kind === 'agent' ? (
        <AgentChat />
      ) : (
        <GroupChat chat={activeChat} />
      )}
    </div>
  )
}
