import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '../../hooks/useAuth'
import LoginForm from '../../components/auth/LoginForm'

export default function LoginPage() {
  const { isAuthenticated, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, loading, router])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <img 
              src="/petromatch-logo.svg" 
              alt="PetroMatch Logo" 
              className="h-32 w-auto"
            />
          </div>
          <p className="mt-2 text-gray-600">Find your perfect oil & gas job</p>
          <p className="mt-2 text-sm text-blue-600 font-medium">Demo Mode - Use test@test.com / password</p>
        </div>
        <LoginForm />
      </div>
    </div>
  )
}