import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Refresh token queue to prevent race conditions
let isRefreshing = false
let refreshQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

function processQueue(error: unknown, token: string | null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (token) resolve(token)
    else reject(error)
  })
  refreshQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(api(originalRequest))
            },
            reject,
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const response = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        })

        const { access_token, refresh_token } = response.data
        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', refresh_token)

        processQueue(null, access_token)

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: async (email: string, password: string, remember_me: boolean = false) => {
    const response = await api.post('/auth/login', { email, password, remember_me })
    return response.data
  },
  
  devLogin: async () => {
    const response = await api.post('/auth/dev-login')
    return response.data
  },
  
  register: async (companyData: any, userData: any) => {
    const response = await api.post('/auth/register', companyData, {
      params: userData,
    })
    return response.data
  },
  
  getMe: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },

  updateMe: async (data: { first_name?: string; last_name?: string; phone?: string }) => {
    const response = await api.patch('/auth/me', data)
    return response.data
  },

  changeEmailRequest: async (newEmail: string) => {
    const response = await api.post('/auth/change-email/request', { new_email: newEmail })
    return response.data
  },

  changeEmailVerify: async (code: string) => {
    const response = await api.post('/auth/change-email/verify', { code })
    return response.data
  },
  
  changePassword: async (currentPassword: string, newPassword: string) => {
    const response = await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },
  
  // Google OAuth
  getGoogleUrl: async () => {
    const response = await api.get('/auth/google/url')
    return response.data as { auth_url: string; state: string }
  },
  
  googleCallback: async (code: string, state: string) => {
    const response = await api.get('/auth/google/callback', {
      params: { code, state },
    })
    return response.data as { access_token: string; refresh_token: string }
  },
}

// Dashboard API
export const dashboardApi = {
  getStats: async () => {
    const response = await api.get('/dashboard/stats')
    return response.data
  },
  
  getRecentCalls: async (limit = 5) => {
    const response = await api.get('/dashboard/recent-calls', { params: { limit } })
    return response.data
  },
  
  getUpcomingAppointments: async (limit = 5) => {
    const response = await api.get('/dashboard/upcoming-appointments', { params: { limit } })
    return response.data
  },
  
  getActionItems: async (limit = 5) => {
    const response = await api.get('/dashboard/action-items', { params: { limit } })
    return response.data
  },
  
  getAIWorkersStatus: async () => {
    const response = await api.get('/dashboard/ai-workers-status')
    return response.data
  },
}

// AI Workers API
export const aiWorkersApi = {
  list: async () => {
    const response = await api.get('/ai-workers')
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/ai-workers/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/ai-workers', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/ai-workers/${id}`, data)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/ai-workers/${id}`)
    return response.data
  },
  
  toggleStatus: async (id: string) => {
    const response = await api.post(`/ai-workers/${id}/toggle-status`)
    return response.data
  },
  
  getStats: async (id: string) => {
    const response = await api.get(`/ai-workers/${id}/stats`)
    return response.data
  },

  getVoices: async () => {
    const response = await api.get('/ai-workers/voices')
    return response.data
  },

  getVoicePreview: async (voiceId: string): Promise<Blob> => {
    const response = await api.get(`/ai-workers/voice-preview/${voiceId}`, {
      responseType: 'blob',
    })
    return response.data
  },
}

