/** Old-school stat tile: label bar on top, big serif value below. */
export default function StatCard({ label, value, suffix }) {
  return (
    <div className="retro-panel">
      <div className="retro-bar">{label}</div>
      <p className="px-3 py-2 text-2xl font-bold">
        {value}
        {suffix && <span className="ml-1 text-sm font-normal">{suffix}</span>}
      </p>
    </div>
  )
}
