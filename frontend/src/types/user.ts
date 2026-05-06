export type UserRole = 'admin' | 'manager' | 'employee'

export interface User {
  id: string
  username: string
  email?: string | null
  role: UserRole
  dept?: string | null
  is_active: boolean
}

export interface UserCreate {
  username: string
  password: string
  email?: string | null
  role: UserRole
  dept?: string | null
}

export interface UserUpdate {
  email?: string | null
  role?: UserRole
  dept?: string | null
  is_active?: boolean
  password?: string
}

export interface Department {
  code: string
  name: string
  enabled: boolean
}