// Phone Numbers API
export const phoneNumbersApi = {
  list: async () => {
    const response = await api.get('/phone-numbers')
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/phone-numbers/${id}`)
    return response.data
  },
  
  // Create starts the setup wizard - user provides their business number
  create: async (data: { business_number: string; friendly_name?: string; ai_worker_id?: string }) => {
    const response = await api.post('/phone-numbers', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/phone-numbers/${id}`, data)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/phone-numbers/${id}`)
    return response.data
  },
  
  release: async (id: string) => {
    const response = await api.delete(`/phone-numbers/${id}/release`)
    return response.data
  },
}

// Calendars API
export const calendarsApi = {
  list: async () => {
    const response = await api.get('/calendars')
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/calendars/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/calendars', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/calendars/${id}`, data)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/calendars/${id}`)
    return response.data
  },
  
  getOAuthUrl: async (provider: string, calendarId: string) => {
    const response = await api.get(`/calendars/oauth/${provider}/url`, {
      params: { calendar_id: calendarId },
    })
    return response.data
  },
  
  sync: async (id: string) => {
    const response = await api.post(`/calendars/${id}/sync`)
    return response.data
  },

  getZoomOAuthUrl: async (calendarId: string) => {
    const response = await api.get('/calendars/oauth/zoom/url', {
      params: { calendar_id: calendarId },
    })
    return response.data
  },

  disconnectZoom: async (id: string) => {
    const response = await api.delete(`/calendars/${id}/zoom`)
    return response.data
  },

  getTeamsOAuthUrl: async (calendarId: string) => {
    const response = await api.get('/calendars/oauth/teams/url', {
      params: { calendar_id: calendarId },
    })
    return response.data
  },

  disconnectTeams: async (id: string) => {
    const response = await api.delete(`/calendars/${id}/teams`)
    return response.data
  },

  getGmeetOAuthUrl: async (calendarId: string) => {
    const response = await api.get('/calendars/oauth/gmeet/url', {
      params: { calendar_id: calendarId },
    })
    return response.data
  },

  disconnectGmeet: async (id: string) => {
    const response = await api.delete(`/calendars/${id}/gmeet`)
    return response.data
  },
}

// CRM Integrations API
export const crmApi = {
  list: async () => {
    const response = await api.get('/crm')
    return response.data
  },

  get: async (id: string) => {
    const response = await api.get(`/crm/${id}`)
    return response.data
  },

  create: async (data: any) => {
    const response = await api.post('/crm', data)
    return response.data
  },

  update: async (id: string, data: any) => {
    const response = await api.patch(`/crm/${id}`, data)
    return response.data
  },

  delete: async (id: string) => {
    const response = await api.delete(`/crm/${id}`)
    return response.data
  },

  getOAuthUrl: async (provider: string, crmId: string) => {
    const response = await api.get(`/crm/oauth/${provider}/url`, {
      params: { crm_id: crmId },
    })
    return response.data
  },

  test: async (id: string) => {
    const response = await api.post(`/crm/${id}/test`)
    return response.data
  },
}

// Websites API
export const websitesApi = {
  list: async () => {
    const response = await api.get('/websites')
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/websites/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/websites', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/websites/${id}`, data)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/websites/${id}`)
    return response.data
  },
  
  reindex: async (id: string) => {
    const response = await api.post(`/websites/${id}/reindex`)
    return response.data
  },
  
  testQuestion: async (id: string, question: string) => {
    const response = await api.post(`/websites/${id}/test`, { question })
    return response.data
  },
}

// Mock data for training (when backend is not available)
const MOCK_TRAINING_RULES = [
  {
    id: 'rule-1',
    rule_key: 'use_formal_address',
    rule_name: 'Gebruik u-vorm',
    rule_description: 'Spreek de klant aan met \'u\' in plaats van \'jij\'.',
    is_enabled: true,
    display_order: 1,
  },
  {
    id: 'rule-2',
    rule_key: 'apologize_on_complaints',
    rule_name: 'Excuses bij klachten',
    rule_description: 'Bied excuses aan wanneer een klant een klacht heeft.',
    is_enabled: true,
    display_order: 2,
  },
  {
    id: 'rule-3',
    rule_key: 'offer_alternatives',
    rule_name: 'Altijd alternatieven aanbieden',
    rule_description: 'Bied altijd een alternatief aan als iets niet mogelijk is.',
    is_enabled: true,
    display_order: 3,
  },
  {
    id: 'rule-4',
    rule_key: 'never_guess',
    rule_name: 'Nooit gokken',
    rule_description: 'Geef nooit informatie waar je niet zeker van bent. Verwijs door indien nodig.',
    is_enabled: true,
    display_order: 4,
  },
  {
    id: 'rule-5',
    rule_key: 'confirm_appointments',
    rule_name: 'Afspraken bevestigen',
    rule_description: 'Herhaal altijd de datum en tijd van een afspraak ter bevestiging.',
    is_enabled: true,
    display_order: 5,
  },
  {
    id: 'rule-6',
    rule_key: 'summarize_at_end',
    rule_name: 'Samenvatten aan einde',
    rule_description: 'Vat aan het einde van het gesprek kort samen wat er is besproken.',
    is_enabled: false,
    display_order: 6,
  },
  {
    id: 'rule-7',
    rule_key: 'collect_callback_number',
    rule_name: 'Terugbelnummer vragen',
    rule_description: 'Vraag om een terugbelnummer als de vraag niet direct beantwoord kan worden.',
    is_enabled: true,
    display_order: 7,
  },
]

// Store mock answers in memory (persists during session)
let mockAnswers: any[] = [
  {
    id: 'answer-1',
    question: 'Wat zijn jullie openingstijden?',
    answer: 'Wij zijn geopend van maandag tot en met vrijdag van 9:00 tot 17:00 uur.',
    category: 'Openingstijden',
    detected_count: 12,
  },
  {
    id: 'answer-2',
    question: 'Waar kan ik parkeren?',
    answer: 'U kunt gratis parkeren op ons eigen parkeerterrein achter het gebouw. Er is ook betaald parkeren in de openbare parkeergarage op 100 meter afstand.',
    category: 'Locatie',
    detected_count: 5,
  },
]

let mockRulesState = [...MOCK_TRAINING_RULES]

// Training API
export const trainingApi = {
  getRules: async () => {
    try {
      const response = await api.get('/training/rules')
      return response.data
    } catch {
      // Return mock data when backend is not available
      return mockRulesState
    }
  },
  
  updateRule: async (id: string, isEnabled: boolean) => {
    try {
      const response = await api.patch(`/training/rules/${id}`, { is_enabled: isEnabled })
      return response.data
    } catch {
      // Update mock data
      mockRulesState = mockRulesState.map(rule => 
        rule.id === id ? { ...rule, is_enabled: isEnabled } : rule
      )
      return mockRulesState.find(r => r.id === id)
    }
  },
  
  getAnswers: async (category?: string) => {
    try {
      const response = await api.get('/training/answers', { params: { category } })
      return response.data
    } catch {
      // Return mock data
      if (category) {
        return mockAnswers.filter(a => a.category === category)
      }
      return mockAnswers
    }
  },
  
  createAnswer: async (data: any) => {
    try {
      const response = await api.post('/training/answers', data)
      return response.data
    } catch {
      // Add to mock data
      const newAnswer = {
        id: `answer-${Date.now()}`,
        ...data,
        detected_count: 0,
      }
      mockAnswers = [...mockAnswers, newAnswer]
      return newAnswer
    }
  },
  
  updateAnswer: async (id: string, data: any) => {
    try {
      const response = await api.patch(`/training/answers/${id}`, data)
      return response.data
    } catch {
      // Update mock data
      mockAnswers = mockAnswers.map(answer =>
        answer.id === id ? { ...answer, ...data } : answer
      )
      return mockAnswers.find(a => a.id === id)
    }
  },
  
  deleteAnswer: async (id: string) => {
    try {
      const response = await api.delete(`/training/answers/${id}`)
      return response.data
    } catch {
      // Remove from mock data
      mockAnswers = mockAnswers.filter(answer => answer.id !== id)
      return { success: true }
    }
  },
  
  getCategories: async () => {
    try {
      const response = await api.get('/training/categories')
      return response.data
    } catch {
      // Return unique categories from mock answers
      const categories = [...new Set(mockAnswers.map(a => a.category).filter(Boolean))]
      return categories
    }
  },
  
  getDetectedQuestions: async () => {
    try {
      const response = await api.get('/training/detected-questions')
      return response.data
    } catch {
      // Return mock detected questions
      return [
        { id: 'dq-1', question: 'Kunnen jullie ook op zaterdag?', occurrences: 8 },
        { id: 'dq-2', question: 'Wat kost een consult?', occurrences: 5 },
      ]
    }
  },

  dismissDetectedQuestion: async (questionId: string) => {
    const response = await api.post(`/training/detected-questions/${questionId}/dismiss`)
    return response.data
  },
}

// Calls API
export const callsApi = {
  list: async (params: any = {}) => {
    const response = await api.get('/calls', { params })
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/calls/${id}`)
    return response.data
  },
  
  getStats: async (startDate?: string, endDate?: string) => {
    const response = await api.get('/calls/stats', {
      params: { start_date: startDate, end_date: endDate },
    })
    return response.data
  },
  
  getActive: async () => {
    const response = await api.get('/calls/active/current')
    return response.data
  },
}

