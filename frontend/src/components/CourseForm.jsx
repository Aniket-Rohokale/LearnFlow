import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'

/**
 * Manual "log a course" form — used on Overview and Activity. POSTs to
 * /api/courses (same endpoint the CourseCreate schema backs); the extension
 * ingest path stays separate.
 */
export default function CourseForm({ onAdded }) {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState('')
  const [instructor, setInstructor] = useState('')

  const addCourse = useMutation({
    mutationFn: body => api('/api/courses', { method: 'POST', body }),
    onSuccess: course => {
      setUrl(''); setTitle(''); setPlatform(''); setInstructor('')
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      onAdded?.(course)
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    addCourse.mutate({
      url,
      title,
      platform,
      ...(instructor ? { instructor } : {}),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cf-title" className="retro-label">Course title *</label>
          <input
            id="cf-title" type="text" required maxLength={300}
            value={title} onChange={e => setTitle(e.target.value)}
            className="retro-input mt-1" placeholder="Python Bootcamp"
          />
        </div>
        <div>
          <label htmlFor="cf-platform" className="retro-label">Platform *</label>
          <input
            id="cf-platform" type="text" required maxLength={100}
            value={platform} onChange={e => setPlatform(e.target.value)}
            className="retro-input mt-1" placeholder="Udemy / Coursera / YouTube"
          />
        </div>
      </div>
      <div>
        <label htmlFor="cf-url" className="retro-label">Course URL *</label>
        <input
          id="cf-url" type="url" required
          value={url} onChange={e => setUrl(e.target.value)}
          className="retro-input mt-1" placeholder="https://www.udemy.com/course/..."
        />
      </div>
      <div>
        <label htmlFor="cf-instructor" className="retro-label">Instructor (optional)</label>
        <input
          id="cf-instructor" type="text" maxLength={200}
          value={instructor} onChange={e => setInstructor(e.target.value)}
          className="retro-input mt-1" placeholder="Jane Doe"
        />
      </div>
      {addCourse.error && (
        <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
          ERROR: {addCourse.error.message}
        </p>
      )}
      {addCourse.isSuccess && (
        <p className="retro-mono text-xs" style={{ color: '#006400' }}>
          OK — course logged. Open it from the course list to add modules.
        </p>
      )}
      <button type="submit" disabled={addCourse.isPending} className="retro-btn retro-btn-primary">
        {addCourse.isPending ? 'LOGGING…' : 'LOG COURSE'}
      </button>
    </form>
  )
}
