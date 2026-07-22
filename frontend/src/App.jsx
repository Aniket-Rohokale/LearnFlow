import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/hooks/useAuth'
import ErrorBoundary from '@/components/ErrorBoundary'
import ProtectedLayout from '@/layouts/ProtectedLayout'
import ActivityPage from '@/pages/ActivityPage'
import CourseDetailPage from '@/pages/CourseDetailPage'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import PlanPage from '@/pages/PlanPage'
import ProfilePage from '@/pages/ProfilePage'
import RoadmapPage from '@/pages/RoadmapPage'
import SignupPage from '@/pages/SignupPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route element={<ProtectedLayout />}>
                <Route path="/" element={<HomePage />} />
                <Route path="/courses/:id" element={<CourseDetailPage />} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/plan" element={<PlanPage />} />
                <Route path="/roadmap" element={<RoadmapPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
