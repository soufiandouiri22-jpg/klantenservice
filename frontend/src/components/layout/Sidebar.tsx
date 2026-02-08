'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Users,
  Phone,
  Calendar,
  Globe,
  GraduationCap,
  PhoneIncoming,
  ClipboardList,
  StickyNote,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Headphones,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSidebarStore, useAuthStore } from '@/lib/store'

const navigation = [
  { name: 'Overzicht', href: '/dashboard', icon: LayoutDashboard },
  { name: 'AI-medewerkers', href: '/dashboard/ai-workers', icon: Headphones },
  { name: 'Telefonie', href: '/dashboard/phone', icon: Phone },
  { name: 'Agenda', href: '/dashboard/calendar', icon: Calendar },
  { name: 'Website-kennis', href: '/dashboard/knowledge', icon: Globe },
  { name: 'Training', href: '/dashboard/training', icon: GraduationCap },
  { name: 'Gesprekken', href: '/dashboard/calls', icon: PhoneIncoming },
  { name: 'Afspraken', href: '/dashboard/appointments', icon: ClipboardList },
  { name: 'Notities', href: '/dashboard/notes', icon: StickyNote },
]

const bottomNavigation = [
  { name: 'Instellingen', href: '/dashboard/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { isCollapsed, toggle } = useSidebarStore()
  const { company, logout } = useAuthStore()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-gray-200 bg-white transition-all duration-300',
        isCollapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-gray-100 px-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600">
            <Headphones className="h-5 w-5 text-white" />
          </div>
          {!isCollapsed && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-display text-lg font-bold text-gray-900"
            >
              klantenservice<span className="text-primary-600">.ai</span>
            </motion.span>
          )}
        </Link>
      </div>

      {/* Company name */}
      {!isCollapsed && company && (
        <div className="border-b border-gray-100 px-4 py-3">
          <p className="text-xs font-medium text-gray-500">Bedrijf</p>
          <p className="truncate text-sm font-medium text-gray-900">
            {company.name}
          </p>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-1">
          {navigation.map((item) => {
            // For the dashboard root, only match exactly to avoid highlighting when on sub-pages
            const isActive = item.href === '/dashboard' 
              ? pathname === '/dashboard'
              : pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  )}
                >
                  <item.icon
                    className={cn(
                      'h-5 w-5 flex-shrink-0',
                      isActive ? 'text-primary-600' : 'text-gray-400'
                    )}
                  />
                  {!isCollapsed && <span>{item.name}</span>}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Bottom navigation */}
      <div className="border-t border-gray-100 p-4">
        <ul className="space-y-1">
          {bottomNavigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  )}
                >
                  <item.icon
                    className={cn(
                      'h-5 w-5 flex-shrink-0',
                      isActive ? 'text-primary-600' : 'text-gray-400'
                    )}
                  />
                  {!isCollapsed && <span>{item.name}</span>}
                </Link>
              </li>
            )
          })}
          <li>
            <button
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
            >
              <LogOut className="h-5 w-5 flex-shrink-0 text-gray-400" />
              {!isCollapsed && <span>Uitloggen</span>}
            </button>
          </li>
        </ul>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 bg-white shadow-sm hover:bg-gray-50 transition-colors"
      >
        {isCollapsed ? (
          <ChevronRight className="h-4 w-4 text-gray-600" />
        ) : (
          <ChevronLeft className="h-4 w-4 text-gray-600" />
        )}
      </button>
    </aside>
  )
}
