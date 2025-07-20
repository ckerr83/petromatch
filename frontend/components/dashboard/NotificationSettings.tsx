import { useState } from 'react'
import { Mail, Star, Clock, Globe } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useRouter } from 'next/router'
import toast from 'react-hot-toast'

interface EmailSignupData {
  email: string
}

export default function NotificationSettings() {
  const [loading, setLoading] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<EmailSignupData>()
  const router = useRouter()

  const onSubmit = async (data: EmailSignupData) => {
    setLoading(true)
    try {
      // Store email for subscription flow
      localStorage.setItem('petromatch_signup_email', data.email)
      
      // Redirect to subscription page
      toast.success('Redirecting to subscription...')
      
      // Simulate redirect to subscription page
      setTimeout(() => {
        router.push(`/subscription?email=${encodeURIComponent(data.email)}`)
      }, 1000)
      
    } catch (error: any) {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center space-x-2 mb-6">
        <Mail className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold">Daily Job Alerts</h3>
      </div>

      <div className="mb-6">
        <h4 className="text-xl font-semibold text-gray-900 mb-3">
          Want daily oil & gas job updates sent to your inbox?
        </h4>
        <p className="text-gray-600 mb-4">
          Get the latest engineering and management opportunities delivered daily to your email.
        </p>
        
        {/* Benefits */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Clock className="w-4 h-4 text-green-600" />
            <span>Daily job alerts</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Star className="w-4 h-4 text-green-600" />
            <span>AI-matched positions</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Globe className="w-4 h-4 text-green-600" />
            <span>Global opportunities</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Email Address
          </label>
          <input
            type="email"
            {...register('email', { 
              required: 'Email address is required',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address'
              }
            })}
            className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter your email address"
          />
          {errors.email && (
            <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 font-medium"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Processing...</span>
            </>
          ) : (
            <>
              <Mail className="w-4 h-4" />
              <span>Subscribe for $10/month</span>
            </>
          )}
        </button>
      </form>

      <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <div className="flex items-start space-x-2">
          <Star className="w-4 h-4 text-blue-600 mt-0.5" />
          <div className="text-sm">
            <p className="text-blue-800 font-medium">Premium Features Included:</p>
            <ul className="text-blue-700 mt-1 space-y-1">
              <li>• Personalized job recommendations</li>
              <li>• AI CV tailoring for job applications</li>
              <li>• Priority access to new listings</li>
              <li>• Weekly market insights</li>
              <li>• Cancel anytime</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}