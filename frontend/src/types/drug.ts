export interface Drug {
  id: number
  name: string
  common_name: string | null
  approval_number: string | null
  specification: string | null
  dosage_form: string | null
  manufacturer: string | null
  category: string | null
  storage_condition: string | null
  description: string | null
  image_url: string | null
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface DrugCreate {
  name: string
  common_name?: string
  approval_number?: string
  specification?: string
  dosage_form?: string
  manufacturer?: string
  category?: string
  storage_condition?: string
  description?: string
}

export type DrugUpdate = Partial<DrugCreate>

export interface DrugListQuery {
  keyword?: string
  manufacturer?: string
  category?: string
  page?: number
  page_size?: number
}
