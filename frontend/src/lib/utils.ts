import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, isToday, isYesterday } from 'date-fns'
import { nl } from 'date-fns/locale'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date, formatStr = 'dd MMM yyyy') {
  const d = typeof date === 'string' ? new Date(date) : date
  return format(d, formatStr, { locale: nl })
}

export function formatDateTime(date: string | Date) {
  const d = typeof date === 'string' ? new Date(date) : date
  return format(d, "dd MMM yyyy 'om' HH:mm", { locale: nl })
}

export function formatTime(date: string | Date) {
  const d = typeof date === 'string' ? new Date(date) : date
  return format(d, 'HH:mm', { locale: nl })
}

export function formatRelativeDate(date: string | Date) {
  const d = typeof date === 'string' ? new Date(date) : date
  
  if (isToday(d)) {
    return `Vandaag om ${format(d, 'HH:mm')}`
  }
  
  if (isYesterday(d)) {
    return `Gisteren om ${format(d, 'HH:mm')}`
  }
  
  return formatDateTime(d)
}

export function formatRelativeTime(date: string | Date) {
  const d = typeof date === 'string' ? new Date(date) : date
  return formatDistanceToNow(d, { addSuffix: true, locale: nl })
}

export function formatDuration(seconds: number) {
  if (seconds < 60) {
    return `${seconds}s`
  }
  
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  
  return `${hours}u ${remainingMinutes}m`
}

export function formatPhoneNumber(phone: string) {
  // Format Dutch phone numbers
  const cleaned = phone.replace(/\D/g, '')
  
  if (cleaned.startsWith('31')) {
    // International format +31
    const local = cleaned.slice(2)
    if (local.length === 9) {
      return `+31 ${local.slice(0, 1)} ${local.slice(1, 4)} ${local.slice(4, 6)} ${local.slice(6)}`
    }
  }
  
  if (cleaned.startsWith('0') && cleaned.length === 10) {
    // Local Dutch format
    return `${cleaned.slice(0, 3)} ${cleaned.slice(3, 6)} ${cleaned.slice(6, 8)} ${cleaned.slice(8)}`
  }
  
  return phone
}

export function getInitials(firstName: string, lastName: string) {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase()
}

export function truncate(str: string, length: number) {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function capitalize(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase()
}

export function getStatusColor(status: string) {
  const colors: Record<string, string> = {
    available: 'text-green-600 bg-green-100',
    busy: 'text-amber-600 bg-amber-100',
    offline: 'text-gray-600 bg-gray-100',
    maintenance: 'text-red-600 bg-red-100',
    completed: 'text-green-600 bg-green-100',
    ready: 'text-green-600 bg-green-100',
    in_progress: 'text-blue-600 bg-blue-100',
    missed: 'text-red-600 bg-red-100',
    voicemail: 'text-purple-600 bg-purple-100',
    confirmed: 'text-green-600 bg-green-100',
    cancelled: 'text-red-600 bg-red-100',
    pending: 'text-amber-600 bg-amber-100',
    crawling: 'text-blue-600 bg-blue-100',
    processing: 'text-blue-600 bg-blue-100',
    outdated: 'text-amber-600 bg-amber-100',
    indexing: 'text-blue-600 bg-blue-100',
    failed: 'text-red-600 bg-red-100',
  }
  return colors[status] || 'text-gray-600 bg-gray-100'
}

export function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    available: 'Beschikbaar',
    busy: 'In gesprek',
    offline: 'Offline',
    maintenance: 'Onderhoud',
    completed: 'Afgerond',
    ready: 'Gereed',
    in_progress: 'Lopend',
    missed: 'Gemist',
    voicemail: 'Voicemail',
    confirmed: 'Bevestigd',
    cancelled: 'Geannuleerd',
    pending: 'In afwachting',
    crawling: 'Indexeren...',
    processing: 'Verwerken...',
    outdated: 'Verouderd',
    indexing: 'Indexeren',
    failed: 'Mislukt',
    ringing: 'Rinkelt',
    held: 'Gereserveerd',
  }
  return labels[status] || status
}

export function getPriorityColor(priority: string) {
  const colors: Record<string, string> = {
    low: 'text-gray-600 bg-gray-100',
    normal: 'text-blue-600 bg-blue-100',
    high: 'text-amber-600 bg-amber-100',
    urgent: 'text-red-600 bg-red-100',
  }
  return colors[priority] || 'text-gray-600 bg-gray-100'
}

export function getPriorityLabel(priority: string) {
  const labels: Record<string, string> = {
    low: 'Laag',
    normal: 'Normaal',
    high: 'Hoog',
    urgent: 'Urgent',
  }
  return labels[priority] || priority
}
