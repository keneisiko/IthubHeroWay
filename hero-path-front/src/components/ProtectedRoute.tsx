import { Navigate, useLocation } from 'react-router-dom'
import { isAuthenticated } from '../auth'

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return children
}
