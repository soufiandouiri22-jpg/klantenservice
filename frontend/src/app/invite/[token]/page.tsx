'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { ArrowLeft, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import Image from 'next/image'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { inviteApi, authApi, companyApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const acceptInviteSchema = z.object({
  password: z
    .string()
    .min(8, 'Wachtwoord moet minimaal 8 karakters zijn')
    .regex(/[A-Z]/, 'Wachtwoord moet minimaal één hoofdletter bevatten')
    .regex(/[a-z]/, 'Wachtwoord moet minimaal één kleine letter bevatten')
    .regex(/[0-9]/, 'Wachtwoord moet minimaal één cijfer bevatten'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Wachtwoorden komen niet overeen',
  path: ['confirmPassword'],
})

type AcceptInviteForm = z.infer<typeof acceptInviteSchema>

interface InviteInfo {
  email: string
  first_name: string
  last_name: string
  company_name: string
  role: string
}

export default function AcceptInvitePage() {
  const router = useRouter()
  const params = useParams()
  const token = params.token as string
  const { setAuth } = useAuthStore()
  
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AcceptInviteForm>({
    resolver: zodResolver(acceptInviteSchema),
  })

  useEffect(() => {
    const fetchInviteInfo = async () => {
      try {
        const info = await inviteApi.getInfo(token)
        setInviteInfo(info)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Deze uitnodiging is ongeldig of verlopen')
      } finally {
        setIsLoading(false)
      }
    }

    if (token) {
      fetchInviteInfo()
    }
  }, [token])

  const onSubmit = async (data: AcceptInviteForm) => {
    setIsSubmitting(true)
    try {
      const response = await inviteApi.accept(token, data.password)
      
      // Store tokens
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)
      
      // Get user and company info
      const [user, company] = await Promise.all([
        authApi.getMe(),
        companyApi.get(),
      ])
      
      setAuth(user, company)
      
      toast.success('Account geactiveerd! Welkom bij het team.')
      router.push('/dashboard')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Er ging iets mis bij het activeren van je account')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getRoleDutch = (role: string) => {
    const roles: Record<string, string> = {
      owner: 'Eigenaar',
      admin: 'Admin',
      manager: 'Manager',
      user: 'Gebruiker',
      viewer: 'Kijker',
    }
    return roles[role] || role
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600 mx-auto" />
          <p className="mt-4 text-gray-600">Uitnodiging laden...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <div className="p-4">
          <Link
            href="/login"
            className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Naar login
          </Link>
        </div>

        <div className="flex-1 flex items-center justify-center px-4">
          <div className="w-full max-w-md text-center">
            <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-8">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
                <XCircle className="h-8 w-8 text-red-600" />
              </div>
              <h1 className="mt-6 text-xl font-semibold text-gray-900">
                Uitnodiging ongeldig
              </h1>
              <p className="mt-2 text-gray-600">{error}</p>
              <Link href="/login">
                <Button className="mt-6 w-full">
                  Ga naar login
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Success state - show form
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
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
              <Image src="/logo-icon.png" alt="klantenservice.ai" width={48} height={48} className="h-12 w-12 rounded-xl" />
            </Link>
            <h1 className="mt-6 text-2xl font-display font-bold text-gray-900">
              Activeer je account
            </h1>
            <p className="mt-2 text-gray-600">
              Stel een wachtwoord in om je account te activeren
            </p>
          </div>

          {/* Info Card */}
          <div className="bg-primary-50 border border-primary-100 rounded-xl p-4 mb-6">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-primary-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-primary-900">
                  Je bent uitgenodigd voor {inviteInfo?.company_name}
                </p>
                <p className="text-sm text-primary-700 mt-1">
                  Rol: {getRoleDutch(inviteInfo?.role || 'viewer')}
                </p>
              </div>
            </div>
          </div>

          {/* Form */}
          <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-8">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              {/* Read-only fields */}
              <div className="space-y-4 pb-4 border-b border-gray-100">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Naam
                  </label>
                  <p className="text-gray-900">
                    {inviteInfo?.first_name} {inviteInfo?.last_name}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    E-mailadres
                  </label>
                  <p className="text-gray-900">{inviteInfo?.email}</p>
                </div>
              </div>

              {/* Password fields */}
              <Input
                label="Wachtwoord"
                type="password"
                placeholder="••••••••"
                helperText="Min. 8 karakters met hoofdletter, kleine letter en cijfer"
                error={errors.password?.message}
                {...register('password')}
              />
              <Input
                label="Wachtwoord bevestigen"
                type="password"
                placeholder="••••••••"
                error={errors.confirmPassword?.message}
                {...register('confirmPassword')}
              />

              <Button
                type="submit"
                className="w-full"
                size="lg"
                isLoading={isSubmitting}
              >
                Account activeren
              </Button>
            </form>
          </div>

          {/* Already have account link */}
          <p className="mt-6 text-center text-sm text-gray-600">
            Al een account?{' '}
            <Link href="/login" className="text-primary-600 hover:text-primary-700 font-medium">
              Log hier in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
