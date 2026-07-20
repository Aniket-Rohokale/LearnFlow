import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'

/**
 * Stage 1 placeholder for the Overview dashboard. Its real purpose right now:
 * prove the frontend can call the protected backend with the Supabase token.
 */
export default function HomePage() {
  const { data, isPending, error } = useQuery({
    queryKey: ['me'],
    queryFn: () => api('/api/me'),
  })

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50">
        Overview
      </h1>
      <div className="mt-6 rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-gray-900">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Backend connection
        </h2>
        {isPending && (
          <div className="mt-2 h-5 w-64 animate-pulse rounded bg-gray-200 dark:bg-gray-800" />
        )}
        {error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
            {error.message} — is the FastAPI server running?
          </p>
        )}
        {data && (
          <p className="mt-2 text-sm text-green-600 dark:text-green-400">
            Authenticated as {data.email} (user {data.id})
          </p>
        )}
      </div>
    </div>
  )
}
