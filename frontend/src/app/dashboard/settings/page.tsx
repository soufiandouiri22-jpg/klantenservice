'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Building2, Shield, CreditCard, Users, Bell, Key, Trash2, Mail, Clock } from 'lucide-react'
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
import { companyApi, usersApi, authApi, paymentsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

const tabs = [
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
  
  // Get initial tab from URL params or default to 'company'
  const initialTab = searchParams.get('tab') || 'company'
  const [activeTab, setActiveTab] = useState(initialTab)
  
  // Update tab when URL params change
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && tabs.some(t => t.id === tabParam)) {
      setActiveTab(tabParam)
    }
  }, [searchParams])
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false)
  const [newUserData, setNewUserData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    role: 'viewer' as 'owner' | 'admin' | 'user' | 'viewer',
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

  const { setCompany } = useAuthStore()
  
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

  const handleUpgrade = (plan: string, interval: 'monthly' | 'yearly' = 'monthly') => {
    checkoutMutation.mutate({ plan, interval })
  }

  const handleManageSubscription = () => {
    portalMutation.mutate()
  }

  const handleInviteUser = () => {
    inviteUserMutation.mutate(newUserData)
  }

  const isLoading = companyLoading || privacyLoading || subscriptionLoading || usersLoading

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
            {activeTab === 'company' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Bedrijfsgegevens</CardTitle>
                    <CardDescription>Algemene informatie over uw bedrijf.</CardDescription>
                  </CardHeader>
                  <CardBody className="space-y-4">
                    <Input
                      label="Bedrijfsnaam"
                      defaultValue={companyData?.name}
                      onBlur={(e) => {
                        if (e.target.value !== companyData?.name) {
                          updateCompanyMutation.mutate({ name: e.target.value })
                        }
                      }}
                    />
                    <Input
                      label="E-mailadres"
                      type="email"
                      defaultValue={companyData?.email}
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
                      <Input
                        label="BTW-nummer"
                        defaultValue={companyData?.btw_number}
                        onBlur={(e) => {
                          if (e.target.value !== companyData?.btw_number) {
                            updateCompanyMutation.mutate({ btw_number: e.target.value })
                          }
                        }}
                      />
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
                      placeholder="U spreekt met de digitale assistent van {company_name}"
                    />
                    <p className="mt-2 text-sm text-gray-500">
                      Gebruik <code className="px-1 py-0.5 bg-gray-100 rounded">{'{company_name}'}</code> om automatisch de bedrijfsnaam in te vullen.
                    </p>
                  </CardBody>
                </Card>
              </motion.div>
            )}

            {activeTab === 'subscription' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Huidig abonnement</CardTitle>
                  </CardHeader>
                  <CardBody>
                    <div className="flex items-center justify-between p-4 rounded-lg bg-primary-50 border border-primary-100">
                      <div>
                        <h3 className="text-lg font-semibold text-primary-900 capitalize">
                          {subscription?.plan} Plan
                        </h3>
                        <p className="text-sm text-primary-700">
                          {subscription?.max_ai_workers} AI-medewerker(s)
                        </p>
                      </div>
                      <Badge variant="success">Actief</Badge>
                    </div>

                    <div className="mt-6 grid grid-cols-3 gap-4">
                      {['starter', 'business', 'enterprise'].map((plan) => (
                        <div
                          key={plan}
                          className={`p-4 rounded-lg border-2 ${
                            subscription?.plan === plan
                              ? 'border-primary-500 bg-primary-50'
                              : 'border-gray-200'
                          }`}
                        >
                          <h4 className="font-medium text-gray-900 capitalize">{plan}</h4>
                          <p className="text-sm text-gray-500">
                            {plan === 'starter' ? '1' : plan === 'business' ? '5' : '5+'} AI-medewerkers
                          </p>
                          {subscription?.plan !== plan && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="mt-3 w-full"
                              onClick={() => handleUpgrade(plan)}
                              disabled={checkoutMutation.isPending}
                            >
                              {checkoutMutation.isPending ? 'Laden...' : (subscription?.plan === 'starter' ? 'Upgraden' : 'Wijzigen')}
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Manage subscription button for existing Stripe customers */}
                    {subscription?.has_stripe && (
                      <div className="mt-6 pt-6 border-t border-gray-200">
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
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
                      <select
                        value={newUserData.role}
                        onChange={(e) => setNewUserData({ ...newUserData, role: e.target.value as any })}
                        className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                      >
                        <option value="viewer">Kijker - Alleen bekijken</option>
                        <option value="user">Gebruiker - Basistoegang</option>
                        <option value="admin">Admin - Volledige toegang</option>
                      </select>
                    </div>
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
