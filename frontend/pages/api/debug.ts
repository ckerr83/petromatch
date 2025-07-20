import { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // Import the API URL logic from utils/api.ts
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://intelligent-learning-production.up.railway.app'
  
  res.status(200).json({
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    computed_API_URL: API_URL,
    NODE_ENV: process.env.NODE_ENV,
    timestamp: new Date().toISOString(),
    all_env_vars: Object.keys(process.env).filter(key => key.startsWith('NEXT_PUBLIC_'))
  })
}