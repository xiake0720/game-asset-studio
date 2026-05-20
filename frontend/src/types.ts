export type JobOutput = {
  name: string
  size_bytes: number
  url: string
}

export type JobState = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  created_at: string
  updated_at: string
  input_name: string
  error?: string | null
  outputs: JobOutput[]
  report?: any
}
