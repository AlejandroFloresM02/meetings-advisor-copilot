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
