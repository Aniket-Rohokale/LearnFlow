/** Pulse placeholders while queries load — dithered grey, boxy. */
export function SkeletonLine({ className = 'h-5 w-48' }) {
  return (
    <div
      className={`animate-pulse ${className}`}
      style={{ background: 'repeating-linear-gradient(90deg,#e2dac7 0 6px,#efe9da 6px 12px)' }}
    />
  )
}

export function SkeletonCard({ lines = 2 }) {
  return (
    <div className="retro-panel p-4">
      <div className="space-y-3">
        {Array.from({ length: lines }, (_, i) => (
          <SkeletonLine key={i} className={i === 0 ? 'h-4 w-24' : 'h-6 w-40'} />
        ))}
      </div>
    </div>
  )
}
