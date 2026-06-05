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
    accountId: 'ACC-1002',
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

function Button({ children, className = '', ...props }) {
  return (
    <button className={`button ${className}`.trim()} {...props}>
      {children}
    </button>
  )
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

// Camera-tile accent colors for the meeting window (cycled per participant).
const CAMERA_COLORS = ['#4f6dd4', '#d4794f', '#4fd49b', '#b14fd4', '#d4c24f', '#4fb8d4', '#d44f7a']

function openGroupMeetingWindow(chat, people = []) {
  const meeting = window.open('', 'calderon-group-meeting', 'width=1120,height=760')

  if (!meeting) {
    window.alert('Allow pop-ups to open the group meeting window.')
    return
  }

  const tiles = people
    .map((person, index) => {
      const cameraState = index === 2 ? 'Speaking' : 'Camera on'

      return `
        <article class="camera-tile">
          <div class="camera-feed" style="--person-color: ${escapeHtml(person.color)};">
            <div class="camera-glow"></div>
            <div class="camera-person">${escapeHtml(initials(person.name))}</div>
            <div class="camera-bars" aria-hidden="true">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div class="camera-meta">
            <span class="camera-name">${escapeHtml(person.name)}</span>
            <span class="camera-title">${escapeHtml(person.title)}</span>
            <span class="camera-state">${cameraState}</span>
          </div>
        </article>
      `
    })
    .join('')

  meeting.document.open()
  meeting.document.write(`
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>${escapeHtml(chat.name)} Meeting</title>
        <style>
          :root {
            color-scheme: light dark;
            --bg: #111218;
            --surface: #1c1e26;
            --surface-2: #252833;
            --line: #343845;
            --text: #f4f5f8;
            --muted: #a9afbd;
            font-family: system-ui, 'Segoe UI', Roboto, sans-serif;
          }

          * { box-sizing: border-box; }

          html,
          body {
            height: 100%;
            overflow: hidden;
          }

          body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
          }

          .meeting {
            height: 100vh;
            display: grid;
            grid-template-rows: auto minmax(0, 1fr) auto;
            overflow: hidden;
          }

          .meeting-head,
          .meeting-controls {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 16px 22px;
            background: rgba(28, 30, 38, 0.94);
            border-bottom: 1px solid var(--line);
          }

          .meeting-controls {
            justify-content: center;
            border-top: 1px solid var(--line);
            border-bottom: 0;
          }

          h1 {
            margin: 0;
            font-size: 18px;
            letter-spacing: 0;
          }

          .meeting-subtitle,
          .meeting-time,
          .camera-title {
            color: var(--muted);
            font-size: 13px;
          }

          .meeting-subtitle {
            display: block;
            margin-top: 3px;
          }

          .camera-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            grid-auto-rows: minmax(0, 1fr);
            gap: 14px;
            padding: 20px;
            align-content: center;
            min-height: 0;
            overflow: hidden;
          }

          .camera-tile {
            min-height: 0;
            display: grid;
            grid-template-rows: minmax(0, 1fr) auto;
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
          }

          .camera-feed {
            position: relative;
            min-height: 0;
            display: grid;
            place-items: center;
            overflow: hidden;
            background:
              radial-gradient(circle at 35% 24%, color-mix(in srgb, var(--person-color), white 22%), transparent 0 16%, transparent 28%),
              linear-gradient(135deg, color-mix(in srgb, var(--person-color), black 20%), #171922 72%);
          }

          .camera-glow {
            position: absolute;
            width: 42%;
            aspect-ratio: 1;
            border-radius: 50%;
            background: color-mix(in srgb, var(--person-color), white 12%);
            filter: blur(44px);
            opacity: 0.46;
          }

          .camera-person {
            position: relative;
            z-index: 1;
            width: 86px;
            height: 86px;
            display: grid;
            place-items: center;
            border-radius: 50%;
            background: color-mix(in srgb, var(--person-color), black 8%);
            color: white;
            font-size: 26px;
            font-weight: 700;
            box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
          }

          .camera-bars {
            position: absolute;
            right: 14px;
            bottom: 14px;
            display: flex;
            align-items: end;
            gap: 3px;
            height: 18px;
          }

          .camera-bars span {
            width: 4px;
            border-radius: 999px;
            background: #9df0c4;
          }

          .camera-bars span:nth-child(1) { height: 8px; }
          .camera-bars span:nth-child(2) { height: 15px; }
          .camera-bars span:nth-child(3) { height: 11px; }

          .camera-meta {
            display: grid;
            gap: 2px;
            padding: 12px 14px;
            background: var(--surface-2);
          }

          .camera-name {
            font-size: 14px;
            font-weight: 700;
          }

          .camera-title,
          .camera-state {
            font-size: 12px;
          }

          .camera-state {
            color: #9df0c4;
          }

          .control {
            min-width: 44px;
            height: 40px;
            padding: 0 14px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface-2);
            color: var(--text);
            font: inherit;
          }

          .control.leave {
            border-color: #f87171;
            background: #dc2626;
            color: #fff;
          }
        </style>
      </head>
      <body>
        <main class="meeting">
          <header class="meeting-head">
            <div>
              <h1>${escapeHtml(chat.name)}</h1>
              <span class="meeting-subtitle">${people.length} cameras active</span>
            </div>
            <span class="meeting-time">Group meeting</span>
          </header>
          <section class="camera-grid" aria-label="Participant cameras">
            ${tiles}
          </section>
          <footer class="meeting-controls" aria-label="Meeting controls">
            <button class="control" type="button">Mic</button>
            <button class="control" type="button">Camera</button>
            <button class="control" type="button">Share</button>
            <button class="control leave" type="button" onclick="window.close()">Leave</button>
          </footer>
        </main>
      </body>
    </html>
  `)
  meeting.document.close()
  meeting.focus()
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
        'Hi! I’m Sage, your advisor agent. Ask me anything',
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

// ---------------------------------------------------------------------------
// Pre-meeting brief panel — renders the structured one-pager from the backend
// (GET /api/accounts/{id}/brief): snapshot, ranked risk flags, talking points,
// since-last-meeting and next steps. Deterministic facts; LLM phrasing layered
// on top when it passes the fact-check guard.
// ---------------------------------------------------------------------------

const SEVERITY_COLOR = { high: '#e5534b', medium: '#d9a441', low: '#3fa46a' }

function BriefPanel({ accountId, accountName, onClose }) {
  const [brief, setBrief] = useState(null)
  const [error, setError] = useState(null)
  const bodyRef = useRef(null)

  // Always open at the top so the snapshot + risk flags are seen first.
  useEffect(() => { bodyRef.current?.scrollTo({ top: 0 }) }, [brief])

  useEffect(() => {
    let cancelled = false
    setBrief(null)
    setError(null)
    fetch(`/api/accounts/${accountId}/brief`)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load brief (${res.status})`)
        return res.json()
      })
      .then((data) => { if (!cancelled) setBrief(data) })
      .catch((err) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [accountId])

  const a = brief?.account
  return (
    <aside className="brief-panel">
      <header className="briefing-head">
        <Avatar label="📋" color="#4f6dd4" size={30} />
        <div className="briefing-title">
          <strong>Pre-Meeting Brief</strong>
          <span>{accountName}</span>
        </div>
        <button className="briefing-close" onClick={onClose} aria-label="Close brief">
          ×
        </button>
      </header>

      <div className="brief-body" ref={bodyRef}>
        {error && <div className="msg error"><div className="bubble">⚠️ {error}</div></div>}
        {!brief && !error && (
          <div className="brief-loading">
            <div className="bubble typing"><span></span><span></span><span></span></div>
            <p>Generating brief…</p>
          </div>
        )}
        {brief && (
          <>
            {a && (
              <div className="brief-snapshot">
                <div className="brief-account-name">{a.name}</div>
                <div className="brief-tags">
                  {a.type && <span className="brief-tag">{a.type}</span>}
                  {a.tier && <span className="brief-tag">{a.tier}</span>}
                  {a.status && <span className="brief-tag">{a.status}</span>}
                </div>
                <dl className="brief-meta">
                  <div><dt>RM</dt><dd>{a.relationship_manager || '—'}</dd></div>
                  <div><dt>Consultant</dt><dd>{a.consultant || '—'}</dd></div>
                  <div><dt>AUM w/ CG</dt><dd>${(a.aum_with_cg_mm ?? 0).toLocaleString()}mm</dd></div>
                  <div><dt>Strategy</dt><dd>{a.primary_strategy || '—'}</dd></div>
                </dl>
              </div>
            )}

            {brief.headline && <div className="brief-headline">{brief.headline}</div>}

            {brief.meeting?.purpose && (
              <p className="brief-purpose">
                🎯 {brief.meeting.purpose}{brief.meeting.date ? ` · ${brief.meeting.date}` : ''}
              </p>
            )}

            {brief.risk_flags?.length > 0 && (
              <section className="brief-section">
                <h4>Risk flags</h4>
                {brief.risk_flags.map((r) => (
                  <div key={r.id} className="brief-risk">
                    <div className="brief-risk-head">
                      <span className="brief-sev-dot" style={{ background: SEVERITY_COLOR[r.severity] || '#888' }} />
                      <span className="brief-risk-title">{r.title}</span>
                      <span className="brief-risk-score">{Math.round((r.score ?? 0) * 100)}</span>
                    </div>
                    <div className="brief-risk-evidence">{r.evidence}</div>
                    {r.explanation && <div className="brief-risk-expl">{r.explanation}</div>}
                  </div>
                ))}
              </section>
            )}

            {brief.talking_points?.length > 0 && (
              <section className="brief-section">
                <h4>Talking points</h4>
                <ul className="brief-list">
                  {brief.talking_points.map((t, i) => <li key={i}>{t.text}</li>)}
                </ul>
              </section>
            )}

            {brief.since_last_meeting && (
              <section className="brief-section">
                <h4>Since last meeting · {brief.since_last_meeting.date}</h4>
                <p className="brief-since">{brief.since_last_meeting.summary}</p>
                {brief.since_last_meeting.open_action_items?.length > 0 && (
                  <ul className="brief-list">
                    {brief.since_last_meeting.open_action_items.map((ai, i) => <li key={i}>{ai.text}</li>)}
                  </ul>
                )}
              </section>
            )}

            {brief.suggested_next_steps?.length > 0 && (
              <section className="brief-section">
                <h4>Suggested next steps</h4>
                <ul className="brief-list">
                  {brief.suggested_next_steps.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </section>
            )}

            {brief.meta?.grounded_in && (
              <p className="brief-grounded">Grounded in {brief.meta.grounded_in.join(' · ')}</p>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

function GroupChat({ chat }) {
  const [messages, setMessages] = useState([])
  const [participants, setParticipants] = useState({})
  const [error, setError] = useState(null)
  const [card, setCard] = useState(null) // { user, x, y, above }
  const [briefingOpen, setBriefingOpen] = useState(false)
  const [briefOpen, setBriefOpen] = useState(false)
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
          className={`briefing-btn ${briefOpen ? 'active' : ''}`}
          onClick={() => { setBriefOpen((v) => !v); setBriefingOpen(false) }}
        >
          Pre-Meeting Brief
        </button>
        <button
          className={`briefing-btn ${briefingOpen ? 'active' : ''}`}
          style={{ marginLeft: 8 }}
          onClick={() => { setBriefingOpen((v) => !v); setBriefOpen(false) }}
        >
          Conversation Briefing
        </button>
        <div className="conv-head-actions">
          <Button
            className="meeting-button"
            type="button"
            onClick={() =>
              openGroupMeetingWindow(
                chat,
                members.map((name, i) => {
                  const p = profileFor(name)
                  return { name, title: p.position || p.team || '', color: CAMERA_COLORS[i % CAMERA_COLORS.length] }
                }),
              )
            }
          >
            <span className="meeting-button-icon" aria-hidden="true"></span>
            Start meeting
          </Button>
        </div>
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

        {briefOpen && (
          <BriefPanel
            accountId={chat.accountId}
            accountName={chat.name}
            onClose={() => setBriefOpen(false)}
          />
        )}
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
