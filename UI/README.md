# Sage Agent — UI

A React + Vite front end for an agentic plugin that lives in a conversational /
meeting environment (Teams / Slack style). The UI is laid out like Teams: a
left **chat list** and an active **conversation** pane on the right.

It ships with two chats:

| Chat                                   | Kind   | Behaviour                                                   |
| -------------------------------------- | ------ | ----------------------------------------------------------- |
| **Sage Agent**                         | Live   | A 1:1 advisor chat wired to the FastAPI backend.            |
| **Calderon Teachers' — Deal War Room** | Mockup | A static, simulated 5-person group conversation. Read-only. |

> The group conversation is **synthetic**. It is grounded in the mock
> `Capital_Group_CRM_mock.xlsx` dataset (a fictional CRM) — no real client data.

---

## Tech stack

- **React 19** with hooks
- **Vite 8** (dev server + build) via `@vitejs/plugin-react`
- **ESLint 10** (`eslint .`)
- Plain CSS with light/dark theming through CSS variables — no UI framework

## Prerequisites

- **Node.js** 18+ (developed on Node 24) and **npm**

## Getting started

```bash
npm install      # install dependencies (creates node_modules/)
npm run dev      # start the dev server → http://localhost:3000
```

### npm scripts

| Script            | What it does                        |
| ----------------- | ----------------------------------- |
| `npm run dev`     | Start the Vite dev server with HMR. |
| `npm run build`   | Production build to `dist/`.        |
| `npm run preview` | Serve the production build locally. |
| `npm run lint`    | Run ESLint over the project.        |

## Ports & backend

- The **UI dev server** runs on **`http://localhost:3000`** (`server.port` in
  [`vite.config.js`](vite.config.js), with `strictPort: true` so it fails loudly
  rather than silently moving if 3000 is taken).
- Requests to **`/api`** are proxied to the **FastAPI backend** on
  **`http://localhost:8000`**. This avoids CORS in development — the browser
  only ever talks to the Vite dev server.
- The backend is **not** part of this folder. Start it separately on port 8000.
  Without it, the UI still loads, but messages sent in the **Sage Agent** chat
  will return an error.

## How the chats work

### Sage Agent (live)

- On submit, the typed message is POSTed to `/api/chat` as
  `{ message, thread_id }`.
- `thread_id` is a stable per-tab id (`web-<random>`) so the backend can keep
  conversation memory for the session.
- The backend's `reply` is appended as an assistant bubble. Network/HTTP errors
  render as an inline error bubble; a typing indicator shows while awaiting a
  response.

### Calderon Teachers' — Deal War Room (mockup)

- A hard-coded thread between five teammates from the CRM org chart
  (Diane Okafor, Gregory Tanaka, Marcus Hale, Sofia Marchetti, Janet Osei).
- Each speaker has a colored initials avatar, title, and timestamp; consecutive
  messages from the same person are stacked Teams-style.
- The composer is intentionally **disabled** — this chat is for display only.

## Project structure

```
UI/
├── index.html            # App entry, mounts #root
├── vite.config.js        # Dev server port (3000) + /api → :8000 proxy
├── eslint.config.js      # Lint rules
└── src/
    ├── main.jsx          # React root
    ├── App.jsx           # Workspace shell, Sidebar, AgentChat, GroupChat + mock data
    ├── App.css           # Layout + chat/bubble styling
    └── index.css         # CSS variables (light/dark theme), base styles
```

### Where to edit things

- **Add / change a chat:** the `CHATS` array in [`src/App.jsx`](src/App.jsx).
- **Edit the group conversation:** the `GROUP_THREAD` / `PEOPLE` constants in
  [`src/App.jsx`](src/App.jsx).
- **Theme colors:** the CSS variables in [`src/index.css`](src/index.css)
  (a `prefers-color-scheme: dark` block overrides for dark mode).
