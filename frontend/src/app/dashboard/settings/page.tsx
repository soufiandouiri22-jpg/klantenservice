'use client'

import { useState, useEffect, useRef, useCallback, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Building2, Shield, CreditCard, Users, User, Key, Trash2, Mail, Clock, Check, RefreshCw, Pencil, Loader2, CheckCircle, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { Badge } from '@/components/ui/Badge'
import { PageLoader } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { Select } from '@/components/ui/Select'
import { companyApi, usersApi, authApi, paymentsApi, kvkApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const tabs = [
  { id: 'profile', label: 'Persoonsgegevens', icon: User },
  { id: 'company', label: 'Bedrijf', icon: Building2 },
  { id: 'privacy', label: 'Privacy', icon: Shield },
  { id: 'subscription', label: 'Abonnement', icon: CreditCard },
  { id: 'users', label: 'Gebruikers', icon: Users },
  { id: 'security', label: 'Beveiliging', icon: Key },
]

function SettingsContent() {
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const { company, user } = useAuthStore()
  
  // Get initial tab from URL params or default to 'profile' (Persoonsgegevens)
  const initialTab = searchParams.get('tab') || 'profile'
  const [activeTab, setActiveTab] = useState(initialTab)
  
  // Update tab when URL params change
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && tabs.some(t => t.id === tabParam)) {
      setActiveTab(tabParam)
    }
  }, [searchParams])
  // Email change modal state
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false)
  const [emailStep, setEmailStep] = useState<1 | 2>(1)
  const [newEmail, setNewEmail] = useState('')
  const [emailCode, setEmailCode] = useState(['', '', '', '', '', ''])
  const [emailCooldown, setEmailCooldown] = useState(0)
  const emailCodeRefs = useRef<(HTMLInputElement | null)[]>([])

  // KVK autocomplete state (settings company tab)
  const [kvkResults, setKvkResults] = useState<any[]>([])
  const [isKvkSearching, setIsKvkSearching] = useState(false)
  const [showKvkDropdown, setShowKvkDropdown] = useState(false)
  const kvkSettingsRef = useRef<HTMLDivElement>(null)
  const kvkDebounceRef = useRef<NodeJS.Timeout | null>(null)
  const companyNameRef = useRef<HTMLInputElement>(null)

  // BTW validation state
  const [btwStatus, setBtwStatus] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle')

  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false)
  const [newUserData, setNewUserData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'viewer' as 'owner' | 'admin' | 'user' | 'viewer',
  })

  const { data: currentUser, isLoading: profileLoading } = useQuery({
    queryKey: ['auth-me'],
    queryFn: authApi.getMe,
  })

  const { data: companyData, isLoading: companyLoading } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
  })

  const { data: privacySettings, isLoading: privacyLoading } = useQuery({
    queryKey: ['privacy-settings'],
    queryFn: companyApi.getPrivacySettings,
  })

  const { data: subscription, isLoading: subscriptionLoading } = useQuery({
    queryKey: ['subscription'],
    queryFn: companyApi.getSubscription,
  })

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })

  const { setCompany, setUser } = useAuthStore()
  
  const updateProfileMutation = useMutation({
    mutationFn: authApi.updateMe,
    onSuccess: (updatedUser) => {
      queryClient.invalidateQueries({ queryKey: ['auth-me'] })
      if (updatedUser) {
        setUser({
          id: updatedUser.id,
          email: updatedUser.email,
          first_name: updatedUser.first_name,
          last_name: updatedUser.last_name,
          role: updatedUser.role,
          company_id: updatedUser.company_id,
          oauth_provider: updatedUser.oauth_provider,
          is_verified: updatedUser.is_verified,
          is_superadmin: updatedUser.is_superadmin,
        })
      }
      toast.success('Persoonsgegevens bijgewerkt')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon gegevens niet opslaan')
    },
  })

  const updateCompanyMutation = useMutation({
    mutationFn: companyApi.update,
    onSuccess: (updatedCompany) => {
      queryClient.invalidateQueries({ queryKey: ['company'] })
      // Update the auth store so sidebar reflects changes
      if (updatedCompany) {
        setCompany({
          id: updatedCompany.id,
          name: updatedCompany.name,
          slug: updatedCompany.slug,
          subscription_plan: updatedCompany.subscription_plan,
          max_ai_workers: updatedCompany.max_ai_workers,
        })
      }
      toast.success('Bedrijfsgegevens bijgewerkt')
    },
  })

  const updatePrivacyMutation = useMutation({
    mutationFn: companyApi.updatePrivacySettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['privacy-settings'] })
      toast.success('Privacy-instellingen bijgewerkt')
    },
  })

  const inviteUserMutation = useMutation({
    mutationFn: usersApi.invite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('Uitnodiging verstuurd! De gebruiker ontvangt een e-mail.')
      setIsAddUserModalOpen(false)
      setNewUserData({
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: 'viewer',
      })
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Er ging iets mis bij het versturen van de uitnodiging'
      toast.error(message)
    },
  })

  const resendInviteMutation = useMutation({
    mutationFn: usersApi.resendInvite,
    onSuccess: () => {
      toast.success('Uitnodiging opnieuw verstuurd!')
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Er ging iets mis bij het opnieuw versturen'
      toast.error(message)
    },
  })

  const deleteUserMutation = useMutation({
    mutationFn: usersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('Gebruiker verwijderd')
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Er ging iets mis bij het verwijderen van de gebruiker'
      toast.error(message)
    },
  })

  const checkoutMutation = useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval?: 'monthly' | 'yearly' }) => 
      paymentsApi.createCheckoutSession(plan, interval),
    onSuccess: (data) => {
      // Redirect to Stripe Checkout
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Er ging iets mis bij het starten van de betaling'
      toast.error(message)
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => paymentsApi.createPortalSession(),
    onSuccess: (data) => {
      // Redirect to Stripe Customer Portal
      if (data.portal_url) {
        window.location.href = data.portal_url
      }
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Er ging iets mis bij het openen van het klantportaal'
      toast.error(message)
    },
  })

  // Email change cooldown timer
  useEffect(() => {
    if (emailCooldown > 0) {
      const timer = setTimeout(() => setEmailCooldown(emailCooldown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [emailCooldown])

  const requestEmailChangeMutation = useMutation({
    mutationFn: (email: string) => authApi.changeEmailRequest(email),
    onSuccess: () => {
      toast.success('Verificatiecode verzonden naar uw huidige e-mailadres')
      setEmailStep(2)
      setEmailCooldown(60)
      // Focus first code input after step transition
      setTimeout(() => emailCodeRefs.current[0]?.focus(), 100)
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail
      if (detail?.includes('Wacht nog')) {
        const match = detail.match(/(\d+) seconden/)
        if (match) setEmailCooldown(parseInt(match[1]))
      }
      toast.error(detail || 'Kon verificatiecode niet versturen')
    },
  })

  const verifyEmailChangeMutation = useMutation({
    mutationFn: (code: string) => authApi.changeEmailVerify(code),
    onSuccess: (updatedUser) => {
      queryClient.invalidateQueries({ queryKey: ['auth-me'] })
      if (updatedUser) {
        setUser({
          id: updatedUser.id,
          email: updatedUser.email,
          first_name: updatedUser.first_name,
          last_name: updatedUser.last_name,
          role: updatedUser.role,
          company_id: updatedUser.company_id,
          oauth_provider: updatedUser.oauth_provider,
          is_verified: updatedUser.is_verified,
          is_superadmin: updatedUser.is_superadmin,
        })
      }
      toast.success('E-mailadres succesvol gewijzigd')
      closeEmailModal()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Verificatie mislukt')
      setEmailCode(['', '', '', '', '', ''])
      emailCodeRefs.current[0]?.focus()
    },
  })

  const closeEmailModal = () => {
    setIsEmailModalOpen(false)
    setEmailStep(1)
    setNewEmail('')
    setEmailCode(['', '', '', '', '', ''])
    setEmailCooldown(0)
  }

  const handleEmailCodeChange = (index: number, value: string) => {
    if (value && !/^\d$/.test(value)) return
    const newCode = [...emailCode]
    newCode[index] = value
    setEmailCode(newCode)
    if (value && index < 5) {
      emailCodeRefs.current[index + 1]?.focus()
    }
    if (value && index === 5 && newCode.every(d => d !== '')) {
      verifyEmailChangeMutation.mutate(newCode.join(''))
    }
  }

  const handleEmailCodeKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !emailCode[index] && index > 0) {
      emailCodeRefs.current[index - 1]?.focus()
    }
  }

  const handleEmailCodePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (pastedData.length === 6) {
      setEmailCode(pastedData.split(''))
      emailCodeRefs.current[5]?.focus()
      verifyEmailChangeMutation.mutate(pastedData)
    }
  }

  const handleResendEmailCode = () => {
    if (emailCooldown > 0) return
    requestEmailChangeMutation.mutate(newEmail)
  }

  // Close KVK dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (kvkSettingsRef.current && !kvkSettingsRef.current.contains(e.target as Node)) {
        setShowKvkDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleKvkSearch = useCallback((value: string) => {
    if (kvkDebounceRef.current) clearTimeout(kvkDebounceRef.current)
    if (value.length < 2) {
      setKvkResults([])
      setShowKvkDropdown(false)
      return
    }
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

  const handleSelectKvkCompany = useCallback((result: any) => {
    // Build update payload from KVK data
    const update: any = { name: result.naam, kvk_number: result.kvk_nummer }
    if (result.adres) {
      if (result.adres.straatnaam) {
        update.address = result.adres.huisnummer
          ? `${result.adres.straatnaam} ${result.adres.huisnummer}`
          : result.adres.straatnaam
      }
      if (result.adres.postcode) update.postal_code = result.adres.postcode
      if (result.adres.plaats) update.city = result.adres.plaats
    }
    updateCompanyMutation.mutate(update)
    setShowKvkDropdown(false)
    // Update the input visually
    if (companyNameRef.current) companyNameRef.current.value = result.naam
    toast.success(`Bedrijfsgegevens bijgewerkt vanuit KVK (${result.kvk_nummer})`)
  }, [updateCompanyMutation])

  const handleBtwValidation = useCallback(async (btwNummer: string) => {
    if (!btwNummer || btwNummer.length < 4) {
      setBtwStatus('idle')
      return
    }
    setBtwStatus('checking')
    try {
      const result = await kvkApi.validateBtw(btwNummer)
      setBtwStatus(result.geldig ? 'valid' : 'invalid')
      if (!result.geldig) {
        toast.error(result.melding || 'BTW-nummer is ongeldig')
      }
    } catch {
      setBtwStatus('idle')
    }
  }, [])

  const handleUpgrade = (plan: string, interval: 'monthly' | 'yearly' = 'monthly') => {
    checkoutMutation.mutate({ plan, interval })
  }

  const handleManageSubscription = () => {
    portalMutation.mutate()
  }

  const handleInviteUser = () => {
    inviteUserMutation.mutate(newUserData)
  }

  const isLoading = profileLoading || companyLoading || privacyLoading || subscriptionLoading || usersLoading

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <Header title="Instellingen" description="Beheer uw account en bedrijfsinstellingen." />

      <div className="p-6">
        <div className="flex gap-6">
          {/* Tabs */}
          <div className="w-64 flex-shrink-0">
            <nav className="space-y-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <tab.icon className={`h-5 w-5 ${activeTab === tab.id ? 'text-primary-600' : 'text-gray-400'}`} />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Content */}
          <div className="flex-1 space-y-6">
            {activeTab === 'profile' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Persoonsgegevens</CardTitle>
                    <CardDescription>
                      Uw naam en e-mail. Bij inloggen met Google worden deze automatisch ingevuld.
                    </CardDescription>
                  </CardHeader>
                  <CardBody className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <Input
                        label="Voornaam"
                        defaultValue={currentUser?.first_name}
                        onBlur={(e) => {
                          const v = e.target.value.trim()
                          if (v !== currentUser?.first_name) {
                            updateProfileMutation.mutate({ first_name: v })
                          }
                        }}
                      />
                      <Input
                        label="Achternaam"
                        defaultValue={currentUser?.last_name}
                        onBlur={(e) => {
                          const v = e.target.value.trim()
                          if (v !== currentUser?.last_name) {
                            updateProfileMutation.mutate({ last_name: v })
                          }
                        }}
                      />
                    </div>
                    <div>
                      <label className="label">E-mailadres</label>
                      <div className="flex gap-3 items-center">
                        <div className="flex-1 input bg-gray-50 text-gray-700 cursor-not-allowed">
                          {currentUser?.email}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsEmailModalOpen(true)}
                          className="flex-shrink-0"
                        >
                          <Pencil className="h-4 w-4 mr-1.5" />
                          Wijzigen
                        </Button>
                      </div>
                    </div>
                    <Input
                      label="Telefoonnummer"
                      defaultValue={currentUser?.phone ?? ''}
                      onBlur={(e) => {
                        const v = e.target.value.trim() || undefined
                        if (v !== (currentUser?.phone ?? '')) {
                          updateProfileMutation.mutate({ phone: v })
                        }
                      }}
                    />
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {activeTab === 'company' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Bedrijfsgegevens</CardTitle>
                    <CardDescription>Algemene informatie over uw bedrijf.</CardDescription>
                  </CardHeader>
                  <CardBody className="space-y-4">
                    <div className="relative" ref={kvkSettingsRef}>
                      <Input
                        ref={companyNameRef}
                        label="Bedrijfsnaam"
                        defaultValue={companyData?.name}
                        autoComplete="off"
                        onChange={(e) => handleKvkSearch(e.target.value)}
                        onBlur={(e) => {
                          const v = e.target.value.trim()
                          if (v !== companyData?.name) {
                            updateCompanyMutation.mutate({ name: v })
                          }
                        }}
                      />
                      {isKvkSearching && (
                        <div className="absolute right-3 top-9 text-gray-400">
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </div>
                      )}
                      {showKvkDropdown && kvkResults.length > 0 && (
                        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white rounded-lg border border-gray-200 shadow-lg overflow-hidden">
                          <p className="px-4 py-2 text-xs text-gray-500 bg-gray-50 border-b border-gray-100">
                            Selecteer om gegevens automatisch in te vullen
                          </p>
                          {kvkResults.map((result: any, index: number) => (
                            <button
                              key={`${result.kvk_nummer}-${index}`}
                              type="button"
                              onMouseDown={(e) => {
                                e.preventDefault() // Prevent input blur
                                handleSelectKvkCompany(result)
                              }}
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
                      label="E-mailadres voor facturatie"
                      type="email"
                      defaultValue={companyData?.email}
                      helperText="Facturen en betalingsherinneringen worden naar dit adres gestuurd."
                      onBlur={(e) => {
                        if (e.target.value !== companyData?.email) {
                          updateCompanyMutation.mutate({ email: e.target.value })
                        }
                      }}
                    />
                    <Input
                      label="Telefoonnummer"
                      defaultValue={companyData?.phone}
                      onBlur={(e) => {
                        if (e.target.value !== companyData?.phone) {
                          updateCompanyMutation.mutate({ phone: e.target.value })
                        }
                      }}
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <Input
                        label="KvK-nummer"
                        defaultValue={companyData?.kvk_number}
                        onBlur={(e) => {
                          if (e.target.value !== companyData?.kvk_number) {
                            updateCompanyMutation.mutate({ kvk_number: e.target.value })
                          }
                        }}
                      />
                      <div className="relative">
                        <Input
                          label="BTW-nummer"
                          defaultValue={companyData?.btw_number}
                          placeholder="NL123456789B01"
                          onBlur={(e) => {
                            const v = e.target.value.trim()
                            if (v !== companyData?.btw_number) {
                              updateCompanyMutation.mutate({ btw_number: v })
                              if (v) handleBtwValidation(v)
                              else setBtwStatus('idle')
                            }
                          }}
                        />
                        {btwStatus === 'checking' && (
                          <Loader2 className="absolute right-3 top-9 h-4 w-4 animate-spin text-gray-400" />
                        )}
                        {btwStatus === 'valid' && (
                          <div className="mt-1 flex items-center gap-1 text-xs text-green-600">
                            <CheckCircle className="h-3.5 w-3.5" />
                            BTW-nummer is geldig
                          </div>
                        )}
                        {btwStatus === 'invalid' && (
                          <div className="mt-1 flex items-center gap-1 text-xs text-red-600">
                            <XCircle className="h-3.5 w-3.5" />
                            BTW-nummer is ongeldig
                          </div>
                        )}
                      </div>
                    </div>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Adresgegevens</CardTitle>
                  </CardHeader>
                  <CardBody className="space-y-4">
                    <Input
                      label="Adres"
                      defaultValue={companyData?.address}
                      onBlur={(e) => {
                        if (e.target.value !== companyData?.address) {
                          updateCompanyMutation.mutate({ address: e.target.value })
                        }
                      }}
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <Input
                        label="Postcode"
                        defaultValue={companyData?.postal_code}
                        onBlur={(e) => {
                          if (e.target.value !== companyData?.postal_code) {
                            updateCompanyMutation.mutate({ postal_code: e.target.value })
                          }
                        }}
                      />
                      <Input
                        label="Plaats"
                        defaultValue={companyData?.city}
                        onBlur={(e) => {
                          if (e.target.value !== companyData?.city) {
                            updateCompanyMutation.mutate({ city: e.target.value })
                          }
                        }}
                      />
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {activeTab === 'privacy' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Privacy & Compliance</CardTitle>
                    <CardDescription>Instellingen voor AVG/GDPR compliance.</CardDescription>
                  </CardHeader>
                  <CardBody className="space-y-6">
                    <div>
                      <label className="label">Data retentie (dagen)</label>
                      <Input
                        type="number"
                        defaultValue={privacySettings?.data_retention_days}
                        min={30}
                        max={365}
                      />
                      <p className="mt-1.5 text-sm text-gray-500">
                        Gesprekslogs worden na dit aantal dagen automatisch verwijderd.
                      </p>
                    </div>

                    <Toggle
                      enabled={privacySettings?.call_recording_enabled}
                      onChange={(enabled) => updatePrivacyMutation.mutate({ call_recording_enabled: enabled })}
                      label="Gesprekken opnemen"
                      description="Gesprekken worden opgenomen voor kwaliteitsdoeleinden."
                    />

                    <Toggle
                      enabled={privacySettings?.call_recording_consent_required}
                      onChange={(enabled) => updatePrivacyMutation.mutate({ call_recording_consent_required: enabled })}
                      label="Toestemming voor opname vragen"
                      description="Vraag bellers expliciet om toestemming voor het opnemen van het gesprek."
                    />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Disclosure bericht</CardTitle>
                    <CardDescription>
                      Dit bericht wordt aan het begin van elk gesprek afgespeeld.
                    </CardDescription>
                  </CardHeader>
                  <CardBody>
                    <textarea
                      className="input min-h-[100px] resize-none"
                      defaultValue={privacySettings?.disclosure_message}
                      placeholder="U spreekt met {ai_worker_name}, de digitale assistent van {company_name}"
                      onBlur={(e) => {
                        const v = e.target.value.trim()
                        if (v !== privacySettings?.disclosure_message) {
                          updateCompanyMutation.mutate({ disclosure_message: v })
                        }
                      }}
                    />
                    <p className="mt-2 text-sm text-gray-500">
                      Gebruik <code className="px-1 py-0.5 bg-gray-100 rounded">{'{ai_worker_name}'}</code> voor de naam van de AI-medewerker en <code className="px-1 py-0.5 bg-gray-100 rounded">{'{company_name}'}</code> voor de bedrijfsnaam.
                    </p>
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {activeTab === 'subscription' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                {/* Current Status */}
                <Card>
                  <CardHeader>
                    <CardTitle>Huidig abonnement</CardTitle>
                  </CardHeader>
                  <CardBody>
                    {subscription?.status === 'active' || subscription?.status === 'trialing' ? (
                      <div className="flex items-center justify-between p-4 rounded-lg bg-primary-50 border border-primary-100">
                        <div>
                          <h3 className="text-lg font-semibold text-primary-900 capitalize">
                            {subscription?.plan} Plan
                          </h3>
                          <p className="text-sm text-primary-700">
                            {subscription?.max_ai_workers} AI-medewerker(s)
                          </p>
                        </div>
                        <Badge variant={subscription?.status === 'trialing' ? 'warning' : 'success'}>
                          {subscription?.status === 'trialing' ? 'Proefperiode' : 'Actief'}
                        </Badge>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between p-4 rounded-lg bg-amber-50 border border-amber-200">
                        <div>
                          <h3 className="text-lg font-semibold text-amber-900">
                            Geen actief abonnement
                          </h3>
                          <p className="text-sm text-amber-700">
                            Kies hieronder een abonnement om te starten met uw 14-dagen gratis proefperiode.
                          </p>
                        </div>
                        <Badge variant="warning">Niet actief</Badge>
                      </div>
                    )}
                  </CardBody>
                </Card>

                {/* Plans */}
                <Card>
                  <CardHeader>
                    <CardTitle>Kies uw abonnement</CardTitle>
                    <CardDescription>
                      Start met 14 dagen gratis proefperiode. Geen creditcard vereist om te beginnen.
                    </CardDescription>
                  </CardHeader>
                  <CardBody>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* Starter Plan */}
                      <div className={`relative p-6 rounded-xl border-2 transition-all ${
                        (subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'starter'
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-primary-300'
                      }`}>
                        <h4 className="text-xl font-bold text-gray-900">Starter</h4>
                        <p className="text-sm text-gray-500 mt-1">Perfect voor kleine ondernemers</p>
                        <div className="mt-4">
                          <span className="text-3xl font-bold text-gray-900">€149</span>
                          <span className="text-gray-500">/maand</span>
                        </div>
                        <ul className="mt-4 space-y-2">
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            1 AI-medewerker
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            500 belminuten/maand
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Agenda integratie
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Website kennis
                          </li>
                        </ul>
                        {(subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'starter' ? (
                          <div className="mt-6 py-2 text-center text-sm font-medium text-primary-600">
                            Uw huidige plan
                          </div>
                        ) : (
                          <Button
                            className="mt-6 w-full"
                            variant={subscription?.status !== 'active' && subscription?.status !== 'trialing' ? 'primary' : 'outline'}
                            onClick={() => handleUpgrade('starter')}
                            disabled={checkoutMutation.isPending}
                          >
                            {checkoutMutation.isPending ? 'Laden...' : 
                              subscription?.status !== 'active' && subscription?.status !== 'trialing' 
                                ? 'Start gratis proefperiode' 
                                : subscription?.plan === 'business' || subscription?.plan === 'enterprise'
                                  ? 'Downgraden'
                                  : 'Kiezen'}
                          </Button>
                        )}
                      </div>

                      {/* Business Plan */}
                      <div className={`relative p-6 rounded-xl border-2 transition-all ${
                        (subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'business'
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-primary-500 shadow-lg'
                      }`}>
                        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                          <span className="bg-primary-500 text-white text-xs font-semibold px-3 py-1 rounded-full">
                            Populair
                          </span>
                        </div>
                        <h4 className="text-xl font-bold text-gray-900">Business</h4>
                        <p className="text-sm text-gray-500 mt-1">Ideaal voor groeiende bedrijven</p>
                        <div className="mt-4">
                          <span className="text-3xl font-bold text-gray-900">€299</span>
                          <span className="text-gray-500">/maand</span>
                        </div>
                        <ul className="mt-4 space-y-2">
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            5 AI-medewerkers
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            2000 belminuten/maand
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Prioriteit support
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            API toegang
                          </li>
                        </ul>
                        {(subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'business' ? (
                          <div className="mt-6 py-2 text-center text-sm font-medium text-primary-600">
                            Uw huidige plan
                          </div>
                        ) : (
                          <Button
                            className="mt-6 w-full"
                            onClick={() => handleUpgrade('business')}
                            disabled={checkoutMutation.isPending}
                          >
                            {checkoutMutation.isPending ? 'Laden...' : 
                              subscription?.status !== 'active' && subscription?.status !== 'trialing' 
                                ? 'Start gratis proefperiode' 
                                : subscription?.plan === 'starter'
                                  ? 'Upgraden'
                                  : subscription?.plan === 'enterprise'
                                    ? 'Downgraden'
                                    : 'Kiezen'}
                          </Button>
                        )}
                      </div>

                      {/* Enterprise Plan */}
                      <div className={`relative p-6 rounded-xl border-2 transition-all ${
                        (subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'enterprise'
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-primary-300'
                      }`}>
                        <h4 className="text-xl font-bold text-gray-900">Enterprise</h4>
                        <p className="text-sm text-gray-500 mt-1">Voor grote organisaties</p>
                        <div className="mt-4">
                          <span className="text-3xl font-bold text-gray-900">Op aanvraag</span>
                        </div>
                        <ul className="mt-4 space-y-2">
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            7+ AI-medewerkers
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Onbeperkte belminuten
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Dedicated support
                          </li>
                          <li className="flex items-center text-sm text-gray-600">
                            <Check className="h-4 w-4 text-green-500 mr-2" />
                            Custom integraties
                          </li>
                        </ul>
                        {(subscription?.status === 'active' || subscription?.status === 'trialing') && subscription?.plan === 'enterprise' ? (
                          <div className="mt-6 py-2 text-center text-sm font-medium text-primary-600">
                            Uw huidige plan
                          </div>
                        ) : (
                          <Button
                            className="mt-6 w-full"
                            variant="outline"
                            onClick={() => window.location.href = '/contact'}
                          >
                            Aanvragen
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Manage subscription button for existing Stripe customers */}
                    {subscription?.has_stripe && (subscription?.status === 'active' || subscription?.status === 'trialing') && (
                      <div className="mt-8 pt-6 border-t border-gray-200">
                        <Button
                          variant="outline"
                          onClick={handleManageSubscription}
                          disabled={portalMutation.isPending}
                        >
                          {portalMutation.isPending ? 'Laden...' : 'Beheer abonnement & facturen'}
                        </Button>
                        <p className="mt-2 text-sm text-gray-500">
                          Wijzig je betaalmethode, bekijk facturen of annuleer je abonnement.
                        </p>
                      </div>
                    )}
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {activeTab === 'users' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader className="flex items-center justify-between">
                    <div>
                      <CardTitle>Gebruikers</CardTitle>
                      <CardDescription>Beheer wie toegang heeft tot het dashboard.</CardDescription>
                    </div>
                    <Button size="sm" onClick={() => setIsAddUserModalOpen(true)}>Gebruiker toevoegen</Button>
                  </CardHeader>
                  <CardBody className="p-0">
                    <div className="divide-y divide-gray-100">
                      {users?.map((u: any) => (
                        <div key={u.id} className="flex items-center justify-between p-4">
                          <div className="flex items-center gap-4">
                            <div className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-medium ${
                              u.is_active 
                                ? 'bg-primary-100 text-primary-700' 
                                : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              {u.is_active ? (
                                <>{u.first_name?.[0] || ''}{u.last_name?.[0] || ''}</>
                              ) : (
                                <Clock className="h-5 w-5" />
                              )}
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">
                                {u.first_name} {u.last_name}
                                {u.id === user?.id && (
                                  <span className="ml-2 text-xs text-gray-400">(jij)</span>
                                )}
                                {!u.is_active && (
                                  <span className="ml-2 text-xs text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded-full">Uitgenodigd</span>
                                )}
                              </p>
                              <p className="text-sm text-gray-500">{u.email}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge
                              variant={
                                u.role === 'owner' ? 'primary' :
                                u.role === 'admin' ? 'warning' : 'gray'
                              }
                            >
                              {u.role === 'owner' ? 'Eigenaar' : 
                               u.role === 'admin' ? 'Admin' : 
                               u.role === 'user' ? 'Gebruiker' : 'Kijker'}
                            </Badge>
                            {!u.is_active && u.id !== user?.id && (
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => resendInviteMutation.mutate(u.id)}
                                disabled={resendInviteMutation.isPending}
                                title="Uitnodiging opnieuw versturen"
                              >
                                <Mail className="h-4 w-4" />
                              </Button>
                            )}
                            {u.id !== user?.id && u.role !== 'owner' && (
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => {
                                  if (confirm(`Weet je zeker dat je ${u.first_name} ${u.last_name} wilt verwijderen?`)) {
                                    deleteUserMutation.mutate(u.id)
                                  }
                                }}
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardBody>
                </Card>

                {/* Invite User Modal */}
                <Modal
                  isOpen={isAddUserModalOpen}
                  onClose={() => setIsAddUserModalOpen(false)}
                  title="Gebruiker uitnodigen"
                  description="De gebruiker ontvangt een e-mail om zelf een wachtwoord in te stellen."
                >
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <Input
                        label="Voornaam"
                        value={newUserData.first_name}
                        onChange={(e) => setNewUserData({ ...newUserData, first_name: e.target.value })}
                        placeholder="Jan"
                        required
                      />
                      <Input
                        label="Achternaam"
                        value={newUserData.last_name}
                        onChange={(e) => setNewUserData({ ...newUserData, last_name: e.target.value })}
                        placeholder="Jansen"
                        required
                      />
                    </div>
                    <Input
                      label="E-mailadres"
                      type="email"
                      value={newUserData.email}
                      onChange={(e) => setNewUserData({ ...newUserData, email: e.target.value })}
                      placeholder="jan@bedrijf.nl"
                      required
                    />
                    <Input
                      label="Telefoonnummer"
                      type="tel"
                      value={newUserData.phone}
                      onChange={(e) => setNewUserData({ ...newUserData, phone: e.target.value })}
                      placeholder="+31 6 12345678"
                    />
                    <Select
                      label="Rol"
                      value={newUserData.role}
                      onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value as any })}
                    >
                      <option value="viewer">Kijker - Alleen bekijken</option>
                      <option value="user">Gebruiker - Basistoegang</option>
                      <option value="admin">Admin - Volledige toegang</option>
                    </Select>
                    <div className="flex gap-3 pt-4">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => setIsAddUserModalOpen(false)}
                      >
                        Annuleren
                      </Button>
                      <Button
                        className="flex-1"
                        onClick={handleInviteUser}
                        disabled={inviteUserMutation.isPending || !newUserData.email || !newUserData.first_name || !newUserData.last_name}
                      >
                        {inviteUserMutation.isPending ? 'Versturen...' : 'Uitnodiging versturen'}
                      </Button>
                    </div>
                  </div>
                </Modal>
              </motion.div>
            )}

            {/* Email Change Verification Modal */}
            <Modal
              isOpen={isEmailModalOpen}
              onClose={closeEmailModal}
              title="E-mailadres wijzigen"
              description={
                emailStep === 1
                  ? 'Voer uw nieuwe e-mailadres in. We sturen een verificatiecode naar uw huidige e-mailadres.'
                  : `We hebben een 6-cijferige code gestuurd naar ${currentUser?.email}. Voer de code in om de wijziging te bevestigen.`
              }
            >
              {emailStep === 1 ? (
                <div className="space-y-4">
                  <Input
                    label="Nieuw e-mailadres"
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="nieuw@email.nl"
                  />
                  <div className="flex gap-3 pt-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={closeEmailModal}
                    >
                      Annuleren
                    </Button>
                    <Button
                      className="flex-1"
                      onClick={() => requestEmailChangeMutation.mutate(newEmail)}
                      disabled={!newEmail || requestEmailChangeMutation.isPending}
                      isLoading={requestEmailChangeMutation.isPending}
                    >
                      Verstuur code
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Nieuw e-mailadres:</p>
                    <p className="font-medium text-gray-900">{newEmail}</p>
                  </div>

                  {/* Code Input */}
                  <div className="flex justify-center gap-2">
                    {emailCode.map((digit, index) => (
                      <input
                        key={index}
                        ref={(el) => { emailCodeRefs.current[index] = el }}
                        type="text"
                        inputMode="numeric"
                        maxLength={1}
                        value={digit}
                        onChange={(e) => handleEmailCodeChange(index, e.target.value)}
                        onKeyDown={(e) => handleEmailCodeKeyDown(index, e)}
                        onPaste={index === 0 ? handleEmailCodePaste : undefined}
                        className="w-12 h-14 text-center text-2xl font-bold border-2 border-gray-300 rounded-lg focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 outline-none transition-all"
                        disabled={verifyEmailChangeMutation.isPending}
                      />
                    ))}
                  </div>

                  {/* Verify Button */}
                  <Button
                    onClick={() => verifyEmailChangeMutation.mutate(emailCode.join(''))}
                    className="w-full"
                    isLoading={verifyEmailChangeMutation.isPending}
                    disabled={emailCode.some(d => d === '')}
                  >
                    Bevestigen
                  </Button>

                  {/* Resend */}
                  <div className="text-center">
                    <p className="text-sm text-gray-600 mb-2">
                      Geen code ontvangen?
                    </p>
                    <button
                      onClick={handleResendEmailCode}
                      disabled={requestEmailChangeMutation.isPending || emailCooldown > 0}
                      className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <RefreshCw className={`mr-2 h-4 w-4 ${requestEmailChangeMutation.isPending ? 'animate-spin' : ''}`} />
                      {emailCooldown > 0
                        ? `Opnieuw versturen (${emailCooldown}s)`
                        : 'Opnieuw versturen'}
                    </button>
                  </div>

                  {/* Help text */}
                  <p className="text-xs text-center text-gray-500">
                    De code is 10 minuten geldig. Controleer ook uw spam folder.
                  </p>
                </div>
              )}
            </Modal>

            {activeTab === 'security' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                {user?.oauth_provider === 'google' ? (
                  <Card>
                    <CardHeader>
                      <CardTitle>Ingelogd via Google</CardTitle>
                      <CardDescription>Je account is gekoppeld aan Google.</CardDescription>
                    </CardHeader>
                    <CardBody>
                      <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
                        <p className="text-sm text-blue-800">
                          Je bent ingelogd via je Google account. Je wachtwoord en accountbeveiliging beheer je via{' '}
                          <a 
                            href="https://myaccount.google.com/security" 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="font-medium underline hover:text-blue-900"
                          >
                            Google Account Instellingen
                          </a>.
                        </p>
                      </div>
                    </CardBody>
                  </Card>
                ) : (
                  <Card>
                    <CardHeader>
                      <CardTitle>Wachtwoord wijzigen</CardTitle>
                      <CardDescription>Wijzig uw wachtwoord voor extra beveiliging.</CardDescription>
                    </CardHeader>
                    <CardBody className="space-y-4">
                      <Input
                        label="Huidig wachtwoord"
                        type="password"
                        placeholder="••••••••"
                      />
                      <Input
                        label="Nieuw wachtwoord"
                        type="password"
                        placeholder="••••••••"
                        helperText="Minimaal 8 karakters met hoofdletter, kleine letter en cijfer"
                      />
                      <Input
                        label="Nieuw wachtwoord bevestigen"
                        type="password"
                        placeholder="••••••••"
                      />
                      <Button>Wachtwoord wijzigen</Button>
                    </CardBody>
                  </Card>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle>Sessies</CardTitle>
                    <CardDescription>Beheer uw actieve sessies.</CardDescription>
                  </CardHeader>
                  <CardBody>
                    <div className="p-4 rounded-lg bg-gray-50 flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">Huidige sessie</p>
                        <p className="text-sm text-gray-500">Ingelogd op {new Date().toLocaleDateString('nl-NL')}</p>
                      </div>
                      <Badge variant="success">Actief</Badge>
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600" />
        </div>
      </DashboardLayout>
    }>
      <SettingsContent />
    </Suspense>
  )
}
