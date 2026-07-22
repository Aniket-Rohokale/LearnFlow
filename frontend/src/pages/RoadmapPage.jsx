import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import EmptyState from '@/components/EmptyState'
import { SkeletonCard } from '@/components/Skeleton'

export default function RoadmapPage() {
  const queryClient = useQueryClient()

  const { data, isPending, error } = useQuery({
    queryKey: ['roadmap'],
    queryFn: () => api('/api/recommendations/roadmap/latest'),
    retry: false,
  })

  const generate = useMutation({
    mutationFn: () => api('/api/roadmap/generate', { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roadmap'] }),
  })

  if (isPending) {
    return (
      <div className="space-y-4">
        <h1 className="retro-h1">Skill Roadmap</h1>
        <SkeletonCard lines={5} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="retro-h1 flex-1">Skill Roadmap</h1>
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
          title="No roadmap yet"
          message="Complete a course or set your career goal in Profile, then generate a roadmap."
        >
          <div className="flex gap-3">
            <Link to="/profile" className="retro-btn">EDIT PROFILE</Link>
            <button
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
              className="retro-btn retro-btn-primary"
            >
              {generate.isPending ? 'GENERATING…' : 'GENERATE ROADMAP'}
            </button>
          </div>
        </EmptyState>
      )}

      {generate.error && generate.error.status === 409 && (
        <div className="retro-note">
          <Link to="/profile" className="retro-link">
            {generate.error.message} — set it in Profile.
          </Link>
        </div>
      )}

      {generate.error && generate.error.status !== 409 && (
        <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
          ERROR: {generate.error.message}
        </p>
      )}

      {data && data.content_json && (
        <>
          {data.content_json.gaps?.length > 0 && (
            <div className="retro-panel">
              <div className="retro-bar">Identified gaps</div>
              <div className="flex flex-wrap gap-2 p-3">
                {data.content_json.gaps.map((gap, i) => (
                  <span key={i} className="retro-chip amber">{gap}</span>
                ))}
              </div>
            </div>
          )}

          <ol className="space-y-2">
            {data.content_json.next_steps?.map((step, i) => (
              <li key={i} className="retro-panel p-0">
                <div className="flex items-start gap-3 p-3">
                  <span className="retro-mono flex h-6 w-6 shrink-0 items-center justify-center border border-black text-xs font-bold">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="font-bold">{step.skill}</p>
                    <p className="mt-0.5 text-sm">{step.why}</p>
                    {step.suggested_resource && (
                      <p className="retro-mono mt-1 text-xs">
                        Resource: {step.suggested_resource}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}
