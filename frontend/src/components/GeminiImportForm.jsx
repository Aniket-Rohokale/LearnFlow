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

export default function GeminiImportForm({ onAdded }) {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [pageText, setPageText] = useState('')
  const [copied, setCopied] = useState(false)

  const importCourse = useMutation({
    mutationFn: body => api('/api/courses/ingest', { method: 'POST', body }),
    onSuccess: course => {
      setUrl('')
      setPageText('')
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      onAdded?.(course)
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    importCourse.mutate({ url, page_text: pageText })
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(GEMINI_PROMPT)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard API unavailable — user can select manually */
    }
  }

  return (
    <div className="p-4 space-y-5">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="gi-url" className="retro-label">Course page URL *</label>
          <input
            id="gi-url"
            type="url"
            required
            value={url}
            onChange={e => setUrl(e.target.value)}
            className="retro-input mt-1"
            placeholder="https://www.udemy.com/course/..."
          />
        </div>
        <div>
          <label htmlFor="gi-text" className="retro-label">
            Paste Gemini output here *
          </label>
          <textarea
            id="gi-text"
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
        {importCourse.error && (
          <p role="alert" className="retro-mono text-xs" style={{ color: '#8b0000' }}>
            ERROR: {importCourse.error.message}
          </p>
        )}
        {importCourse.isSuccess && (
          <p className="retro-mono text-xs" style={{ color: '#006400' }}>
            OK — course {importCourse.data.created ? 'imported' : 'updated'} successfully!
          </p>
        )}
        <button
          type="submit"
          disabled={importCourse.isPending}
          className="retro-btn retro-btn-primary"
        >
          {importCourse.isPending ? 'IMPORTING…' : 'IMPORT COURSE'}
        </button>
      </form>

      {/* Prompt section */}
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
          Open a course page → activate <strong>Ask Gemini</strong> in Chrome →
          paste the prompt above → copy the response → paste it in the form above.
        </p>
      </div>
    </div>
  )
}
