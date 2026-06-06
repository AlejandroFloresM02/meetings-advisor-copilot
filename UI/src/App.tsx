import { Button } from '@/components/ui/button'

// Scaffold smoke test. Confirms the Vite + Tailwind v4 + shadcn/ui toolchain
// is wired (the `@/` alias, theme tokens, and a registry component all resolve).
// The real pre-meeting brief dashboard is built later in sub-project D.
function App() {
  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto flex min-h-svh max-w-2xl flex-col items-center justify-center gap-8 px-6 text-center">
        <div className="space-y-3">
          <p className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            Meeting Copilot · V2
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">
            Frontend environment ready
          </h1>
          <p className="text-muted-foreground">
            Vite + React + TypeScript, Tailwind v4, and shadcn/ui. This
            placeholder only confirms the toolchain — the brief dashboard comes
            later.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
        </div>
      </div>
    </main>
  )
}

export default App
