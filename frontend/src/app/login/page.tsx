'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Headphones, ArrowLeft, Zap } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { authApi, companyApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const loginSchema = z.object({
  email: z.string().email('Voer een geldig e-mailadres in'),
  password: z.string().min(1, 'Wachtwoord is verplicht'),
})

type LoginForm = z.infer<typeof loginSchema>

// Google icon SVG component
function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  )
}

export default function LoginPage() {
  const router = useRouter()
  const { setAuth } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)
  const [isDevLoading, setIsDevLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true)
    try {
      const response = await authApi.login(data.email, data.password)
      
      // Store tokens
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)
      
      // Get user and company info
      const [user, company] = await Promise.all([
        authApi.getMe(),
        companyApi.get(),
      ])
      
      setAuth(user, company)
      
      toast.success('Welkom terug!')
      router.push('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Inloggen mislukt')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setIsGoogleLoading(true)
    try {
      const { auth_url, state } = await authApi.getGoogleUrl()
      // Store state in sessionStorage for verification after redirect
      sessionStorage.setItem('google_oauth_state', state)
      // Redirect to Google
      window.location.href = auth_url
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Kon Google login niet starten')
      setIsGoogleLoading(false)
    }
  }

  const handleDevLogin = () => {
    setIsDevLoading(true)
    
    // Mock user data - no backend needed
    const mockUser = {
      id: 'dev-user-001',
      email: 'dev@klantenservice.ai',
      first_name: 'Dev',
      last_name: 'Admin',
      role: 'owner',
      company_id: 'dev-company-001',
    }
    
    const mockCompany = {
      id: 'dev-company-001',
      name: 'Dev Company',
      slug: 'dev-company',
      subscription_plan: 'professional',
      max_ai_workers: 10,
    }
    
    // Set fake tokens (for API interceptor compatibility)
    localStorage.setItem('access_token', 'dev-token-mock')
    localStorage.setItem('refresh_token', 'dev-refresh-mock')
    
    // Set auth state
    setAuth(mockUser, mockCompany)
    
    toast.success('Dev login succesvol!')
    router.push('/dashboard')
    
    setIsDevLoading(false)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Back link */}
      <div className="p-4">
        <Link
          href="/"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Terug naar home
        </Link>
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="text-center mb-8">
            <Link href="/" className="inline-flex items-center gap-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600">
                <Headphones className="h-6 w-6 text-white" />
              </div>
            </Link>
            <h1 className="mt-6 text-2xl font-display font-bold text-gray-900">
              Welkom terug
            </h1>
            <p className="mt-2 text-gray-600">
              Log in op uw klantenservice.ai account
            </p>
          </div>

          {/* Form */}
          <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-8">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <Input
                label="E-mailadres"
                type="email"
                placeholder="uw@email.nl"
                error={errors.email?.message}
                {...register('email')}
              />
              <Input
                label="Wachtwoord"
                type="password"
                placeholder="••••••••"
                error={errors.password?.message}
                {...register('password')}
              />

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600">Onthoud mij</span>
                </label>
                <Link
                  href="/forgot-password"
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  Wachtwoord vergeten?
                </Link>
              </div>

              <Button
                type="submit"
                className="w-full"
                size="lg"
                isLoading={isLoading}
              >
                Inloggen
              </Button>
            </form>

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-white px-4 text-gray-500">of</span>
              </div>
            </div>

            {/* Google Login Button */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={isGoogleLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-700 font-medium hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isGoogleLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600" />
              ) : (
                <GoogleIcon className="h-5 w-5" />
              )}
              Doorgaan met Google
            </button>

            {/* Dev Login Button - Mock login without backend */}
            <button
              type="button"
              onClick={handleDevLogin}
              disabled={isDevLoading}
              className="mt-3 w-full flex items-center justify-center gap-3 px-4 py-3 border-2 border-dashed border-amber-400 rounded-lg bg-amber-50 text-amber-700 font-medium hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isDevLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-300 border-t-amber-600" />
              ) : (
                <Zap className="h-5 w-5" />
              )}
              Dev Login (Admin)
            </button>
          </div>

          {/* Register link */}
          <p className="mt-6 text-center text-sm text-gray-600">
            Nog geen account?{' '}
            <Link href="/register" className="text-primary-600 hover:text-primary-700 font-medium">
              Maak een account aan
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
