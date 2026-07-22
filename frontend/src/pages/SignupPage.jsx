import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function SignupPage() {
  const { signUp } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const { data, error } = await signUp(email, password)
    setSubmitting(false)
    if (error) {
      setError(error.message)
    } else if (data.session) {
      // Email confirmation disabled -> signed in immediately.
      navigate('/')
    } else {
      // Email confirmation enabled -> user must click the link first.
      setNotice('Check your email for a confirmation link, then sign in.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="retro-panel w-full max-w-sm">
        <div className="retro-bar">Create account</div>
        <div className="p-6">
          <h1 className="text-xl font-bold">
            Join Track<span style={{ color: '#00008b' }}>AI</span>
          </h1>
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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="retro-input mt-1"
              />
              <p className="retro-mono mt-1 text-xs">At least 8 characters.</p>
            </div>
            {error && (
              <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
                ERROR: {error}
              </p>
            )}
            {notice && (
              <p role="status" className="retro-mono text-xs" style={{ color: '#006400' }}>
                {notice}
              </p>
            )}
            <button type="submit" disabled={submitting} className="retro-btn retro-btn-primary w-full">
              {submitting ? 'CREATING…' : 'SIGN UP'}
            </button>
          </form>
          <p className="retro-mono mt-4 text-xs">
            Already have an account?{' '}
            <Link to="/login" className="retro-link">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
