export type AlertType = 'expiry_warning' | 'expired' | 'low_stock'
export type AlertSeverity = 'info' | 'warning' | 'critical'

export interface Alert {
  id: number
  alert_type: AlertType
  drug_id: number | null
  batch_id: number | null
  message: string
  severity: AlertSeverity
  is_read: boolean
  is_resolved: boolean
  resolved_by: number | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface AlertListResponse {
  total: number
  unread_count: number
  items: Alert[]
}

export interface AlertStats {
  total: number
  unread: number
  critical: number
  warning: number
  info: number
  expiry_warning: number
  expired: number
  low_stock: number
}

export interface AlertListQuery {
  alert_type?: AlertType
  severity?: AlertSeverity
  is_read?: boolean
  is_resolved?: boolean
  page?: number
  page_size?: number
}
