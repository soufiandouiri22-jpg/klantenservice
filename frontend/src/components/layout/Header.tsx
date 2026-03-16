'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Bell,
  User,
  Menu,
  CheckCheck,
  MessageSquare,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { useAuthStore, useSidebarStore } from '@/lib/store'
import { getInitials } from '@/lib/utils'
import { notificationsApi } from '@/lib/api'

interface HeaderProps {
  title?: string
  description?: string
  actions?: React.ReactNode
  showActionsOnMobile?: boolean
}

const notifIcons: Record<string, React.ElementType> = {
  detected_question: MessageSquare,
  call_error: AlertTriangle,
  note_action: StickyNote,
  website_indexed: CheckCircle,
  website_failed: XCircle,
  appointment_new: Calendar,
  appointment_cancelled: XCircle,
}

export function Header({ title, description, actions, showActionsOnMobile = false }: HeaderProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const { setMobileOpen } = useSidebarStore()

  const [isNotifOpen, setIsNotifOpen] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)

  const { data: notifData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(),
    refetchInterval: 30_000,
    retry: 1,
    retryDelay: 10_000,
  })

  const markReadMutation = useMutation({
    mutationFn: notificationsApi.markRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleNotifClick = useCallback((notif: any) => {
    if (!notif.is_read) {
      markReadMutation.mutate(notif.id)
    }
    if (notif.url) {
      router.push(notif.url)
    }
    setIsNotifOpen(false)
  }, [router, markReadMutation])

  const unreadCount = notifData?.unread_count ?? 0

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    const diffHour = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)

    if (diffMin < 1) return 'Zojuist'
    if (diffMin < 60) return `${diffMin}m geleden`
    if (diffHour < 24) return `${diffHour}u geleden`
    if (diffDay < 7) return `${diffDay}d geleden`
    return date.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
  }

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
        <div className="flex h-16 items-center justify-between px-4 sm:px-6">
          {/* Left: Hamburger + Page title */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              {title && (
                <h1 className="text-lg sm:text-xl font-semibold text-gray-900 truncate">{title}</h1>
              )}
              {description && (
                <p className="text-sm text-gray-500 hidden sm:block">{description}</p>
              )}
            </div>
          </div>

          {/* Right: Actions and user */}
          <div className="flex items-center gap-2 sm:gap-4">
            {/* Notifications */}
            <div className="relative" ref={notifRef}>
              <button
                onClick={() => setIsNotifOpen(!isNotifOpen)}
                className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              >
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4.5 w-4.5 min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>

              {isNotifOpen && (
                <div className="fixed left-4 right-4 top-[4.25rem] sm:absolute sm:left-auto sm:top-full sm:right-0 sm:mt-1 sm:w-96 bg-white rounded-lg border border-gray-200 shadow-lg overflow-hidden z-50">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                    <h3 className="text-sm font-semibold text-gray-900">Notificaties</h3>
                    {unreadCount > 0 && (
                      <button
                        onClick={() => markAllReadMutation.mutate()}
                        className="inline-flex items-center text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        <CheckCheck className="h-3.5 w-3.5 mr-1" />
                        Alles gelezen
                      </button>
                    )}
                  </div>
                  <div className="max-h-80 sm:max-h-96 overflow-y-auto">
                    {notifData?.notifications?.length > 0 ? (
                      notifData.notifications.map((notif: any) => {
                        const Icon = notifIcons[notif.type] || Bell
                        return (
                          <button
                            key={notif.id}
                            onClick={() => handleNotifClick(notif)}
                            className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors border-b border-gray-50 last:border-0 ${
                              notif.is_read ? 'hover:bg-gray-50' : 'bg-primary-50/30 hover:bg-primary-50/50'
                            }`}
                          >
                            <div className={`flex-shrink-0 mt-0.5 h-8 w-8 rounded-full flex items-center justify-center ${
                              notif.is_read ? 'bg-gray-100' : 'bg-primary-100'
                            }`}>
                              <Icon className={`h-4 w-4 ${notif.is_read ? 'text-gray-500' : 'text-primary-600'}`} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm truncate ${notif.is_read ? 'text-gray-700' : 'font-medium text-gray-900'}`}>
                                {notif.title}
                              </p>
                              {notif.message && (
                                <p className="text-xs text-gray-500 truncate mt-0.5">{notif.message}</p>
                              )}
                              <p className="text-xs text-gray-400 mt-1">{formatTimeAgo(notif.created_at)}</p>
                            </div>
                            {!notif.is_read && (
                              <span className="flex-shrink-0 mt-2 h-2 w-2 rounded-full bg-primary-500" />
                            )}
                          </button>
                        )
                      })
                    ) : (
                      <div className="p-8 text-center">
                        <Bell className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">Geen notificaties</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {actions && <div className={showActionsOnMobile ? '' : 'hidden md:block'}>{actions}</div>}

            {/* User menu */}
            <div className="flex items-center gap-3 border-l border-gray-200 pl-3 sm:pl-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-100 text-sm font-medium text-primary-700">
                {user ? getInitials(user.first_name, user.last_name) : <User className="h-5 w-5" />}
              </div>
              <div className="hidden md:block">
                <p className="text-sm font-medium text-gray-900">
                  {user?.first_name} {user?.last_name}
                </p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
            </div>
          </div>
        </div>
      </header>
    </>
  )
}
