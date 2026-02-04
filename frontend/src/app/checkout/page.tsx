'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Headphones, ArrowLeft, Loader2, CreditCard } from 'lucide-react'
import toast from 'react-hot-toast'
import { paymentsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

// Force dynamic rendering - this page uses searchParams and localStorage
export const dynamic = 'force-dynamic'

export default function CheckoutPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, company } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const plan = searchParams.get('plan') || 'starter'
  const interval = (searchParams.get('interval') as 'monthly' | 'yearly') || 'monthly'

  useEffect(() => {
    const startCheckout = async () => {
      // Check if user is logged in
      const token = localStorage.getItem('access_token')
      
      if (!token || !user) {
        // Not logged in - redirect to login with return URL
        const returnUrl = `/checkout?plan=${plan}&interval=${interval}`
        router.push(`/login?redirect=${encodeURIComponent(returnUrl)}`)
        return
      }

      // Validate plan
      if (!['starter', 'business', 'enterprise'].includes(plan)) {
        setError('Ongeldig pakket geselecteerd')
        setIsLoading(false)
        return
      }

      // Enterprise is "op aanvraag" - redirect to contact
      if (plan === 'enterprise') {
        router.push('/contact')
        return
      }

      // Start Stripe checkout
      try {
        const data = await paymentsApi.createCheckoutSession(plan, interval)
        
        if (data.checkout_url) {
          // Redirect to Stripe
          window.location.href = data.checkout_url
        } else {
          setError('Kon checkout niet starten')
          setIsLoading(false)
        }
      } catch (err: any) {
        console.error('Checkout error:', err)
        const message = err.response?.data?.detail || 'Er ging iets mis bij het starten van de checkout'
        setError(message)
        toast.error(message)
        setIsLoading(false)
      }
    }

    startCheckout()
  }, [plan, interval, user, router])

  // Show loading state
  if (isLoading && !error) {
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
          <div className="text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-primary-600 mx-auto mb-6">
              <CreditCard className="h-8 w-8 text-white" />
            </div>
            <div className="flex items-center justify-center gap-3 mb-4">
              <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
              <span className="text-lg text-gray-700">Checkout wordt gestart...</span>
            </div>
            <p className="text-gray-500">
              Je wordt doorgestuurd naar onze beveiligde betaalpagina.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Show error state
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
        <div className="w-full max-w-md text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-red-100 mx-auto mb-6">
            <CreditCard className="h-8 w-8 text-red-600" />
          </div>
          <h1 className="text-2xl font-display font-bold text-gray-900 mb-4">
            Er ging iets mis
          </h1>
          <p className="text-gray-600 mb-8">
            {error || 'Kon de checkout niet starten. Probeer het opnieuw.'}
          </p>
          <div className="space-y-3">
            <Link
              href={`/checkout?plan=${plan}&interval=${interval}`}
              className="block w-full rounded-lg bg-primary-600 py-3 text-center text-white font-medium hover:bg-primary-700"
            >
              Opnieuw proberen
            </Link>
            <Link
              href="/"
              className="block w-full rounded-lg border border-gray-300 py-3 text-center text-gray-700 font-medium hover:bg-gray-50"
            >
              Terug naar home
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
