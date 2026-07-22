/** Friendly empty state, typewriter flavour. */
export default function EmptyState({ title, message, children }) {
  return (
    <div className="retro-panel">
      <div className="retro-bar">Notice</div>
      <div className="flex flex-col items-center px-6 py-10 text-center">
        <p className="text-lg font-bold">{title}</p>
        <p className="retro-mono mt-2 max-w-md text-xs">{message}</p>
        {children && <div className="mt-4">{children}</div>}
      </div>
    </div>
  )
}
