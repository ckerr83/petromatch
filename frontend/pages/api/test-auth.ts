import { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Force the correct Railway URL - ignore environment variable for now
  const API_URL = 'https://intelligent-learning-production.up.railway.app'
  
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }
  
  try {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: 'test@test.com',
        password: 'password'
      })
    })
    
    const data = await response.json()
    
    res.status(200).json({
      success: response.ok,
      status: response.status,
      url: `${API_URL}/auth/login`,
      data: data,
      headers: Object.fromEntries(response.headers.entries())
    })
  } catch (error: any) {
    res.status(500).json({
      error: error.message,
      url: `${API_URL}/auth/login`
    })
  }
}