// Appointments API
export const appointmentsApi = {
  list: async (params: any = {}) => {
    const response = await api.get('/appointments', { params })
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/appointments/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/appointments', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/appointments/${id}`, data)
    return response.data
  },
  
  cancel: async (id: string, reason?: string) => {
    const response = await api.post(`/appointments/${id}/cancel`, { reason })
    return response.data
  },
  
  getToday: async () => {
    const response = await api.get('/appointments/today')
    return response.data
  },
  
  getUpcoming: async (days = 7) => {
    const response = await api.get('/appointments/upcoming', { params: { days } })
    return response.data
  },
}

// Notes API
export const notesApi = {
  list: async (params: any = {}) => {
    const response = await api.get('/notes', { params })
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/notes/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/notes', data)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/notes/${id}`, data)
    return response.data
  },
  
  resolve: async (id: string, notes?: string) => {
    const response = await api.post(`/notes/${id}/resolve`, { resolution_notes: notes })
    return response.data
  },
  
  reopen: async (id: string) => {
    const response = await api.post(`/notes/${id}/reopen`)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/notes/${id}`)
    return response.data
  },
  
  getActionRequired: async () => {
    const response = await api.get('/notes/action-required')
    return response.data
  },
}

// Company API
export const companyApi = {
  get: async () => {
    const response = await api.get('/companies/me')
    return response.data
  },
  
  update: async (data: any) => {
    const response = await api.patch('/companies/me', data)
    return response.data
  },
  
  getSubscription: async () => {
    const response = await api.get('/companies/me/subscription')
    return response.data
  },
  
  getPrivacySettings: async () => {
    const response = await api.get('/companies/me/privacy-settings')
    return response.data
  },
  
  updatePrivacySettings: async (data: any) => {
    const response = await api.patch('/companies/me/privacy-settings', data)
    return response.data
  },
}

// Users API
export const usersApi = {
  list: async () => {
    const response = await api.get('/users')
    return response.data
  },
  
  get: async (id: string) => {
    const response = await api.get(`/users/${id}`)
    return response.data
  },
  
  create: async (data: any) => {
    const response = await api.post('/users', data)
    return response.data
  },
  
  invite: async (data: { email: string; first_name: string; last_name: string; phone?: string; role: string }) => {
    const response = await api.post('/users/invite', data)
    return response.data
  },
  
  resendInvite: async (userId: string) => {
    const response = await api.post(`/users/resend-invite/${userId}`)
    return response.data
  },
  
  update: async (id: string, data: any) => {
    const response = await api.patch(`/users/${id}`, data)
    return response.data
  },
  
  delete: async (id: string) => {
    const response = await api.delete(`/users/${id}`)
    return response.data
  },
}

// Invite API (public endpoints)
export const inviteApi = {
  getInfo: async (token: string) => {
    const response = await api.get(`/auth/invite/${token}`)
    return response.data as {
      email: string
      first_name: string
      last_name: string
      company_name: string
      role: string
    }
  },
  
  accept: async (token: string, password: string) => {
    const response = await api.post('/auth/accept-invite', { token, password })
    return response.data as { access_token: string; refresh_token: string }
  },
}

// Admin API (superadmin only)
export const adminApi = {
  // System Prompts
  getPrompts: async (category?: string) => {
    const response = await api.get('/admin/prompts', { params: { category } })
    return response.data
  },
  
  getPrompt: async (id: string) => {
    const response = await api.get(`/admin/prompts/${id}`)
    return response.data
  },
  
  createPrompt: async (data: any) => {
    const response = await api.post('/admin/prompts', data)
    return response.data
  },
  
  updatePrompt: async (id: string, data: any) => {
    const response = await api.put(`/admin/prompts/${id}`, data)
    return response.data
  },
  
  deletePrompt: async (id: string) => {
    const response = await api.delete(`/admin/prompts/${id}`)
    return response.data
  },
  
  previewPrompt: async () => {
    const response = await api.get('/admin/prompts/preview')
    return response.data
  },
  
  seedPrompts: async () => {
    const response = await api.post('/admin/prompts/seed')
    return response.data
  },
  
  getCategories: async () => {
    const response = await api.get('/admin/categories')
    return response.data
  },
  
  // Metrics
  getMetricsOverview: async () => {
    const response = await api.get('/admin/metrics/overview')
    return response.data
  },
  
  getLatencyMetrics: async (hours: number = 24) => {
    const response = await api.get('/admin/metrics/latency', { params: { hours } })
    return response.data
  },
  
  getCostMetrics: async () => {
    const response = await api.get('/admin/metrics/costs')
    return response.data
  },
  
  getBusinessMetrics: async () => {
    const response = await api.get('/admin/metrics/business')
    return response.data
  },

  getAnalytics: async (period: string = '30d') => {
    const response = await api.get('/admin/analytics', { params: { period } })
    return response.data
  },

  getRealtimeVisitors: async () => {
    const response = await api.get('/admin/analytics/realtime')
    return response.data
  },
  
  // Customers
  getCustomers: async () => {
    const response = await api.get('/admin/customers')
    return response.data
  },
  
  getCustomerDetail: async (customerId: string) => {
    const response = await api.get(`/admin/customers/${customerId}`)
    return response.data
  },
  
  updateCustomerOverrides: async (customerId: string, overrides: any) => {
    const response = await api.put(`/admin/customers/${customerId}/overrides`, overrides)
    return response.data
  },
  
  toggleKillSwitch: async (customerId: string, enabled: boolean, reason?: string) => {
    const response = await api.post(`/admin/customers/${customerId}/kill-switch`, { enabled, reason })
    return response.data
  },
  
  deleteCustomer: async (customerId: string) => {
    const response = await api.delete(`/admin/customers/${customerId}`)
    return response.data
  },
  
  updateSubscription: async (customerId: string, data: { subscription_plan?: string; subscription_status?: string }) => {
    const response = await api.put(`/admin/customers/${customerId}/subscription`, data)
    return response.data
  },
  
  // Global Config
  getGlobalConfigs: async () => {
    const response = await api.get('/admin/config')
    return response.data
  },
  
  updateGlobalConfig: async (key: string, data: { value?: any; description?: string }) => {
    const response = await api.put(`/admin/config/${key}`, data)
    return response.data
  },
  
  seedGlobalConfigs: async () => {
    const response = await api.post('/admin/config/seed')
    return response.data
  },
  
  // Voices (ElevenLabs)
  getVoices: async () => {
    const response = await api.get('/admin/voices')
    return response.data
  },

  getVoicePreview: async (voiceId: string): Promise<Blob> => {
    const response = await api.get(`/admin/voice-preview/${voiceId}`, {
      responseType: 'blob',
    })
    return response.data
  },
  
  // Logs
  getRecentCalls: async (limit: number = 50, companyId?: string) => {
    const response = await api.get('/admin/calls/recent', { params: { limit, company_id: companyId } })
    return response.data
  },
  
  getCallTrace: async (callId: string) => {
    const response = await api.get(`/admin/calls/${callId}/trace`)
    return response.data
  },
}

// Payments API (Stripe)
export const paymentsApi = {
  createCheckoutSession: async (plan: string, interval: 'monthly' | 'yearly' = 'monthly') => {
    const response = await api.post('/payments/create-checkout-session', { plan, interval })
    return response.data
  },
  
  createPortalSession: async () => {
    const response = await api.post('/payments/create-portal-session', {})
    return response.data
  },
  
  getSubscription: async () => {
    const response = await api.get('/payments/subscription')
    return response.data
  },
}

// KVK API
export const kvkApi = {
  search: async (naam: string, limit: number = 5) => {
    const response = await api.get('/kvk/zoeken', { params: { naam, limit } })
    return response.data
  },

  validateBtw: async (btwNummer: string) => {
    const response = await api.get('/kvk/valideer-btw', { params: { btw_nummer: btwNummer } })
    return response.data
  },

  validateKvk: async (kvkNummer: string) => {
    const response = await api.get('/kvk/valideer-kvk', { params: { kvk_nummer: kvkNummer } })
    return response.data
  },
}

// Search API
export const searchApi = {
  search: async (q: string, limit: number = 10) => {
    const response = await api.get('/search', { params: { q, limit } })
    return response.data
  },
}

// Notifications API
export const notificationsApi = {
  list: async (limit: number = 20) => {
    const response = await api.get('/notifications', { params: { limit } })
    return response.data
  },

  markRead: async (notificationId: string) => {
    const response = await api.post(`/notifications/${notificationId}/read`)
    return response.data
  },

  markAllRead: async () => {
    const response = await api.post('/notifications/read-all')
    return response.data
  },
}
