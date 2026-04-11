export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T | null
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
