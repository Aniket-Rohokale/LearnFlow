import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import EmptyState from '@/components/EmptyState'
import { SkeletonCard } from '@/components/Skeleton'

/**
 * Return the most recent Sunday at midnight (local time).
 * If today IS Sunday, returns today at 00:00.
 */
function lastSunday() {
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  d.setDate(d.getDate() - d.getDay()) // getDay(): 0 = Sunday
  return d
}

export default function PlanPage() {
  const queryClient = useQueryClient()
  const autoTriggered = useRef(false)

  const { data, isPending, error } = useQuery({
    queryKey: ['plan'],
    queryFn: () => api('/api/recommendations/plan/latest'),
    retry: false,
  })

  const generate = useMutation({
    mutationFn: () => api('/api/plan/generate', { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plan'] }),
  })

  // Auto-regenerate: if the stored plan is from before this week's Sunday,
  // trigger a fresh generation so the user always sees an up-to-date plan
  // that reflects new courses and current completion status.
  useEffect(() => {
    if (autoTriggered.current) return
    if (isPending || generate.isPending) return
    if (!data?.created_at) return

    const planDate = new Date(data.created_at)
    if (planDate < lastSunday()) {
      autoTriggered.current = true
      generate.mutate()
    }
  }, [data, isPending, generate.isPending])

  if (isPending) {
    return (
      <div className="space-y-4">
        <h1 className="retro-h1">Study Plan</h1>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <SkeletonCard key={i} lines={3} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h1 className="retro-h1">Study Plan</h1>
          {data?.created_at && (
            <p className="retro-mono text-xs mt-1" style={{ color: '#666' }}>
              Generated on{' '}
              {new Date(data.created_at).toLocaleDateString(undefined, {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          )}
        </div>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="retro-btn retro-btn-primary ml-4 shrink-0"
        >
          {generate.isPending ? 'GENERATING…' : 'REGENERATE'}
        </button>
      </div>

      {generate.isPending && autoTriggered.current && (
        <div className="retro-note">
          <strong>Auto-regenerating:</strong> Your plan is from last week.
          Generating a fresh plan with your latest courses and progress…
        </div>
      )}

      {error && error.status === 404 && (
        <EmptyState
          title="No plan yet"
          message="Generate a 7-day study plan from your captured courses."
        >
          <button
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="retro-btn retro-btn-primary"
          >
            {generate.isPending ? 'GENERATING…' : 'GENERATE PLAN'}
          </button>
        </EmptyState>
      )}

      {generate.error && (
        <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
          ERROR: {generate.error.message}
        </p>
      )}

      {data && data.content_json && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {data.content_json.days.map((day, i) => {
            const upcoming = new Date()
            upcoming.setDate(upcoming.getDate() + 1 + i) // tomorrow + i
            return (
            <div key={i} className="retro-panel">
              <div className="retro-bar">
                {upcoming.toLocaleDateString(undefined, {
                  weekday: 'short', month: 'short', day: 'numeric',
                })}
              </div>
              <ul className="space-y-1 p-3">
                {day.blocks.map((block, j) => (
                  <li key={j} className="text-sm">
                    <span className="font-bold">{block.module_title}</span>
                    <span className="retro-mono ml-2 text-xs">{block.minutes} min</span>
                  </li>
                ))}
              </ul>
              <p className="retro-mono border-t border-black px-3 py-1 text-xs">
                {day.total_minutes} min total
              </p>
            </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
