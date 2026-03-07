'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from './Sidebar'
import { TestCallWidget } from '@/components/TestCallWidget'
import { useSidebarStore, useAuthStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { authApi } from '@/lib/api'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter()
  const { isCollapsed } = useSidebarStore()
  const { isAuthenticated, user } = useAuthStore()
  const [isCheckingVerification, setIsCheckingVerification] = useState(true)

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('access_token')
    if (!token && !isAuthenticated) {
      router.push('/login')
      return
    }

    // Check if user is verified
    const checkVerification = async () => {
      try {
        const userData = await authApi.getMe()
        // If user is not verified and not a Google OAuth user, redirect to verify
        if (!userData.is_verified && userData.oauth_provider !== 'google') {
          router.push('/verify')
          return
        }
      } catch (error) {
        // If API call fails, redirect to login
        router.push('/login')
        return
      }
      setIsCheckingVerification(false)
    }

    checkVerification()
  }, [isAuthenticated, router])

  // Show loading state while checking verification
  if (isCheckingVerification) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">Laden...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <main
        className={cn(
          'min-h-screen transition-all duration-300',
          isCollapsed ? 'md:ml-20' : 'md:ml-64'
        )}
      >
        {children}
      </main>
      <TestCallWidget />
    </div>
  )
}
