import { useState, useEffect } from 'react'
import Cookies from 'js-cookie'
import api from '../utils/api'

export const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = Cookies.get('token')
    setIsAuthenticated(!!token)
    setLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)

    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })

    const { access_token } = response.data
    Cookies.set('token', access_token, { expires: 7 })
    setIsAuthenticated(true)
    return response.data
  }

  const signup = async (email: string, password: string) => {
    const response = await api.post('/auth/signup', { email, password })
    return response.data
  }

  const logout = () => {
    Cookies.remove('token')
    setIsAuthenticated(false)
  }

  return {
    isAuthenticated,
    loading,
    login,
    signup,
    logout,
  }
}