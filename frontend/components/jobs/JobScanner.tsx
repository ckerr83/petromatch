import { useState, useEffect } from 'react'
import { Search, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import api from '../../utils/api'
import toast from 'react-hot-toast'
import { JobBoard, ScrapeTask } from '../../types'

interface JobScannerProps {
  onScanComplete: (taskId: number) => void
}

export default function JobScanner({ onScanComplete }: JobScannerProps) {
  const [boards, setBoards] = useState<JobBoard[]>([])
  const [selectedBoards, setSelectedBoards] = useState<number[]>([])
  const [scanning, setScanning] = useState(false)
  const [currentTask, setCurrentTask] = useState<ScrapeTask | null>(null)

  useEffect(() => {
    fetchBoards()
  }, [])

  useEffect(() => {
    if (currentTask && currentTask.status === 'running') {
      const interval = setInterval(() => {
        checkTaskStatus(currentTask.task_id)
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [currentTask])

  const fetchBoards = async () => {
    try {
      const response = await api.get('/jobs/boards')
      setBoards(response.data)
    } catch (error) {
      toast.error('Failed to fetch job boards')
    }
  }

  const checkTaskStatus = async (taskId: number) => {
    try {
      const response = await api.get(`/jobs/status/${taskId}`)
      setCurrentTask(response.data)
      
      if (response.data.status === 'completed') {
        setScanning(false)
        onScanComplete(taskId)
        toast.success('Job scan completed!')
      } else if (response.data.status === 'failed') {
        setScanning(false)
        toast.error('Job scan failed')
      }
    } catch (error) {
      console.error('Error checking task status:', error)
    }
  }

  const startScan = async () => {
    if (selectedBoards.length === 0) {
      toast.error('Please select at least one job board')
      return
    }

    setScanning(true)
    try {
      console.log('Starting scan with board_ids:', selectedBoards)
      const response = await api.post('/jobs/scrape', {
        board_ids: selectedBoards
      })
      
      console.log('Scan response:', response.data)
      const taskData = {
        task_id: response.data.task_id,
        status: response.data.status,
        created_at: new Date().toISOString() // Fallback for created_at
      }
      console.log('Setting current task:', taskData)
      setCurrentTask(taskData)
      onScanComplete(response.data.task_id)
      toast.success(`Job scan started! Task ID: ${response.data.task_id}`)
    } catch (error: any) {
      setScanning(false)
      console.error('Scan error:', error)
      toast.error(error.response?.data?.detail || 'Failed to start scan')
    }
  }

  const toggleBoard = (boardId: number) => {
    setSelectedBoards(prev =>
      prev.includes(boardId)
        ? prev.filter(id => id !== boardId)
        : [...prev, boardId]
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-600" />
      case 'running':
        return <Clock className="w-5 h-5 text-blue-600 animate-spin" />
      default:
        return <Clock className="w-5 h-5 text-gray-600" />
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold mb-4">Job Scanner</h3>
      
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Select Job Boards</h4>
        <div className="space-y-2">
          {boards.map(board => (
            <label key={board.id} className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-gray-50">
              <input
                type="checkbox"
                checked={selectedBoards.includes(board.id)}
                onChange={() => toggleBoard(board.id)}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <div className="flex-1">
                <div className="font-medium">{board.name}</div>
                <div className="text-sm text-gray-500">{board.base_url}</div>
                {board.login_required && (
                  <div className="text-xs text-orange-600">Requires login</div>
                )}
              </div>
            </label>
          ))}
        </div>
      </div>

      {currentTask && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Current Scan</div>
              <div className="text-sm text-gray-600">
                Started {currentTask.created_at ? new Date(currentTask.created_at).toLocaleString() : 'Unknown time'}
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {getStatusIcon(currentTask.status)}
              <span className="text-sm font-medium capitalize">{currentTask.status}</span>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={startScan}
        disabled={scanning || selectedBoards.length === 0}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
      >
        {scanning ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            <span>Scanning...</span>
          </>
        ) : (
          <>
            <Search className="w-4 h-4" />
            <span>Start Scan</span>
          </>
        )}
      </button>
    </div>
  )
}