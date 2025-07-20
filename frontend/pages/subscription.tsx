import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { CheckCircle, Mail, CreditCard, Shield, ArrowLeft } from 'lucide-react'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'

interface PaymentFormData {
  cardNumber: string
  expiryDate: string
  cvv: string
  cardholderName: string
  billingEmail: string
}

export default function SubscriptionPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(1) // 1: plan details, 2: payment form
  const router = useRouter()
  const { register, handleSubmit, formState: { errors } } = useForm<PaymentFormData>()

  useEffect(() => {
    // Get email from URL or localStorage
    const emailFromUrl = router.query.email as string
    const emailFromStorage = localStorage.getItem('petromatch_signup_email')
    const feature = router.query.feature as string
    
    if (emailFromUrl) {
      setEmail(emailFromUrl)
    } else if (emailFromStorage) {
      setEmail(emailFromStorage)
    }
    
    // Handle different features
    if (feature === 'cv-tailoring') {
      const jobData = localStorage.getItem('petromatch_tailor_job')
      if (jobData) {
        const parsedJob = JSON.parse(jobData)
        // Could use this data to customize the subscription page
      }
    }
  }, [router.query])

  const handleContinue = () => {
    setStep(2)
  }

  const onSubmit = async (data: PaymentFormData) => {
    setLoading(true)
    try {
      // Simulate payment processing
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      toast.success('Subscription activated! Welcome to PetroMatch Premium!')
      
      // Clear stored email
      localStorage.removeItem('petromatch_signup_email')
      
      // Redirect to dashboard
      router.push('/dashboard')
      
    } catch (error) {
      toast.error('Payment failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const goBack = () => {
    if (step === 2) {
      setStep(1)
    } else {
      router.back()
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          {/* Header */}
          <div className="bg-blue-600 text-white p-6">
            <div className="flex items-center space-x-4">
              <button
                onClick={goBack}
                className="p-2 hover:bg-blue-700 rounded-md"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex items-center space-x-3">
                <img 
                  src="/petromatch-logo.svg" 
                  alt="PetroMatch Logo" 
                  className="h-8 w-auto"
                />
              </div>
            </div>
            <h1 className="text-2xl font-bold mt-4">Subscribe to Daily Job Alerts</h1>
            <p className="text-blue-100">Get personalized oil & gas opportunities delivered daily</p>
          </div>

          {step === 1 ? (
            /* Plan Details */
            <div className="p-6">
              <div className="text-center mb-8">
                <div className="inline-flex items-center space-x-2 text-3xl font-bold text-gray-900">
                  <span>$10</span>
                  <span className="text-lg font-normal text-gray-600">/month</span>
                </div>
                <p className="text-gray-600 mt-2">Cancel anytime • No setup fees</p>
              </div>

              {/* Features */}
              <div className="space-y-4 mb-8">
                <h3 className="font-semibold text-gray-900 mb-4">What you'll get:</h3>
                {[
                  'Daily personalized job recommendations',
                  'AI-powered job matching based on your CV',
                  'AI CV tailoring for specific job applications',
                  'Priority access to new job listings',
                  'Weekly oil & gas market insights',
                  'Global opportunities from trusted partners',
                  'Email alerts for jobs matching your criteria',
                  'Cancel anytime with one click'
                ].map((feature, index) => (
                  <div key={index} className="flex items-center space-x-3">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-gray-700">{feature}</span>
                  </div>
                ))}
              </div>

              {/* Email confirmation */}
              <div className="bg-gray-50 p-4 rounded-md mb-6">
                <div className="flex items-center space-x-2">
                  <Mail className="w-5 h-5 text-blue-600" />
                  <span className="font-medium text-gray-900">Subscription Email:</span>
                </div>
                <p className="text-gray-700 mt-1">{email || 'Email not provided'}</p>
              </div>

              <button
                onClick={handleContinue}
                className="w-full bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 font-medium"
              >
                Continue to Payment
              </button>
            </div>
          ) : (
            /* Payment Form */
            <form onSubmit={handleSubmit(onSubmit)} className="p-6">
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Payment Information</h3>
                <p className="text-gray-600">Secure payment powered by industry-standard encryption</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Card Number
                  </label>
                  <input
                    type="text"
                    {...register('cardNumber', { 
                      required: 'Card number is required',
                      pattern: {
                        value: /^[0-9\s]{13,19}$/,
                        message: 'Invalid card number'
                      }
                    })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="1234 5678 9012 3456"
                  />
                  {errors.cardNumber && (
                    <p className="text-red-500 text-sm mt-1">{errors.cardNumber.message}</p>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Expiry Date
                    </label>
                    <input
                      type="text"
                      {...register('expiryDate', { 
                        required: 'Expiry date is required',
                        pattern: {
                          value: /^(0[1-9]|1[0-2])\/([0-9]{2})$/,
                          message: 'Use MM/YY format'
                        }
                      })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="MM/YY"
                    />
                    {errors.expiryDate && (
                      <p className="text-red-500 text-sm mt-1">{errors.expiryDate.message}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      CVV
                    </label>
                    <input
                      type="text"
                      {...register('cvv', { 
                        required: 'CVV is required',
                        pattern: {
                          value: /^[0-9]{3,4}$/,
                          message: 'Invalid CVV'
                        }
                      })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="123"
                    />
                    {errors.cvv && (
                      <p className="text-red-500 text-sm mt-1">{errors.cvv.message}</p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Cardholder Name
                  </label>
                  <input
                    type="text"
                    {...register('cardholderName', { required: 'Cardholder name is required' })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="John Doe"
                  />
                  {errors.cardholderName && (
                    <p className="text-red-500 text-sm mt-1">{errors.cardholderName.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Billing Email
                  </label>
                  <input
                    type="email"
                    {...register('billingEmail', { 
                      required: 'Billing email is required',
                      pattern: {
                        value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                        message: 'Invalid email address'
                      }
                    })}
                    defaultValue={email}
                    className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="your@email.com"
                  />
                  {errors.billingEmail && (
                    <p className="text-red-500 text-sm mt-1">{errors.billingEmail.message}</p>
                  )}
                </div>
              </div>

              {/* Security notice */}
              <div className="flex items-center space-x-2 mt-6 p-3 bg-green-50 border border-green-200 rounded-md">
                <Shield className="w-5 h-5 text-green-600" />
                <span className="text-sm text-green-800">Your payment information is encrypted and secure</span>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-6 bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 font-medium"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Processing Payment...</span>
                  </>
                ) : (
                  <>
                    <CreditCard className="w-4 h-4" />
                    <span>Subscribe for $10/month</span>
                  </>
                )}
              </button>

              <p className="text-xs text-gray-500 text-center mt-4">
                By subscribing, you agree to our Terms of Service and Privacy Policy. 
                You can cancel your subscription at any time.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}