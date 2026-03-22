'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Users,
  Phone,
  Calendar,
  Plug,
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
  X,
} from 'lucide-react'
import Image from 'next/image'
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
  { name: 'Integraties', href: '/dashboard/integrations', icon: Plug },
]

const bottomNavigation = [
  { name: 'Instellingen', href: '/dashboard/settings', icon: Settings },
]

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  const { isCollapsed, toggle } = useSidebarStore()
  const { company, logout } = useAuthStore()
  const isMobile = !!onNavigate

  const showLabel = isMobile || !isCollapsed

  return (
    <>
      {/* Logo */}
      <div className={cn("flex h-16 flex-shrink-0 items-center border-b border-gray-800/60", showLabel ? "justify-between px-4" : "justify-center")}>
        <Link href="/dashboard" className="flex items-center gap-2" onClick={onNavigate}>
          <Image src="/logo-icon.png" alt="klantenservice.ai" width={36} height={36} className="h-9 w-9 rounded-lg flex-shrink-0" />
          {showLabel && (
            <span className="font-display text-lg font-bold text-white">
              klantenservice<span className="text-primary-400">.ai</span>
            </span>
          )}
        </Link>
        {isMobile && (
          <button onClick={onNavigate} className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-800 hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Company name */}
      {showLabel && company && (
        <div className="flex-shrink-0 border-b border-gray-800/60 px-4 py-3">
          <p className="text-xs font-medium text-gray-500">Bedrijf</p>
          <p className="truncate text-sm font-medium text-gray-200">{company.name}</p>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-0.5">
          {navigation.map((item) => {
            const isActive = item.href === '/dashboard'
              ? pathname === '/dashboard'
              : pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-white/10 text-white'
                      : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                  )}
                >
                  <item.icon className={cn('h-[18px] w-[18px] flex-shrink-0', isActive ? 'text-white' : 'text-gray-500')} />
                  {showLabel && <span>{item.name}</span>}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Bottom navigation */}
      <div className="flex-shrink-0 border-t border-gray-800/60 p-3">
        <ul className="space-y-0.5">
          {bottomNavigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-white/10 text-white'
                      : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                  )}
                >
                  <item.icon className={cn('h-[18px] w-[18px] flex-shrink-0', isActive ? 'text-white' : 'text-gray-500')} />
                  {showLabel && <span>{item.name}</span>}
                </Link>
              </li>
            )
          })}
          <li>
            <button
              onClick={() => { onNavigate?.(); logout() }}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-400 hover:bg-white/5 hover:text-gray-200 transition-colors"
            >
              <LogOut className="h-[18px] w-[18px] flex-shrink-0 text-gray-500" />
              {showLabel && <span>Uitloggen</span>}
            </button>
          </li>
        </ul>
      </div>
    </>
  )
}

export function Sidebar() {
  const { isCollapsed, isMobileOpen, setMobileOpen, toggle } = useSidebarStore()
  const pathname = usePathname()

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname, setMobileOpen])

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 hidden md:flex h-screen flex-col bg-gray-950 transition-all duration-300',
          isCollapsed ? 'w-20' : 'w-64'
        )}
      >
        <SidebarContent />
        <button
          onClick={toggle}
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 bg-white shadow-sm hover:bg-gray-50 transition-colors"
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4 text-gray-600" /> : <ChevronLeft className="h-4 w-4 text-gray-600" />}
        </button>
      </aside>

      {/* Mobile sidebar overlay + drawer */}
      <AnimatePresence>
        {isMobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 bg-black/60 md:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 z-50 flex h-screen w-72 flex-col bg-gray-950 shadow-xl md:hidden pb-[max(1.5rem,env(safe-area-inset-bottom))]"
            >
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
