'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function TermsRedirect() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/voorwaarden')
  }, [router])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600 mx-auto" />
        <p className="mt-4 text-gray-600">Doorsturen naar voorwaarden...</p>
      </div>
    </div>
  )
}
