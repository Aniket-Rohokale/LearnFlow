import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'

const GEMINI_PROMPT = `Look at this course page and give me a structured summary in this exact format:

COURSE TITLE: [full title of the course]
PLATFORM: [platform name like Udemy, Coursera, YouTube, etc.]
INSTRUCTOR: [instructor name, or "None" if not listed]

MODULES:
1. [Module/Section title] | [duration in minutes, or "N/A"]
2. [Module/Section title] | [duration in minutes, or "N/A"]
...

List all top-level sections or modules in order. Use the section titles exactly as shown on the page. Convert all durations to minutes (e.g., "2hr 30min" = 150). Do not include sub-lectures — only top-level sections.`

/**
 * Update an existing course using Ask Gemini output. The course URL is
 * pre-filled and read-only — the user only pastes Gemini's structured text.
 *
 * Submits to POST /api/courses/ingest which upserts on (user_id, url):
 *   - Adds new modules from the Gemini output
 *   - Preserves completion state for modules whose title matches
 *   - Recomputes percent_complete server-side
 *   - Never creates a duplicate course
 */
export default function GeminiUpdateForm({ courseId, courseUrl }) {
  const queryClient = useQueryClient()
  const [pageText, setPageText] = useState('')
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const updateCourse = useMutation({
    mutationFn: body => api('/api/courses/ingest', { method: 'POST', body }),
    onSuccess: () => {
      setPageText('')
      setExpanded(false)
      queryClient.invalidateQueries({ queryKey: ['course', courseId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(GEMINI_PROMPT)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard API unavailable */
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    updateCourse.mutate({ url: courseUrl, page_text: pageText })
  }

  return (
    <div className="retro-panel">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="retro-bar w-full text-left cursor-pointer flex items-center justify-between"
      >
        <span>Update course via Ask Gemini</span>
        <span style={{ fontFamily: 'Courier New', fontSize: 14 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {expanded && (
        <div className="p-4 space-y-4">
          {/* Pre-filled URL (read-only) */}
          <div>
            <label className="retro-label">Course URL (auto-filled)</label>
            <input
              type="text"
              readOnly
              value={courseUrl}
              className="retro-input mt-1"
              style={{ opacity: 0.6, cursor: 'not-allowed' }}
            />
          </div>

          {/* How it works */}
          <div className="retro-note">
            <strong>How it works:</strong> Paste updated Gemini output below.
            The system will add any <strong>new topics</strong>, preserve your{' '}
            <strong>completed topics</strong>, and recalculate your{' '}
            <strong>completion percentage</strong> — without creating a duplicate course.
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor="gu-text" className="retro-label">
                Paste Gemini output here *
              </label>
              <textarea
                id="gu-text"
                required
                minLength={50}
                value={pageText}
                onChange={e => setPageText(e.target.value)}
                className="retro-textarea mt-1"
                rows={8}
                placeholder={
                  'COURSE TITLE: Python Bootcamp\nPLATFORM: Udemy\nINSTRUCTOR: Jane Doe\n\nMODULES:\n1. Getting Started | 30\n2. Variables & Data Types | 45\n...'
                }
              />
            </div>
            {updateCourse.error && (
              <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
                ERROR: {updateCourse.error.message}
              </p>
            )}
            {updateCourse.isSuccess && (
              <p className="retro-mono text-xs" style={{ color: '#006400' }}>
                OK — course updated! New topics added, completed topics preserved,
                progress recalculated.
              </p>
            )}
            <button
              type="submit"
              disabled={updateCourse.isPending}
              className="retro-btn retro-btn-primary"
            >
              {updateCourse.isPending ? 'UPDATING…' : 'UPDATE COURSE'}
            </button>
          </form>

          {/* Copyable prompt */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="retro-label" style={{ margin: 0 }}>
                Prompt for Ask Gemini (Chrome)
              </p>
              <button
                type="button"
                onClick={handleCopy}
                className={`retro-copy-btn ${copied ? 'copied' : ''}`}
              >
                {copied ? '✓ COPIED' : 'COPY PROMPT'}
              </button>
            </div>
            <div className="retro-prompt-box">{GEMINI_PROMPT}</div>
            <p className="retro-mono text-xs mt-2" style={{ color: '#666' }}>
              Open the course page → activate <strong>Ask Gemini</strong> in
              Chrome → paste the prompt above → copy the response → paste it
              in the form above.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
