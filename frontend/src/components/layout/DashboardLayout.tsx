'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from './Sidebar'
import { useSidebarStore, useAuthStore } from '@/lib/store'
import { cn } from '@/lib/utils'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter()
  const { isCollapsed } = useSidebarStore()
  const { isAuthenticated, user } = useAuthStore()

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('access_token')
    if (!token && !isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, router])

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <main
        className={cn(
          'min-h-screen transition-all duration-300',
          isCollapsed ? 'ml-20' : 'ml-64'
        )}
      >
        {children}
      </main>
    </div>
  )
}
