import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import CourseForm from '@/components/CourseForm'
import EmptyState from '@/components/EmptyState'
import { SkeletonCard } from '@/components/Skeleton'

const SOURCE_CHIP = {
  extension: 'blue',
  manual: 'amber',
  dashboard: 'green',
}

export default function ActivityPage() {
  const queryClient = useQueryClient()
  const [minutes, setMinutes] = useState('')
  const [when, setWhen] = useState('') // datetime-local; empty = now

  const { data: logs, isPending, error } = useQuery({
    queryKey: ['activity'],
    queryFn: () => api('/api/activity'),
  })

  const logSession = useMutation({
    mutationFn: body => api('/api/activity', { method: 'POST', body }),
    onSuccess: () => {
      setMinutes('')
      setWhen('')
      queryClient.invalidateQueries({ queryKey: ['activity'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    logSession.mutate({
      session_minutes: Number(minutes),
      source: 'manual',
      ...(when ? { occurred_at: new Date(when).toISOString() } : {}),
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="retro-h1">Study log</h1>

      {/* Log a session */}
      <div className="retro-panel">
        <div className="retro-bar">Log a session</div>
        <form onSubmit={handleSubmit} className="p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label htmlFor="minutes" className="retro-label">Minutes</label>
              <input
                id="minutes"
                type="number"
                min="1"
                max="1440"
                required
                value={minutes}
                onChange={e => setMinutes(e.target.value)}
                className="retro-input mt-1 w-28"
              />
            </div>
            <div>
              <label htmlFor="when" className="retro-label">
                When <span className="normal-case">(optional, defaults to now)</span>
              </label>
              <input
                id="when"
                type="datetime-local"
                value={when}
                max={new Date().toISOString().slice(0, 16)}
                onChange={e => setWhen(e.target.value)}
                className="retro-input mt-1"
              />
            </div>
            <button type="submit" disabled={logSession.isPending} className="retro-btn retro-btn-primary">
              {logSession.isPending ? 'LOGGING…' : 'LOG SESSION'}
            </button>
          </div>
          {logSession.error && (
            <p role="alert" className="retro-mono mt-3 text-xs" style={{ color: '#8b0000' }}>
              ERROR: {logSession.error.message}
            </p>
          )}
        </form>
      </div>

      {/* Add the course being learnt */}
      <div className="retro-panel">
        <div className="retro-bar">Add the course you&apos;re learning</div>
        <p className="retro-mono px-4 pt-3 text-xs">
          Studying something not tracked yet? Log it here — or capture it with
          the browser extension for automatic module lists.
        </p>
        <CourseForm />
      </div>

      {/* Session list */}
      <div>
        <div className="retro-bar">Recent sessions (14 days)</div>
        {isPending ? (
          <SkeletonCard lines={3} />
        ) : error ? (
          <p className="retro-mono mt-2 text-xs" style={{ color: '#8b0000' }}>
            ERROR: {error.message}
          </p>
        ) : logs.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            message="Log a session above, or use the extension's Start/Stop timer while you study."
          />
        ) : (
          <ul className="retro-panel">
            {logs.map(log => (
              <li key={log.id} className="retro-row flex items-center justify-between px-4 py-2">
                <div>
                  <p className="text-sm font-bold">{log.session_minutes} min</p>
                  <p className="retro-mono text-xs">
                    {new Date(log.occurred_at).toLocaleString(undefined, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </p>
                </div>
                <span className={`retro-chip ${SOURCE_CHIP[log.source] ?? ''}`}>
                  {log.source}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
