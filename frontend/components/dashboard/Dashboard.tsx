import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { LogOut, User } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import CVUpload from '../cv/CVUpload'
import JobScanner from '../jobs/JobScanner'
import JobMatches from '../jobs/JobMatches'
import NotificationSettings from './NotificationSettings'
import LocationPreferences from './LocationPreferences'
import api from '../../utils/api'
import toast from 'react-hot-toast'
import { CV } from '../../types'

export default function Dashboard() {
  const { logout } = useAuth()
  const router = useRouter()
  const [cv, setCV] = useState<CV | null>(null)
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCV()
  }, [])

  const fetchCV = async () => {
    try {
      const response = await api.get('/user/cv')
      setCV(response.data)
    } catch (error: any) {
      if (error.response?.status !== 404) {
        toast.error('Failed to fetch CV')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    router.push('/auth/login')
  }

  const handleCVUpload = (newCV: CV) => {
    setCV(newCV)
  }

  const handleScanComplete = (taskId: number) => {
    setCurrentTaskId(taskId)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <img 
                src="/petromatch-logo.svg" 
                alt="PetroMatch Logo" 
                className="h-16 w-auto"
              />
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2 text-gray-600">
                <User className="w-5 h-5" />
                <span>Dashboard</span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <CVUpload onUpload={handleCVUpload} currentCV={cv} />
            <JobScanner onScanComplete={handleScanComplete} />
            <JobMatches taskId={currentTaskId} />
          </div>
          
          <div className="space-y-8">
            <LocationPreferences />
            <NotificationSettings />
            
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Tips</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>• Upload your CV first to get started</li>
                <li>• Set your location preferences for better matches</li>
                <li>• Select relevant job boards for your search</li>
                <li>• Use the matching feature to find best fits</li>
                <li>• Tailor your CV for specific positions</li>
                <li>• Set up notifications for new matches</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}