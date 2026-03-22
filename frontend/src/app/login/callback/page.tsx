'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import Image from 'next/image'
import { authApi, companyApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

function CallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setAuth } = useAuthStore()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const errorParam = searchParams.get('error')

      // Handle Google OAuth errors
      if (errorParam) {
        setError('Google login is geannuleerd')
        setTimeout(() => router.push('/login'), 2000)
        return
      }

      if (!code || !state) {
        setError('Ongeldige callback parameters')
        setTimeout(() => router.push('/login'), 2000)
        return
      }

      // Verify state matches what we stored
      const storedState = sessionStorage.getItem('google_oauth_state')
      if (state !== storedState) {
        setError('Ongeldige state token - mogelijke CSRF aanval')
        setTimeout(() => router.push('/login'), 2000)
        return
      }

      // Get stored redirect URL before clearing
      const redirectUrl = sessionStorage.getItem('auth_redirect_url') || '/dashboard'
      
      // Clear stored state and redirect URL
      sessionStorage.removeItem('google_oauth_state')
      sessionStorage.removeItem('auth_redirect_url')

      try {
        // Exchange code for tokens
        const tokens = await authApi.googleCallback(code, state)
        
        // Store tokens — Google login is always remembered
        localStorage.setItem('access_token', tokens.access_token)
        localStorage.setItem('refresh_token', tokens.refresh_token)
        localStorage.setItem('remember_me', 'true')
        
        // Get user and company info
        const [user, company] = await Promise.all([
          authApi.getMe(),
          companyApi.get(),
        ])
        
        setAuth(user, company)
        
        toast.success('Welkom!')
        router.push(redirectUrl)
      } catch (err: any) {
        const message = err.response?.data?.detail || 'Google login mislukt'
        setError(message)
        toast.error(message)
        setTimeout(() => router.push('/login'), 3000)
      }
    }

    handleCallback()
  }, [searchParams, router, setAuth])

  return (
    <>
      {error ? (
        <>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">
            Er ging iets mis
          </h1>
          <p className="text-gray-600 mb-4">{error}</p>
          <p className="text-sm text-gray-500">
            U wordt doorgestuurd naar de loginpagina...
          </p>
        </>
      ) : (
        <>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">
            Bezig met inloggen...
          </h1>
          <p className="text-gray-600 mb-6">
            Even geduld, we verwerken uw Google login.
          </p>
          {/* Loading spinner */}
          <div className="flex justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600" />
          </div>
        </>
      )}
    </>
  )
}

function LoadingFallback() {
  return (
    <>
      <h1 className="text-xl font-semibold text-gray-900 mb-2">
        Laden...
      </h1>
      <div className="flex justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600" />
      </div>
    </>
  )
}

export default function GoogleCallbackPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        {/* Logo */}
        <div className="flex justify-center mb-6">
          <Image src="/logo-icon.png" alt="klantenservice.ai" width={64} height={64} className="h-16 w-16 rounded-xl" />
        </div>

        <Suspense fallback={<LoadingFallback />}>
          <CallbackContent />
        </Suspense>
      </div>
    </div>
  )
}
