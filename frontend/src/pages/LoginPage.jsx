import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const { error } = await signIn(email, password)
    setSubmitting(false)
    if (error) setError(error.message)
    else navigate('/')
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="retro-panel w-full max-w-sm">
        <div className="retro-bar">Member sign-in</div>
        <div className="p-6">
          <h1 className="text-xl font-bold">
            Track<span style={{ color: '#00008b' }}>AI</span>
          </h1>
          <p className="retro-mono mt-1 text-xs">
            All your course progress, one dashboard.
          </p>
          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div>
              <label htmlFor="email" className="retro-label">Email</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="retro-input mt-1"
              />
            </div>
            <div>
              <label htmlFor="password" className="retro-label">Password</label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="retro-input mt-1"
              />
            </div>
            {error && (
              <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
                ERROR: {error}
              </p>
            )}
            <button type="submit" disabled={submitting} className="retro-btn retro-btn-primary w-full">
              {submitting ? 'SIGNING IN…' : 'SIGN IN'}
            </button>
          </form>
          <p className="retro-mono mt-4 text-xs">
            No account?{' '}
            <Link to="/signup" className="retro-link">Sign up</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
