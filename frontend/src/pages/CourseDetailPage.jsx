import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import GeminiUpdateForm from '@/components/GeminiUpdateForm'
import ProgressBar from '@/components/ProgressBar'
import { SkeletonCard } from '@/components/Skeleton'

export default function CourseDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: course, isPending, error } = useQuery({
    queryKey: ['course', id],
    queryFn: () => api(`/api/courses/${id}`),
  })

  const toggleModule = useMutation({
    mutationFn: ({ moduleId, completed }) =>
      api(`/api/modules/${moduleId}`, { method: 'PATCH', body: { completed } }),
    // Optimistic: flip the checkbox instantly; server recomputes the %.
    onMutate: async ({ moduleId, completed }) => {
      await queryClient.cancelQueries({ queryKey: ['course', id] })
      const previous = queryClient.getQueryData(['course', id])
      queryClient.setQueryData(['course', id], old => ({
        ...old,
        modules: old.modules.map(m =>
          m.id === moduleId ? { ...m, completed } : m
        ),
      }))
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      queryClient.setQueryData(['course', id], ctx.previous)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['course', id] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const deleteCourse = useMutation({
    mutationFn: () => api(`/api/courses/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate('/')
    },
  })

  if (isPending) return <SkeletonCard lines={5} />

  if (error) {
    return (
      <div className="space-y-3">
        <p className="retro-mono text-xs" style={{ color: '#8b0000' }}>
          {error.status === 404 ? 'ERROR 404: Course not found.' : `ERROR: ${error.message}`}
        </p>
        <Link to="/" className="retro-link text-sm">← Back to overview</Link>
      </div>
    )
  }

  const done = course.modules.filter(m => m.completed).length

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="retro-link retro-mono text-xs">← Overview</Link>
        <div className="mt-2 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="retro-h1">{course.title}</h1>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="retro-chip blue">{course.platform}</span>
              {course.instructor && <span className="retro-mono text-xs">{course.instructor}</span>}
              <a href={course.url} target="_blank" rel="noreferrer" className="retro-link text-sm">
                Open course ↗
              </a>
            </p>
          </div>
          <button
            onClick={() => {
              if (window.confirm(`Delete "${course.title}" and all its progress?`)) {
                deleteCourse.mutate()
              }
            }}
            disabled={deleteCourse.isPending}
            className="retro-btn retro-btn-danger shrink-0"
          >
            DELETE
          </button>
        </div>
      </div>

      <div className="retro-panel">
        <div className="retro-bar">Progress</div>
        <div className="p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="retro-mono text-xs">
              {done} of {course.modules.length} modules complete
            </span>
            <span className="font-bold">{course.percent_complete}%</span>
          </div>
          <div className="mt-2">
            <ProgressBar percent={course.percent_complete} />
          </div>
        </div>
      </div>

      <div className="retro-panel">
        <div className="retro-bar">Modules</div>
        <ul>
          {course.modules.map(module => (
            <li key={module.id} className="retro-row flex items-center gap-3 px-4 py-2">
              <input
                id={`module-${module.id}`}
                type="checkbox"
                checked={module.completed}
                onChange={e =>
                  toggleModule.mutate({ moduleId: module.id, completed: e.target.checked })
                }
                className="h-4 w-4"
              />
              <label
                htmlFor={`module-${module.id}`}
                className={`flex-1 cursor-pointer text-sm ${
                  module.completed ? 'line-through opacity-50' : ''
                }`}
              >
                {module.title}
              </label>
              {module.estimated_minutes != null && (
                <span className="retro-mono shrink-0 text-xs">
                  {module.estimated_minutes} min
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Update via Ask Gemini */}
      <GeminiUpdateForm courseId={id} courseUrl={course.url} />
    </div>
  )
}
