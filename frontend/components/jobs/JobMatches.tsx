import { useState, useEffect } from 'react'
import { ExternalLink, FileText, Sparkles, Star } from 'lucide-react'
import { useRouter } from 'next/router'
import api from '../../utils/api'
import toast from 'react-hot-toast'
import { Match, JobListing } from '../../types'

interface JobMatchesProps {
  taskId: number | null
}

export default function JobMatches({ taskId }: JobMatchesProps) {
  const [matches, setMatches] = useState<Match[]>([])
  const [jobResults, setJobResults] = useState<JobListing[]>([])
  const [loading, setLoading] = useState(false)
  const [tailoring, setTailoring] = useState<number | null>(null)
  const [hasTriedMatching, setHasTriedMatching] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (taskId) {
      console.log('JobMatches component received taskId:', taskId)
      // Reset the matching flag for new tasks
      setHasTriedMatching(false)
      // First check for existing matches
      fetchMatches()
      // Also fetch direct job results as fallback
      fetchJobResults()
      // If no matches exist, automatically start matching
      checkAndStartMatching()
    }
  }, [taskId])

  const fetchJobResults = async () => {
    if (!taskId) return

    try {
      console.log('Fetching job results for task:', taskId)
      const response = await api.get(`/jobs/results/${taskId}`)
      console.log('Got job results:', response.data.length, 'jobs')
      setJobResults(response.data)
    } catch (error) {
      console.error('Failed to fetch job results:', error)
    }
  }

  const checkAndStartMatching = async () => {
    if (!taskId || hasTriedMatching) return
    
    try {
      const response = await api.get(`/jobs/matches/${taskId}`)
      if (response.data.length === 0) {
        setHasTriedMatching(true)
        console.log('No matches found, starting matching for task:', taskId)
        startMatching()
      } else {
        console.log('Found existing matches:', response.data.length)
        setMatches(response.data)
      }
    } catch (error) {
      if (!hasTriedMatching) {
        setHasTriedMatching(true)
        console.log('Error checking matches, starting matching for task:', taskId)
        startMatching()
      }
    }
  }

  const fetchMatches = async () => {
    if (!taskId) return

    setLoading(true)
    try {
      const response = await api.get(`/jobs/matches/${taskId}`)
      setMatches(response.data)
    } catch (error) {
      toast.error('Failed to fetch matches')
    } finally {
      setLoading(false)
    }
  }

  const startMatching = async () => {
    if (!taskId) return

    setLoading(true)
    try {
      await api.post('/jobs/match', { task_id: taskId })
      toast.success('Matching started!')
      
      // Wait a bit then fetch matches once
      setTimeout(async () => {
        try {
          const response = await api.get(`/jobs/matches/${taskId}`)
          setMatches(response.data)
          setLoading(false)
        } catch (error) {
          setLoading(false)
        }
      }, 2000)
    } catch (error: any) {
      setLoading(false)
      toast.error(error.response?.data?.detail || 'Failed to start matching')
    }
  }

  const tailorCV = async (jobId: number, jobTitle: string) => {
    // Store job details for subscription page
    localStorage.setItem('petromatch_tailor_job', JSON.stringify({
      jobId,
      jobTitle,
      feature: 'cv_tailoring'
    }))
    
    toast.success('Redirecting to unlock CV tailoring...')
    
    // Redirect to subscription page
    setTimeout(() => {
      router.push('/subscription?feature=cv-tailoring')
    }, 1000)
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-100'
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  if (!taskId) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">Job Matches</h3>
        <div className="text-center text-gray-500">
          <Sparkles className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>Start a job scan to see matches</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Job Matches</h3>
        {matches.length === 0 && !loading && (
          <button
            onClick={startMatching}
            className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 flex items-center space-x-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>Find Matches</span>
          </button>
        )}
      </div>

      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          <p className="mt-4 text-gray-600">Finding your perfect matches...</p>
        </div>
      )}

      {matches.length > 0 && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-md p-3 mb-4">
            <div className="text-sm text-blue-800">
              <strong>Results:</strong> Showing top {matches.length} AI-matched jobs from {jobResults.length} total jobs found
            </div>
          </div>
          {matches.map(match => (
            <div key={match.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h4 className="font-semibold text-lg">{match.listing.title}</h4>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getScoreColor(match.score)}`}>
                      {Math.round(match.score * 100)}% Match
                    </span>
                  </div>
                  
                  <div className="text-gray-600 mb-2">
                    <span className="font-medium">{match.listing.company}</span>
                    <span className="mx-2">•</span>
                    <span>{match.listing.location}</span>
                  </div>
                  
                  <div className="text-gray-700 mb-3">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed max-h-32 overflow-y-auto">
                      {match.listing.description}
                    </pre>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <a
                      href={match.listing.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 flex items-center space-x-1"
                    >
                      <ExternalLink className="w-4 h-4" />
                      <span>View Job</span>
                    </a>
                    
                    <button
                      onClick={() => tailorCV(match.listing.id, match.listing.title)}
                      className="bg-gradient-to-r from-purple-600 to-blue-600 text-white px-4 py-2 rounded-md hover:from-purple-700 hover:to-blue-700 flex items-center space-x-2 text-sm font-medium"
                    >
                      <Star className="w-4 h-4" />
                      <span>Tailor my CV to this job</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {matches.length === 0 && jobResults.length > 0 && (
        <div className="space-y-4">
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-4">
            <div className="text-sm text-yellow-800">
              <strong>Jobs Found:</strong> {jobResults.length} total jobs from scan (click "Find Matches" for AI-powered matching)
            </div>
          </div>
          {jobResults.map(job => (
            <div key={job.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h4 className="font-semibold text-lg">{job.title}</h4>
                  </div>
                  
                  <div className="text-gray-600 mb-2">
                    <span className="font-medium">{job.company}</span>
                    <span className="mx-2">•</span>
                    <span>{job.location}</span>
                  </div>
                  
                  <div className="text-gray-700 mb-3">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed max-h-32 overflow-y-auto">
                      {job.description}
                    </pre>
                  </div>
                  
                  <div className="flex items-center space-x-4">
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 flex items-center space-x-1"
                    >
                      <ExternalLink className="w-4 h-4" />
                      <span>View Job</span>
                    </a>
                    
                    <button
                      onClick={() => tailorCV(job.id, job.title)}
                      className="bg-gradient-to-r from-purple-600 to-blue-600 text-white px-4 py-2 rounded-md hover:from-purple-700 hover:to-blue-700 flex items-center space-x-2 text-sm font-medium"
                    >
                      <Star className="w-4 h-4" />
                      <span>Tailor my CV to this job</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {matches.length === 0 && jobResults.length === 0 && !loading && (
        <div className="text-center py-8 text-gray-500">
          <Sparkles className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>No jobs found yet. Try running the matching algorithm!</p>
        </div>
      )}
    </div>
  )
}