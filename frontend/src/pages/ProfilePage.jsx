import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { SkeletonCard } from '@/components/Skeleton'

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const [careerGoal, setCareerGoal] = useState('')
  const [targetHours, setTargetHours] = useState('')
  const [saved, setSaved] = useState(false)

  const { data: profile, isPending, error } = useQuery({
    queryKey: ['profile'],
    queryFn: () => api('/api/profile'),
  })

  // Seed the form once the profile arrives.
  useEffect(() => {
    if (profile) {
      setCareerGoal(profile.career_goal ?? '')
      setTargetHours(profile.target_hours_per_day ?? '')
    }
  }, [profile])

  const save = useMutation({
    mutationFn: body => api('/api/profile', { method: 'PATCH', body }),
    onSuccess: data => {
      queryClient.setQueryData(['profile'], data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    save.mutate({
      career_goal: careerGoal || null,
      target_hours_per_day: targetHours === '' ? null : Number(targetHours),
    })
  }

  if (isPending) return <SkeletonCard lines={4} />
  if (error) {
    return (
      <p className="retro-mono text-xs" style={{ color: '#8b0000' }}>
        ERROR: {error.message}
      </p>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="retro-h1">Profile</h1>
        <p className="retro-mono mt-2 text-xs">{profile.email}</p>
      </div>

      <div className="retro-panel max-w-xl">
        <div className="retro-bar">Settings</div>
        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <div>
            <label htmlFor="career-goal" className="retro-label">Career goal</label>
            <textarea
              id="career-goal"
              rows={3}
              maxLength={500}
              value={careerGoal}
              onChange={e => setCareerGoal(e.target.value)}
              placeholder="e.g. Become a backend engineer within a year"
              className="retro-input mt-1"
            />
          </div>
          <div>
            <label htmlFor="target-hours" className="retro-label">
              Target study hours per day
            </label>
            <input
              id="target-hours"
              type="number"
              min="0.5"
              max="24"
              step="0.5"
              value={targetHours}
              onChange={e => setTargetHours(e.target.value)}
              className="retro-input mt-1 w-32"
            />
          </div>
          <div className="retro-note">
            Your goal and target hours power the AI study planner and burnout
            detection — the more accurate these are, the better its recommendations.
          </div>
          {save.error && (
            <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
              ERROR: {save.error.message}
            </p>
          )}
          <div className="flex items-center gap-3">
            <button type="submit" disabled={save.isPending} className="retro-btn retro-btn-primary">
              {save.isPending ? 'SAVING…' : 'SAVE'}
            </button>
            {saved && (
              <span className="retro-mono text-xs" style={{ color: '#006400' }}>
                SAVED ✓
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
