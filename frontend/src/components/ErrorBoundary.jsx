import { Component } from 'react'

/** Catches render errors anywhere below it; offers a reload escape hatch. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="retro-panel w-full max-w-md">
          <div className="retro-bar">System Error</div>
          <div className="flex flex-col items-center gap-4 p-8 text-center">
            <p className="text-lg font-bold">Something went wrong</p>
            <p className="retro-mono text-xs">{this.state.error.message}</p>
            <button onClick={() => window.location.reload()} className="retro-btn retro-btn-primary">
              RELOAD PAGE
            </button>
          </div>
        </div>
      </div>
    )
  }
}
