import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import EmptyState from '@/components/EmptyState'
import { SkeletonCard } from '@/components/Skeleton'

export default function PlanPage() {
  const queryClient = useQueryClient()

  const { data, isPending, error } = useQuery({
    queryKey: ['plan'],
    queryFn: () => api('/api/recommendations/plan/latest'),
    retry: false,
  })

  const generate = useMutation({
    mutationFn: () => api('/api/plan/generate', { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plan'] }),
  })

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
        <h1 className="retro-h1 flex-1">Study Plan</h1>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="retro-btn retro-btn-primary ml-4 shrink-0"
        >
          {generate.isPending ? 'GENERATING…' : 'REGENERATE'}
        </button>
      </div>

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
          {data.content_json.days.map((day, i) => (
            <div key={i} className="retro-panel">
              <div className="retro-bar">
                {new Date(day.date + 'T00:00:00').toLocaleDateString(undefined, {
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
          ))}
        </div>
      )}
    </div>
  )
}
