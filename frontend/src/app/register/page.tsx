'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import toast from 'react-hot-toast'
import { Headphones, ArrowLeft, Check } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { api } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const registerSchema = z.object({
  company_name: z.string().min(2, 'Bedrijfsnaam moet minimaal 2 karakters zijn'),
  company_email: z.string().email('Voer een geldig e-mailadres in'),
  first_name: z.string().min(1, 'Voornaam is verplicht'),
  last_name: z.string().min(1, 'Achternaam is verplicht'),
  email: z.string().email('Voer een geldig e-mailadres in'),
  password: z
    .string()
    .min(8, 'Wachtwoord moet minimaal 8 karakters zijn')
    .regex(/[A-Z]/, 'Wachtwoord moet minimaal één hoofdletter bevatten')
    .regex(/[a-z]/, 'Wachtwoord moet minimaal één kleine letter bevatten')
    .regex(/[0-9]/, 'Wachtwoord moet minimaal één cijfer bevatten'),
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
  message: 'Wachtwoorden komen niet overeen',
  path: ['confirm_password'],
})

type RegisterForm = z.infer<typeof registerSchema>

const benefits = [
  '14 dagen gratis proberen',
  'Probeer het gratis',
  'Direct operationeel',
  'Nederlandse support',
]

export default function RegisterPage() {
  const router = useRouter()
  const { setAuth } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [step, setStep] = useState(1)

  const {
    register,
    handleSubmit,
    formState: { errors },
    trigger,
    getValues,
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  })

  const handleNextStep = async () => {
    const isValid = await trigger(['company_name', 'company_email'])
    if (isValid) {
      setStep(2)
    }
  }

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true)
    try {
      const response = await api.post('/auth/register', {
        name: data.company_name,
        email: data.company_email,
      }, {
        params: {
          email: data.email,
          password: data.password,
          first_name: data.first_name,
          last_name: data.last_name,
        },
      })
      
      // Store tokens
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)
      
      toast.success('Account aangemaakt! Welkom bij klantenservice.ai')
      router.push('/dashboard')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Registratie mislukt')
    } finally {
      setIsLoading(false)
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
            <div className="bg-white rounded-xl shadow-soft border border-gray-200 p-8">
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                {step === 1 ? (
                  <>
                    <Input
                      label="Bedrijfsnaam"
                      placeholder="Uw bedrijf B.V."
                      error={errors.company_name?.message}
                      {...register('company_name')}
                    />
                    <Input
                      label="Bedrijfs e-mailadres"
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
                    <div className="grid grid-cols-2 gap-4">
                      <Input
                        label="Voornaam"
                        placeholder="Jan"
                        error={errors.first_name?.message}
                        {...register('first_name')}
                      />
                      <Input
                        label="Achternaam"
                        placeholder="Jansen"
                        error={errors.last_name?.message}
                        {...register('last_name')}
                      />
                    </div>
                    <Input
                      label="E-mailadres"
                      type="email"
                      placeholder="jan@uwbedrijf.nl"
                      error={errors.email?.message}
                      {...register('email')}
                    />
                    <Input
                      label="Wachtwoord"
                      type="password"
                      placeholder="••••••••"
                      error={errors.password?.message}
                      helperText="Minimaal 8 karakters met hoofdletter, kleine letter en cijfer"
                      {...register('password')}
                    />
                    <Input
                      label="Wachtwoord bevestigen"
                      type="password"
                      placeholder="••••••••"
                      error={errors.confirm_password?.message}
                      {...register('confirm_password')}
                    />
                    <div className="flex gap-4">
                      <Button
                        type="button"
                        variant="outline"
                        className="flex-1"
                        size="lg"
                        onClick={() => setStep(1)}
                      >
                        Terug
                      </Button>
                      <Button
                        type="submit"
                        className="flex-1"
                        size="lg"
                        isLoading={isLoading}
                      >
                        Account aanmaken
                      </Button>
                    </div>
                  </>
                )}
              </form>
            </div>

            {/* Login link */}
            <p className="mt-6 text-center text-sm text-gray-600">
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
            <div className="h-10 w-10 rounded-full bg-primary-400" />
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
