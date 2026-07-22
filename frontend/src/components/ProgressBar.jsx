/** Segmented old-school progress bar, 0-100. Green blocks at 100%. */
export default function ProgressBar({ percent }) {
  const clamped = Math.max(0, Math.min(100, percent ?? 0))
  return (
    <div className="retro-progress">
      <div
        className={`retro-progress-fill ${clamped >= 100 ? 'done' : ''}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}
