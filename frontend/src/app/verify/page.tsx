'use client'

import { Suspense, useState, useRef, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { Headphones, ArrowLeft, Mail, RefreshCw, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api, authApi, companyApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

function VerifyContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setAuth } = useAuthStore()
  const [email, setEmail] = useState<string>('')
  const [code, setCode] = useState(['', '', '', '', '', ''])
  const [isVerifying, setIsVerifying] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Get email from query parameter
  useEffect(() => {
    const emailParam = searchParams.get('email')
    if (emailParam) {
      setEmail(emailParam)
    } else {
      // No email in URL - redirect to register
      toast.error('Geen e-mailadres gevonden. Start de registratie opnieuw.')
      router.push('/register')
    }
  }, [searchParams, router])

  // Cooldown timer
  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [cooldown])

  const handleChange = (index: number, value: string) => {
    // Only allow digits
    if (value && !/^\d$/.test(value)) return

    const newCode = [...code]
    newCode[index] = value
    setCode(newCode)

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all digits entered
    if (value && index === 5 && newCode.every(d => d !== '')) {
      handleVerify(newCode.join(''))
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    // Handle backspace
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (pastedData.length === 6) {
      const newCode = pastedData.split('')
      setCode(newCode)
      inputRefs.current[5]?.focus()
      handleVerify(pastedData)
    }
  }

  const handleVerify = async (codeString?: string) => {
    const verifyCode = codeString || code.join('')
    if (verifyCode.length !== 6) {
      toast.error('Voer de volledige 6-cijferige code in')
      return
    }

    if (!email) {
      toast.error('Geen e-mailadres gevonden')
      return
    }

    setIsVerifying(true)
    try {
      // Call verify-code endpoint with email and code (no auth required)
      const response = await api.post('/auth/verify-code', {
        email: email,
        code: verifyCode,
      })
      
      // Store tokens received from verification
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)
      
      // Fetch user and company data
      const [userData, companyData] = await Promise.all([
        authApi.getMe(),
        companyApi.get(),
      ])
      setAuth(userData, companyData)
      
      toast.success('E-mail succesvol geverifieerd!')
      router.push('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Verificatie mislukt')
      // Clear the code on error
      setCode(['', '', '', '', '', ''])
      inputRefs.current[0]?.focus()
    } finally {
      setIsVerifying(false)
    }
  }

  const handleResend = async () => {
    if (cooldown > 0) return
    
    if (!email) {
      toast.error('Geen e-mailadres gevonden')
      return
    }
    
    setIsResending(true)
    try {
      // Call resend-code endpoint with email (no auth required)
      await api.post('/auth/resend-code', {
        email: email,
      })
      toast.success('Nieuwe verificatiecode verzonden')
      setCooldown(60)
      // Clear current code
      setCode(['', '', '', '', '', ''])
      inputRefs.current[0]?.focus()
    } catch (error: any) {
      const detail = error.response?.data?.detail
      if (detail?.includes('Wacht nog')) {
        // Extract seconds from error message
        const match = detail.match(/(\d+) seconden/)
        if (match) {
          setCooldown(parseInt(match[1]))
        }
      }
      toast.error(detail || 'Kon geen nieuwe code versturen')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="p-4">
        <Link
          href="/register"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Terug
        </Link>
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="mb-8 text-center">
            <Link href="/" className="inline-flex items-center gap-2 justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary-600">
                <Headphones className="h-6 w-6 text-white" />
              </div>
            </Link>
          </div>

          {/* Card */}
          <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-6 sm:p-8">
            <div className="text-center mb-8">
              <div className="mx-auto w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4">
                <Mail className="h-8 w-8 text-primary-600" />
              </div>
              <h1 className="text-2xl font-display font-bold text-gray-900">
                Verifieer uw e-mail
              </h1>
              <p className="mt-2 text-gray-600">
                We hebben een 6-cijferige code gestuurd naar{' '}
                {email && <span className="font-medium">{email}</span>}
                {!email && <span>uw e-mailadres</span>}.
              </p>
            </div>

            {/* Code Input */}
            <div className="flex justify-center gap-1.5 sm:gap-2 mb-6">
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { inputRefs.current[index] = el }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  onPaste={index === 0 ? handlePaste : undefined}
                  className="w-10 h-12 sm:w-12 sm:h-14 text-center text-xl sm:text-2xl font-bold border-2 border-gray-300 rounded-lg focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 outline-none transition-all"
                  disabled={isVerifying}
                />
              ))}
            </div>

            {/* Verify Button */}
            <Button
              onClick={() => handleVerify()}
              className="w-full"
              size="lg"
              isLoading={isVerifying}
              disabled={code.some(d => d === '')}
            >
              Verifiëren
            </Button>

            {/* Resend */}
            <div className="mt-6 text-center">
              <p className="text-sm text-gray-600 mb-2">
                Geen code ontvangen?
              </p>
              <button
                onClick={handleResend}
                disabled={isResending || cooldown > 0}
                className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${isResending ? 'animate-spin' : ''}`} />
                {cooldown > 0 
                  ? `Opnieuw versturen (${cooldown}s)` 
                  : 'Opnieuw versturen'}
              </button>
            </div>

            {/* Help text */}
            <p className="mt-6 text-xs text-center text-gray-500">
              De code is 10 minuten geldig. Controleer ook uw spam folder.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function VerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">Laden...</p>
        </div>
      </div>
    }>
      <VerifyContent />
    </Suspense>
  )
}
