import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '@/services/api'
import CourseForm from '@/components/CourseForm'
import GeminiImportForm from '@/components/GeminiImportForm'
import EmptyState from '@/components/EmptyState'
import ProgressBar from '@/components/ProgressBar'
import { SkeletonCard } from '@/components/Skeleton'
import StatCard from '@/components/StatCard'

const weekday = iso =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })

const RISK_STYLES = {
  low: 'green',
  medium: 'amber',
  high: 'red',
  unknown: '',
}

export default function HomePage() {
  const [showBurnout, setShowBurnout] = useState(false)

  const { data, isPending, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api('/api/dashboard'),
  })

  if (isPending) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {Array.from({ length: 5 }, (_, i) => <SkeletonCard key={i} />)}
        </div>
        <SkeletonCard lines={4} />
      </div>
    )
  }

  if (error) {
    return (
      <p className="retro-mono text-xs" style={{ color: '#8b0000' }}>
        ERROR: {error.message} — is the FastAPI server running?
      </p>
    )
  }

  const hours7d = (data.total_minutes_7d / 60).toFixed(1)
  const chartData = data.weekly_activity.map(d => ({
    day: weekday(d.date),
    minutes: d.minutes,
  }))
  const burnout = data.burnout ?? { risk: 'unknown', signals: [], suggestions: [] }

  return (
    <div className="space-y-6">
      <h1 className="retro-h1">Overview</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard label="Courses" value={data.total_courses} />
        <StatCard label="Overall progress" value={data.overall_percent} suffix="%" />
        <StatCard label="Streak" value={data.streak_days} suffix={data.streak_days === 1 ? 'day' : 'days'} />
        <StatCard label="This week" value={hours7d} suffix="hrs" />
        <div className="relative">
          <button
            onClick={() => setShowBurnout(!showBurnout)}
            className="retro-panel w-full text-left"
          >
            <div className="retro-bar">Burnout risk</div>
            <div className="px-3 py-2">
              <span className={`retro-chip ${RISK_STYLES[burnout.risk] ?? ''}`}>
                {burnout.risk}
              </span>
            </div>
          </button>
          {showBurnout && burnout.signals.length > 0 && (
            <div className="retro-panel absolute z-10 mt-1 w-72 p-3">
              <p className="retro-label mb-1">Signals</p>
              <ul className="mb-2 space-y-1">
                {burnout.signals.map((s, i) => (
                  <li key={i} className="retro-mono text-xs">{s}</li>
                ))}
              </ul>
              <p className="retro-label mb-1">Suggestions</p>
              <ul className="space-y-1">
                {burnout.suggestions.map((s, i) => (
                  <li key={i} className="retro-mono text-xs">{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* How to capture */}
      <div className="retro-panel">
        <div className="retro-bar">How to capture &amp; update a course</div>
        <div className="p-4">
          <ol className="retro-steps list-none pl-0">
            <li>Sign in to TrackAI in this browser so the extension can pick up your token.</li>
            <li>Open the course page on Udemy, Coursera, YouTube, etc.</li>
            <li>Click the TrackAI extension icon → press <strong>Capture this course</strong>.</li>
            <li>Wait for the result. Re-capturing the same URL updates modules in place (completion is preserved by title).</li>
            <li>Come back here — the course appears below with a live progress bar.</li>
          </ol>
          <div className="retro-note mt-4">
            <strong>NOTE:</strong> Capturing a course using the extension may take a while
            (LLM parse). Do not exit the webpage or click on another tab until the
            popup shows &ldquo;Course added!&rdquo; or &ldquo;Course updated!&rdquo;.
          </div>
        </div>
      </div>

      {/* Import from Ask Gemini */}
      <div className="retro-panel">
        <div className="retro-bar">Import from Ask Gemini</div>
        <GeminiImportForm />
      </div>

      {/* Manual log */}
      <div className="retro-panel">
        <div className="retro-bar">Log a course manually</div>
        <CourseForm />
      </div>

      {/* Weekly chart */}
      <div className="retro-panel">
        <div className="retro-bar">Study activity — last 7 days</div>
        <div className="p-4">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="2 2" vertical={false} stroke="#d6cdb8" />
                <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={11} fontFamily="Verdana" />
                <YAxis tickLine={false} axisLine={false} fontSize={11} fontFamily="Verdana" allowDecimals={false} />
                <Tooltip
                  formatter={v => [`${v} min`, 'Studied']}
                  contentStyle={{ fontFamily: 'Courier New', fontSize: 11, border: '2px solid #1a1a1a' }}
                />
                <Bar dataKey="minutes" fill="#00008b" radius={0} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Courses */}
      <div>
        <div className="retro-bar mb-0">Courses</div>
        {data.courses.length === 0 ? (
          <EmptyState
            title="No courses yet"
            message="Capture one with the extension, or log it manually above."
          />
        ) : (
          <ul className="retro-panel divide-y-0">
            {data.courses.map(course => (
              <li key={course.id} className="retro-row">
                <Link to={`/courses/${course.id}`} className="block p-3 hover:bg-[#f5f0e0]">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold">{course.title}</p>
                      <p className="retro-mono text-xs">{course.platform}</p>
                    </div>
                    <span className="retro-mono shrink-0 text-sm font-bold">
                      {course.percent_complete}%
                    </span>
                  </div>
                  <div className="mt-2">
                    <ProgressBar percent={course.percent_complete} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
