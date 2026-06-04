import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

// A stable per-tab id so the backend keeps conversation memory for this session.
const THREAD_ID = `web-${Math.random().toString(36).slice(2)}`

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

// The five teammates in the group chat (from the Institutional Client Group
// org chart in the CRM). The simulated conversation below is grounded in real
// records from the mock dataset — the State of Calderon Teachers' deal.
const PEOPLE = {
  diane: { name: 'Diane Okafor', title: 'Senior Relationship Director', color: '#d4694f' },
  gregory: { name: 'Gregory Tanaka', title: 'MD — Public Funds & Pensions', color: '#4f6dd4' },
  marcus: { name: 'Marcus Hale', title: 'Relationship Manager', color: '#3f9a8a' },
  sofia: { name: 'Sofia Marchetti', title: 'Relationship Manager', color: '#b8569e' },
  janet: { name: 'Janet Osei', title: 'Director — Client Service & Ops', color: '#c79a3a' },
}

// A simulated war-room thread about the State of Calderon Teachers' Retirement
// Fund pipeline (OPP-3003 $600.5mm + OPP-3002 $345.6mm, Bond Fund of America).
const GROUP_THREAD = [
  {
    from: 'diane',
    time: '9:02 AM',
    text: "Team — quick huddle on State of Calderon Teachers'. The $600.5mm Bond Fund of America mandate (OPP-3003) is in due diligence and expected to close June 30. That's 26 days out. 🗓️",
  },
  {
    from: 'gregory',
    time: '9:04 AM',
    text: "Good. The board has it at 80% probability — what's the remaining risk?",
  },
  {
    from: 'diane',
    time: '9:05 AM',
    text: 'Mercer still has two open DD items: our trade-allocation policy and the fee schedule on the sub-$500mm breakpoint.',
  },
  {
    from: 'marcus',
    time: '9:07 AM',
    text: 'I can pull the breakpoint language we used for Northgate — same Mercer analyst, that might speed things up.',
  },
  {
    from: 'sofia',
    time: '9:09 AM',
    text: 'Watch the optics on fees. Patricia Schmidt (their PM) flagged on our May 7 check-in that the board is fee-sensitive after their last manager search.',
  },
  {
    from: 'diane',
    time: '9:10 AM',
    text: 'Exactly. Lisa Schmidt is the gatekeeper for scheduling, and Liam Mitchell on the board is the real decision driver.',
  },
  {
    from: 'janet',
    time: '9:13 AM',
    text: 'Ops side: if we close June 30 we need funding paperwork started by the 20th. I’ll pre-stage the onboarding pack.',
  },
  {
    from: 'gregory',
    time: '9:15 AM',
    text: "And don't lose sight of the second mandate — the $345.6mm finals presentation (OPP-3002) is July 23. Same strategy, same fund.",
  },
  {
    from: 'diane',
    time: '9:16 AM',
    text: "Right — combined that's ~$946mm of new AUM from one relationship that's still showing $0 with us today. 🚀",
  },
  {
    from: 'marcus',
    time: '9:18 AM',
    text: "I'll get the Mercer analyst the breakpoint memo this afternoon.",
  },
  {
    from: 'sofia',
    time: '9:19 AM',
    text: "I'll prep Patricia with the Q1 attribution one-pager so she can defend us internally.",
  },
  {
    from: 'janet',
    time: '9:20 AM',
    text: 'Onboarding pack pre-staged. I’ll loop in legal the moment we have a verbal.',
  },
  {
    from: 'diane',
    time: '9:21 AM',
    text: "Perfect. Let's reconvene Thursday. Thanks all 🙏",
  },
]

const CHATS = [
  {
    id: 'agent',
    kind: 'agent',
    name: 'Sage Agent',
    subtitle: 'poolside/laguna-m.1:free',
    avatar: { label: 'AI', color: 'var(--accent)' },
    preview: 'Ask me anything — I can tell the time and do math.',
    time: 'now',
  },
  {
    id: 'group',
    kind: 'group',
    name: "Calderon Teachers' — Deal War Room",
    subtitle: '5 members',
    members: Object.values(PEOPLE).map((p) => p.name),
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

function openGroupMeetingWindow(chat) {
  const meeting = window.open('', 'calderon-group-meeting', 'width=1120,height=760')

  if (!meeting) {
    window.alert('Allow pop-ups to open the group meeting window.')
    return
  }

  const tiles = Object.values(PEOPLE)
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
              <span class="meeting-subtitle">${Object.keys(PEOPLE).length} cameras active</span>
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
                <span className="chat-item-time">{c.time}</span>
              </div>
              <div className="chat-item-preview">{c.preview}</div>
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
        body: JSON.stringify({ message: text, thread_id: THREAD_ID }),
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
// Group chat — static, simulated multi-person conversation
// ---------------------------------------------------------------------------

function GroupChat({ chat }) {
  // Render the made-up thread; group messages by sender for cleaner stacking.
  const rows = useMemo(() => {
    return GROUP_THREAD.map((m, i) => {
      const prev = GROUP_THREAD[i - 1]
      return { ...m, person: PEOPLE[m.from], stacked: prev && prev.from === m.from }
    })
  }, [])

  return (
    <section className="conversation">
      <header className="conv-head">
        <Avatar label="👥" color="#4f6dd4" />
        <div className="conv-head-text">
          <h1>{chat.name}</h1>
          <span className="members">{chat.members.join(' · ')}</span>
        </div>
        <div className="conv-head-actions">
          <Button className="meeting-button" type="button" onClick={() => openGroupMeetingWindow(chat)}>
            <span className="meeting-button-icon" aria-hidden="true"></span>
            Start meeting
          </Button>
        </div>
      </header>

      <main className="chat group">
        {rows.map((m, i) => (
          <div key={i} className={`group-row ${m.stacked ? 'stacked' : ''}`}>
            <div className="group-avatar-col">
              {!m.stacked && (
                <Avatar label={initials(m.person.name)} color={m.person.color} size={34} />
              )}
            </div>
            <div className="group-msg-col">
              {!m.stacked && (
                <div className="group-meta">
                  <span className="group-name">{m.person.name}</span>
                  <span className="group-title">{m.person.title}</span>
                  <span className="group-time">{m.time}</span>
                </div>
              )}
              <div className="group-bubble">{m.text}</div>
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
