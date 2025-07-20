import { useState, useRef } from 'react'
import { Upload, FileText, X, Edit3, User } from 'lucide-react'
import api from '../../utils/api'
import toast from 'react-hot-toast'
import { CV } from '../../types'

interface CVUploadProps {
  onUpload: (cv: CV) => void
  currentCV?: CV
}

export default function CVUpload({ onUpload, currentCV }: CVUploadProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'skills'>('upload')
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [skillsText, setSkillsText] = useState('')
  const [savingSkills, setSavingSkills] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = async (file: File) => {
    if (!file) return

    const allowedTypes = ['.txt', '.pdf', '.doc', '.docx']
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
    
    if (!allowedTypes.includes(fileExtension)) {
      toast.error('Please upload a .txt, .pdf, .doc, or .docx file')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post('/user/cv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      onUpload(response.data)
      toast.success('CV uploaded successfully!')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0])
    }
  }

  const handleSkillsSave = async () => {
    if (!skillsText.trim()) {
      toast.error('Please enter your skills and experience')
      return
    }

    setSavingSkills(true)
    try {
      // Create a text file from skills input
      const blob = new Blob([skillsText], { type: 'text/plain' })
      const file = new File([blob], 'skills_profile.txt', { type: 'text/plain' })
      
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post('/user/cv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      onUpload(response.data)
      toast.success('Skills profile saved successfully!')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to save skills')
    } finally {
      setSavingSkills(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold mb-4">Your Profile</h3>
      
      {/* Tab Navigation */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        <button
          onClick={() => setActiveTab('upload')}
          className={`flex-1 flex items-center justify-center space-x-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'upload'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Upload CV</span>
        </button>
        <button
          onClick={() => setActiveTab('skills')}
          className={`flex-1 flex items-center justify-center space-x-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            activeTab === 'skills'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Edit3 className="w-4 h-4" />
          <span>Enter Skills</span>
        </button>
      </div>

      {/* Current CV Display */}
      {currentCV && (
        <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg mb-4">
          <div className="flex items-center space-x-3">
            <FileText className="w-5 h-5 text-green-600" />
            <div>
              <p className="font-medium text-green-800">{currentCV.filename}</p>
              <p className="text-sm text-green-600">
                Uploaded on {new Date(currentCV.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setActiveTab('upload')
              fileInputRef.current?.click()
            }}
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            Replace
          </button>
        </div>
      )}

      {/* Upload Tab */}
      {activeTab === 'upload' && !currentCV && (
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-700 mb-2">
            Upload your CV
          </p>
          <p className="text-sm text-gray-500 mb-4">
            Drag and drop your file here, or click to browse
          </p>
          <p className="text-xs text-gray-400">
            Supported formats: .txt, .pdf, .doc, .docx
          </p>
        </div>
      )}

      {/* Skills Tab */}
      {activeTab === 'skills' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Skills & Experience
            </label>
            <textarea
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
              placeholder="Enter your skills, experience, and qualifications here...

Example:
• 10+ years petroleum engineering experience
• Drilling operations and reservoir analysis
• Process engineering and pipeline design
• Experience with ExxonMobil and Shell
• Located in Houston, Texas
• Python, MATLAB, AutoCAD proficiency"
              className="w-full h-40 px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
            />
          </div>
          
          <button
            onClick={handleSkillsSave}
            disabled={savingSkills || !skillsText.trim()}
            className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            {savingSkills ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Saving...</span>
              </>
            ) : (
              <>
                <User className="w-4 h-4" />
                <span>Save Skills Profile</span>
              </>
            )}
          </button>
          
          <div className="text-xs text-gray-500">
            <p>💡 <strong>Tip:</strong> Include your technical skills, years of experience, previous companies, location preferences, and any relevant certifications for better job matching.</p>
          </div>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.pdf,.doc,.docx"
        onChange={handleFileSelect}
        className="hidden"
      />

      {uploading && (
        <div className="mt-4 text-center">
          <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-sm text-gray-600">Uploading...</span>
        </div>
      )}
    </div>
  )
}