export interface User {
  id: number
  email: string
}

export interface CV {
  id: number
  filename: string
  created_at: string
}

export interface JobBoard {
  id: number
  name: string
  login_required: boolean
  base_url: string
}

export interface ScrapeTask {
  task_id: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
}

export interface JobListing {
  id: number
  title: string
  company: string
  location: string
  url: string
  description: string
}

export interface Match {
  id: number
  listing: JobListing
  score: number
  matched_at: string
}

export interface EmailNotification {
  id: number
  cron_schedule: string
  last_sent?: string
}