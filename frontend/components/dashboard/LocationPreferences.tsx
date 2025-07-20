import { useState, useEffect } from 'react'
import { MapPin, Plus, X, Check } from 'lucide-react'
import { useForm } from 'react-hook-form'
import api from '../../utils/api'
import toast from 'react-hot-toast'

interface LocationPreference {
  id: number
  location: string
  created_at: string
}

const POPULAR_LOCATIONS = [
  'Asia',
  'Africa', 
  'Europe',
  'North America',
  'South America',
  'Australia',
  'Worldwide'
]

export default function LocationPreferences() {
  const [preferences, setPreferences] = useState<LocationPreference[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [customLocation, setCustomLocation] = useState('')
  const [selectedLocations, setSelectedLocations] = useState<string[]>([])

  useEffect(() => {
    fetchPreferences()
  }, [])

  const fetchPreferences = async () => {
    try {
      const response = await api.get('/user/location-preferences')
      setPreferences(response.data)
      setSelectedLocations(response.data.map((pref: LocationPreference) => pref.location))
    } catch (error: any) {
      if (error.response?.status !== 404) {
        toast.error('Failed to fetch location preferences')
      }
    } finally {
      setLoading(false)
    }
  }

  const savePreferences = async () => {
    setSaving(true)
    try {
      const response = await api.post('/user/location-preferences', {
        locations: selectedLocations
      })
      setPreferences(response.data)
      toast.success('Location preferences saved!')
    } catch (error: any) {
      toast.error('Failed to save preferences')
    } finally {
      setSaving(false)
    }
  }

  const toggleLocation = (location: string) => {
    setSelectedLocations(prev => 
      prev.includes(location)
        ? prev.filter(l => l !== location)
        : [...prev, location]
    )
  }

  const addCustomLocation = () => {
    if (customLocation.trim() && !selectedLocations.includes(customLocation.trim())) {
      setSelectedLocations(prev => [...prev, customLocation.trim()])
      setCustomLocation('')
    }
  }

  const removeLocation = (location: string) => {
    setSelectedLocations(prev => prev.filter(l => l !== location))
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded mb-4"></div>
          <div className="space-y-2">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center space-x-2 mb-6">
        <MapPin className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold">Location Preferences</h3>
      </div>

      <div className="mb-6">
        <p className="text-gray-600 mb-4">
          Select the locations where you'd like to work. This will help us prioritize relevant job matches.
        </p>
        
        {/* Popular Locations */}
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Popular Locations</h4>
          <div className="grid grid-cols-2 gap-2">
            {POPULAR_LOCATIONS.map((location) => (
              <button
                key={location}
                onClick={() => toggleLocation(location)}
                className={`flex items-center justify-between px-3 py-2 text-sm rounded-md border transition-colors ${
                  selectedLocations.includes(location)
                    ? 'bg-blue-50 border-blue-200 text-blue-800'
                    : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span>{location}</span>
                {selectedLocations.includes(location) && (
                  <Check className="w-4 h-4 text-blue-600" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Location Input */}
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Add Custom Location</h4>
          <div className="flex space-x-2">
            <input
              type="text"
              value={customLocation}
              onChange={(e) => setCustomLocation(e.target.value)}
              placeholder="e.g., Saudi Arabia, Nigeria, etc."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  addCustomLocation()
                }
              }}
            />
            <button
              onClick={addCustomLocation}
              disabled={!customLocation.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Selected Locations */}
        {selectedLocations.length > 0 && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Selected Locations</h4>
            <div className="flex flex-wrap gap-2">
              {selectedLocations.map((location) => (
                <div
                  key={location}
                  className="flex items-center space-x-1 bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm"
                >
                  <span>{location}</span>
                  <button
                    onClick={() => removeLocation(location)}
                    className="hover:bg-blue-200 rounded-full p-0.5"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Save Button */}
        <button
          onClick={savePreferences}
          disabled={saving || selectedLocations.length === 0}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          {saving ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              <span>Save Preferences</span>
            </>
          )}
        </button>
      </div>

      {preferences.length > 0 && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
          <p className="text-sm text-green-800">
            <strong>Tip:</strong> Your location preferences will be used to prioritize relevant job matches. 
            Jobs in your preferred locations will receive higher matching scores.
          </p>
        </div>
      )}
    </div>
  )
}