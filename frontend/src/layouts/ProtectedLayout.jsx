import { Navigate, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/activity', label: 'Activity' },
  { to: '/plan', label: 'Plan' },
  { to: '/roadmap', label: 'Roadmap' },
  { to: '/profile', label: 'Profile' },
]

export default function ProtectedLayout() {
  const { session, loading, signOut, user } = useAuth()

  // Don't redirect while the persisted session is still being restored,
  // otherwise every hard reload bounces through /login.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="retro-mono text-sm">LOADING…</p>
      </div>
    )
  }

  if (!session) return <Navigate to="/login" replace />

  return (
    <div className="min-h-screen py-6">
      <div className="retro-page">
        {/* Masthead */}
        <header className="retro-panel mb-1">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-2xl font-bold tracking-tight">
              Track<span style={{ color: '#00008b' }}>AI</span>
            </span>
            <div className="flex items-center gap-3">
              <span className="retro-mono hidden text-xs sm:inline">{user.email}</span>
              <button onClick={signOut} className="retro-btn">SIGN OUT</button>
            </div>
          </div>
          <hr className="retro-hr" />
          {/* Nav strip */}
          <nav className="flex flex-wrap items-center gap-0 px-2 py-1">
            {NAV.map(({ to, label, end }, i) => (
              <span key={to} className="flex items-center">
                {i > 0 && <span className="retro-mono px-1 text-xs">|</span>}
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `retro-mono px-2 py-1 text-sm ${
                      isActive ? 'font-bold underline' : 'retro-link'
                    }`
                  }
                >
                  {label}
                </NavLink>
              </span>
            ))}
          </nav>
        </header>

        <main className="mt-4">
          <Outlet />
        </main>

        <footer className="mt-8 border-t border-black pt-2 text-center">
          <p className="retro-mono text-xs">
            TrackAI — best viewed at any resolution — powered by FastAPI + React
          </p>
        </footer>
      </div>
    </div>
  )
}
