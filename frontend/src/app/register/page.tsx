'use client'

import { Suspense, useState, useRef, useEffect, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Headphones, ArrowLeft, Check, Loader2, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { api, authApi, kvkApi } from '@/lib/api'

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

const registerSchema = z.object({
  company_name: z.string().min(2, 'Bedrijfsnaam moet minimaal 2 karakters zijn'),
  company_email: z.string().email('Voer een geldig e-mailadres in'),
  first_name: z.string().min(1, 'Voornaam is verplicht'),
  last_name: z.string().min(1, 'Achternaam is verplicht'),
  password: z
    .string()
    .min(8, 'Wachtwoord moet minimaal 8 karakters zijn')
    .regex(/[A-Z]/, 'Wachtwoord moet minimaal één hoofdletter bevatten')
    .regex(/[a-z]/, 'Wachtwoord moet minimaal één kleine letter bevatten')
    .regex(/[0-9]/, 'Wachtwoord moet minimaal één cijfer bevatten'),
  confirm_password: z.string(),
  terms_accepted: z.literal(true).default(true),
  marketing_consent: z.boolean().optional().default(false),
}).refine((data) => data.password === data.confirm_password, {
  message: 'Wachtwoorden komen niet overeen',
  path: ['confirm_password'],
})

type RegisterForm = z.infer<typeof registerSchema>

const benefits = [
  '14 dagen gratis proberen',
  'Annuleren kan altijd',
  'Direct operationeel',
  'Nederlandse support',
]

function RegisterContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLoading, setIsLoading] = useState(false)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)
  const [step, setStep] = useState(1)
  
  // KVK autocomplete state
  const [kvkResults, setKvkResults] = useState<any[]>([])
  const [isKvkSearching, setIsKvkSearching] = useState(false)
  const [showKvkDropdown, setShowKvkDropdown] = useState(false)
  const [selectedKvkData, setSelectedKvkData] = useState<any>(null)
  const kvkRef = useRef<HTMLDivElement>(null)
  const kvkDebounceRef = useRef<NodeJS.Timeout | null>(null)
  
  // Get redirect URL from query params (used for checkout flow)
  const redirectUrl = searchParams.get('redirect') || '/dashboard'

  const {
    register,
    handleSubmit,
    formState: { errors },
    trigger,
    getValues,
    watch,
    setValue,
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { terms_accepted: true, marketing_consent: true },
    mode: 'onTouched',
  })

  const watchPassword = watch('password', '')
  const watchConfirmPassword = watch('confirm_password', '')
  const passwordsMismatch = watchConfirmPassword.length > 0 && watchPassword !== watchConfirmPassword

  // Close KVK dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (kvkRef.current && !kvkRef.current.contains(e.target as Node)) {
        setShowKvkDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleCompanyNameChange = useCallback((value: string) => {
    // Clear any previous timer
    if (kvkDebounceRef.current) clearTimeout(kvkDebounceRef.current)

    if (value.length < 2) {
      setKvkResults([])
      setShowKvkDropdown(false)
      setSelectedKvkData(null)
      return
    }

    // Debounce the KVK search
    kvkDebounceRef.current = setTimeout(async () => {
      setIsKvkSearching(true)
      try {
        const data = await kvkApi.search(value, 5)
        setKvkResults(data.resultaten || [])
        setShowKvkDropdown((data.resultaten || []).length > 0)
      } catch {
        setKvkResults([])
      } finally {
        setIsKvkSearching(false)
      }
    }, 400)
  }, [])

  const handleSelectKvkResult = useCallback((result: any) => {
    // Fill in company name from KVK
    setValue('company_name', result.naam, { shouldValidate: true })
    // Store the full KVK data for sending to backend
    setSelectedKvkData(result)
    setShowKvkDropdown(false)
  }, [setValue])

  const handleNextStep = async () => {
    const isValid = await trigger(['company_name', 'company_email'])
    if (isValid) {
      setStep(2)
    }
  }

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true)
    try {
      // Build company data — include KVK info if selected
      const companyPayload: any = {
        name: data.company_name,
        email: data.company_email,
      }
      if (selectedKvkData) {
        companyPayload.kvk_number = selectedKvkData.kvk_nummer
        if (selectedKvkData.adres) {
          const addr = selectedKvkData.adres
          if (addr.straatnaam) {
            companyPayload.address = addr.huisnummer
              ? `${addr.straatnaam} ${addr.huisnummer}`
              : addr.straatnaam
          }
          if (addr.postcode) companyPayload.postal_code = addr.postcode
          if (addr.plaats) companyPayload.city = addr.plaats
        }
      }

      const response = await api.post('/auth/register', {
        company_data: companyPayload,
        user_data: {
          email: data.company_email,
          password: data.password,
          first_name: data.first_name,
          last_name: data.last_name,
        },
        terms_accepted: data.terms_accepted,
        marketing_consent: data.marketing_consent ?? false,
      })
      
      // Don't store tokens - user must verify email first
      // Redirect to verify page with email as query parameter
      toast.success(response.data.message || 'Account aangemaakt! Controleer uw e-mail voor de verificatiecode.')
      router.push(`/verify?email=${encodeURIComponent(response.data.email)}`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Registratie mislukt')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleRegister = async () => {
    setIsGoogleLoading(true)
    try {
      const { auth_url, state } = await authApi.getGoogleUrl()
      // Store state in sessionStorage for verification after redirect
      sessionStorage.setItem('google_oauth_state', state)
      // Store redirect URL for after OAuth callback
      sessionStorage.setItem('auth_redirect_url', redirectUrl)
      // Redirect to Google
      window.location.href = auth_url
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Kon Google registratie niet starten')
      setIsGoogleLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left panel - Form */}
      <div className="flex-1 flex flex-col">
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
            <div className="mb-8">
              <Link href="/" className="inline-flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-600">
                  <Headphones className="h-5 w-5 text-white" />
                </div>
              </Link>
              <h1 className="mt-6 text-2xl font-display font-bold text-gray-900">
                Account aanmaken
              </h1>
              <p className="mt-2 text-gray-600">
                {step === 1 ? 'Vul uw bedrijfsgegevens in' : 'Maak uw persoonlijke account'}
              </p>
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-2 mb-8">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step >= 1 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                {step > 1 ? <Check className="h-4 w-4" /> : '1'}
              </div>
              <div className={`flex-1 h-1 ${step > 1 ? 'bg-primary-600' : 'bg-gray-200'}`} />
              <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step >= 2 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                2
              </div>
            </div>

            {/* Form */}
            <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-6 sm:p-8">
              {step === 1 && (
                <>
                  {/* Google Register Button */}
                  <button
                    type="button"
                    onClick={handleGoogleRegister}
                    disabled={isGoogleLoading}
                    className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-gray-300 rounded-lg bg-white text-gray-700 font-medium hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isGoogleLoading ? (
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600" />
                    ) : (
                      <GoogleIcon className="h-5 w-5" />
                    )}
                    Registreren met Google
                  </button>

                  {/* Divider */}
                  <div className="relative my-6">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-gray-200" />
                    </div>
                    <div className="relative flex justify-center text-sm">
                      <span className="bg-white px-4 text-gray-500">of</span>
                    </div>
                  </div>
                </>
              )}

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                {step === 1 ? (
                  <>
                    <div className="relative" ref={kvkRef}>
                      <Input
                        label="Bedrijfsnaam"
                        placeholder="Zoek uw bedrijf..."
                        autoComplete="off"
                        error={errors.company_name?.message}
                        {...register('company_name', {
                          onChange: (e) => handleCompanyNameChange(e.target.value),
                        })}
                      />
                      {isKvkSearching && (
                        <div className="absolute right-3 top-9 text-gray-400">
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </div>
                      )}
                      {selectedKvkData && (
                        <p className="mt-1 text-xs text-green-600 flex items-center gap-1">
                          <Building2 className="h-3 w-3" />
                          KvK {selectedKvkData.kvk_nummer}
                          {selectedKvkData.adres?.plaats && ` · ${selectedKvkData.adres.plaats}`}
                        </p>
                      )}
                      {showKvkDropdown && kvkResults.length > 0 && (
                        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white rounded-lg border border-gray-200 shadow-lg overflow-hidden">
                          {kvkResults.map((result: any, index: number) => (
                            <button
                              key={`${result.kvk_nummer}-${index}`}
                              type="button"
                              onClick={() => handleSelectKvkResult(result)}
                              className="w-full flex items-start gap-3 px-4 py-3 hover:bg-gray-50 text-left transition-colors border-b border-gray-50 last:border-0"
                            >
                              <Building2 className="h-5 w-5 text-gray-400 mt-0.5 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">{result.naam}</p>
                                <p className="text-xs text-gray-500 mt-0.5">
                                  KvK {result.kvk_nummer}
                                  {result.adres?.plaats && ` · ${result.adres.plaats}`}
                                  {result.adres?.straatnaam && `, ${result.adres.straatnaam}`}
                                  {result.adres?.huisnummer && ` ${result.adres.huisnummer}`}
                                </p>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <Input
                      label="E-mailadres"
                      type="email"
                      placeholder="info@uwbedrijf.nl"
                      error={errors.company_email?.message}
                      {...register('company_email')}
                    />
                    <Button
                      type="button"
                      className="w-full"
                      size="lg"
                      onClick={handleNextStep}
                    >
                      Volgende stap
                    </Button>
                  </>
                ) : (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <Input
                        label="Voornaam"
                        placeholder="Jan"
                        autoComplete="off"
                        error={errors.first_name?.message}
                        {...register('first_name')}
                      />
                      <Input
                        label="Achternaam"
                        placeholder="Jansen"
                        autoComplete="off"
                        error={errors.last_name?.message}
                        {...register('last_name')}
                      />
                    </div>
                    <input type="password" name="fake-password" autoComplete="off" className="hidden" tabIndex={-1} aria-hidden="true" />
                    <Input
                      label="Wachtwoord"
                      type="password"
                      placeholder="••••••••"
                      autoComplete="off"
                      error={errors.password?.message}
                      helperText="Minimaal 8 karakters met hoofdletter, kleine letter en cijfer"
                      {...register('password')}
                    />
                    <Input
                      label="Wachtwoord bevestigen"
                      type="password"
                      placeholder="••••••••"
                      autoComplete="off"
                      error={passwordsMismatch ? 'Wachtwoorden komen niet overeen' : errors.confirm_password?.message}
                      {...register('confirm_password')}
                    />
                    <label className="flex items-center gap-3 cursor-pointer group">
                      <div className="relative flex items-center justify-center">
                        <input
                          type="checkbox"
                          className="peer sr-only"
                          {...register('marketing_consent')}
                        />
                        <div className="h-5 w-5 rounded-md border-2 border-gray-300 bg-white transition-all peer-checked:border-primary-600 peer-checked:bg-primary-600 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2 group-hover:border-gray-400 peer-checked:group-hover:border-primary-700" />
                        <Check className="absolute h-3.5 w-3.5 text-white opacity-0 transition-opacity peer-checked:opacity-100 pointer-events-none" />
                      </div>
                      <span className="text-sm text-gray-600 select-none">
                        Ja, ik ontvang graag tips en aanbiedingen per e-mail.
                      </span>
                    </label>
                    <div className="flex gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="lg"
                        className="flex-1 whitespace-nowrap"
                        onClick={() => setStep(1)}
                      >
                        Terug
                      </Button>
                      <Button
                        type="submit"
                        size="lg"
                        className="flex-1 whitespace-nowrap"
                        isLoading={isLoading}
                      >
                        Account aanmaken
                      </Button>
                    </div>
                    <p className="text-xs text-center text-gray-400 leading-relaxed">
                      Door een account aan te maken ga je akkoord met onze{' '}
                      <Link href="/voorwaarden" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-primary-600 underline">
                        algemene voorwaarden
                      </Link>
                      {' '}en ons{' '}
                      <Link href="/avg" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-primary-600 underline">
                        privacybeleid
                      </Link>.
                    </p>
                  </>
                )}
              </form>
            </div>

            {/* Login link */}
            <p className="mt-6 mb-8 text-center text-sm text-gray-600">
              Al een account?{' '}
              <Link href="/login" className="text-primary-600 hover:text-primary-700 font-medium">
                Log in
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* Right panel - Benefits */}
      <div className="hidden lg:flex lg:w-[480px] bg-primary-600 p-12 flex-col justify-center">
        <h2 className="text-2xl font-display font-bold text-white">
          Start vandaag nog
        </h2>
        <p className="mt-4 text-primary-100">
          Ontdek hoe klantenservice.ai uw telefonische klantenservice transformeert.
        </p>
        <ul className="mt-8 space-y-4">
          {benefits.map((benefit) => (
            <li key={benefit} className="flex items-center gap-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-500">
                <Check className="h-4 w-4 text-white" />
              </div>
              <span className="text-white">{benefit}</span>
            </li>
          ))}
        </ul>
        <div className="mt-12 p-6 rounded-xl bg-primary-500/50">
          <p className="text-primary-100 text-sm">
            "Sinds we klantenservice.ai gebruiken, missen we geen enkel telefoontje meer. 
            De AI beantwoordt vragen perfect en plant zelf afspraken in."
          </p>
          <div className="mt-4 flex items-center gap-3">
            <img src="/persona/mariadevries.png" alt="Maria de Vries" className="h-10 w-10 rounded-full object-cover" />
            <div>
              <p className="text-sm font-medium text-white">Maria de Vries</p>
              <p className="text-xs text-primary-200">Eigenaar, De Vries Consultancy</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function RegisterPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">Laden...</p>
        </div>
      </div>
    }>
      <RegisterContent />
    </Suspense>
  )
}
