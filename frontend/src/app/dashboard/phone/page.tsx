'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Phone, Settings, Clock, Trash2, Headphones, Plus,
  Check, ArrowRight, ArrowLeft, Copy, PhoneCall,
  CheckCircle2, XCircle, Loader2, HelpCircle
} from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Select'
import Link from 'next/link'
import { phoneNumbersApi, aiWorkersApi } from '@/lib/api'
import { formatPhoneNumber } from '@/lib/utils'
import { useAuthStore } from '@/lib/store'

// Provider data for forwarding codes
const providers = [
  { id: 'kpn', name: 'KPN', code: '*21*', note: 'Vast & Mobiel' },
  { id: 'vodafone', name: 'Vodafone', code: '**21*', note: 'Mobiel' },
  { id: 't-mobile', name: 'T-Mobile', code: '**21*', note: 'Mobiel' },
  { id: 'ziggo', name: 'Ziggo', code: '*21*', note: 'Vast' },
  { id: 'odido', name: 'Odido', code: '**21*', note: 'Mobiel' },
  { id: 'anders', name: 'Anders', code: '*21*', note: 'Standaard' },
]

const days = [
  { key: 'monday', label: 'Maandag' },
  { key: 'tuesday', label: 'Dinsdag' },
  { key: 'wednesday', label: 'Woensdag' },
  { key: 'thursday', label: 'Donderdag' },
  { key: 'friday', label: 'Vrijdag' },
  { key: 'saturday', label: 'Zaterdag' },
  { key: 'sunday', label: 'Zondag' },
]

export default function PhonePage() {
  const queryClient = useQueryClient()
  const { company, user } = useAuthStore()
  const canEdit = user?.role === 'owner' || user?.role === 'admin'
  
  // Wizard state
  const [isWizardOpen, setIsWizardOpen] = useState(false)
  const [wizardStep, setWizardStep] = useState(1)
  const [businessNumber, setBusinessNumber] = useState('')
  const [friendlyName, setFriendlyName] = useState('')
  const [selectedAIWorkerId, setSelectedAIWorkerId] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [createdPhone, setCreatedPhone] = useState<any>(null)
  
  // Settings modal state
  const [selectedPhone, setSelectedPhone] = useState<any>(null)
  const [settingsForm, setSettingsForm] = useState<any>(null)
  
  // Default business hours
  const defaultBusinessHours = {
    monday: { open: '09:00', close: '17:00', enabled: true },
    tuesday: { open: '09:00', close: '17:00', enabled: true },
    wednesday: { open: '09:00', close: '17:00', enabled: true },
    thursday: { open: '09:00', close: '17:00', enabled: true },
    friday: { open: '09:00', close: '17:00', enabled: true },
    saturday: { open: '09:00', close: '17:00', enabled: false },
    sunday: { open: '09:00', close: '17:00', enabled: false },
  }

  // Queries
  const { data: phoneNumbers, isLoading } = useQuery({
    queryKey: ['phone-numbers'],
    queryFn: phoneNumbersApi.list,
  })

  const { data: aiWorkers } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: phoneNumbersApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      setCreatedPhone(data)
      setWizardStep(2)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Er ging iets mis')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      phoneNumbersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Instellingen opgeslagen')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: phoneNumbersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('Telefoon losgekoppeld')
      closeSettings()
    },
  })

  // Wizard functions
  const openWizard = () => {
    setIsWizardOpen(true)
    setWizardStep(1)
    setBusinessNumber('')
    setFriendlyName('')
    setSelectedAIWorkerId('')
    setSelectedProvider('')
    setCreatedPhone(null)
  }

  const closeWizard = () => {
    setIsWizardOpen(false)
    setWizardStep(1)
    setBusinessNumber('')
    setFriendlyName('')
    setSelectedAIWorkerId('')
    setSelectedProvider('')
    setCreatedPhone(null)
  }

  const handleStep1Submit = () => {
    if (!businessNumber.trim()) {
      toast.error('Voer uw telefoonnummer in')
      return
    }
    createMutation.mutate({
      business_number: businessNumber,
      friendly_name: friendlyName || undefined,
      ai_worker_id: selectedAIWorkerId || undefined,
    })
  }

  const handleProviderSelect = (providerId: string) => {
    setSelectedProvider(providerId)
    if (createdPhone) {
      updateMutation.mutate({
        id: createdPhone.id,
        data: { provider: providerId },
      })
    }
  }

  const handleSetupComplete = () => {
    if (createdPhone) {
      updateMutation.mutate({
        id: createdPhone.id,
        data: { setup_completed: true },
      })
    }
    setWizardStep(4)
  }

  const handleVerifySuccess = () => {
    if (createdPhone) {
      updateMutation.mutate({
        id: createdPhone.id,
        data: { forwarding_verified: true },
      })
    }
    toast.success('Gelukt! Uw telefoon is nu gekoppeld.')
    closeWizard()
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Gekopieerd!')
  }

  // Get forwarding code for selected provider
  const getForwardingCode = () => {
    const provider = providers.find(p => p.id === selectedProvider)
    if (!provider || !createdPhone) return ''
    const number = createdPhone.number.replace('+', '')
    return `${provider.code}${number}#`
  }

  // Settings functions
  const openSettings = (phone: any) => {
    setSelectedPhone(phone)
    const mergedBusinessHours = { ...defaultBusinessHours }
    if (phone.business_hours) {
      Object.keys(phone.business_hours).forEach((day) => {
        mergedBusinessHours[day as keyof typeof defaultBusinessHours] = {
          ...defaultBusinessHours[day as keyof typeof defaultBusinessHours],
          ...phone.business_hours[day],
        }
      })
    }
    setSettingsForm({
      ai_worker_id: phone.ai_worker_id || '',
      business_hours: mergedBusinessHours,
      voicemail_enabled: phone.voicemail_enabled ?? true,
      voicemail_greeting: phone.voicemail_greeting || '',
      voicemail_email: phone.voicemail_email || '',
      sms_confirmation_enabled: phone.sms_confirmation_enabled ?? false,
      sms_confirmation_template: phone.sms_confirmation_template || 'Uw afspraak bij {bedrijfsnaam} is bevestigd op {datum} om {tijd}. Tot dan!',
      sms_callback_template: phone.sms_callback_template || 'Uw verzoek is genoteerd bij {bedrijfsnaam}. U wordt zo snel mogelijk teruggebeld.',
      transfer_enabled: phone.transfer_enabled ?? false,
      transfer_number: phone.transfer_number || '',
      after_hours_message: phone.after_hours_message || '',
    })
  }

  const closeSettings = () => {
    setSelectedPhone(null)
    setSettingsForm(null)
  }

  const handleSaveSettings = () => {
    if (!selectedPhone || !settingsForm) return
    updateMutation.mutate({
      id: selectedPhone.id,
      data: {
        ...settingsForm,
        ai_worker_id: settingsForm.ai_worker_id || null,
      },
    })
    closeSettings()
  }

  const toggleBusinessDay = (dayKey: string) => {
    setSettingsForm((prev: any) => ({
      ...prev,
      business_hours: {
        ...prev.business_hours,
        [dayKey]: {
          ...prev.business_hours[dayKey],
          enabled: !prev.business_hours[dayKey]?.enabled,
        },
      },
    }))
  }

  const updateBusinessHours = (dayKey: string, field: 'open' | 'close', value: string) => {
    setSettingsForm((prev: any) => ({
      ...prev,
      business_hours: {
        ...prev.business_hours,
        [dayKey]: {
          ...prev.business_hours[dayKey],
          [field]: value,
        },
      },
    }))
  }

  // Helper functions
  const getAIWorkerName = (workerId: string | null) => {
    if (!workerId || !aiWorkers) return null
    const worker = aiWorkers.find((w: any) => w.id === workerId)
    return worker?.name || null
  }

  // Check phone number limit (same as AI workers limit)
  const maxPhoneNumbers = company?.max_ai_workers || 1
  const canAddPhone = (phoneNumbers?.length || 0) < maxPhoneNumbers

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  // Workers that don't have a phone number yet (for "Koppel aan AI-medewerker" in wizard)
  const availableWorkersForPhone = aiWorkers?.filter((w: any) => !w.linked_phone) || []

  return (
    <DashboardLayout>
      <Header
        title="Telefonie"
        description={`${phoneNumbers?.length || 0} van ${maxPhoneNumbers} nummers gekoppeld`}
        actions={
          canEdit && phoneNumbers?.length > 0 ? (
            <Button onClick={openWizard} disabled={!canAddPhone}>
              Nog een nummer koppelen
            </Button>
          ) : null
        }
      />

      <div className={phoneNumbers?.length === 0 ? "flex items-center justify-center min-h-[calc(100vh-4rem)] pb-24 px-4" : "p-4 sm:p-6 space-y-6"}>
        {phoneNumbers?.length === 0 ? (
          <EmptyState
            icon={Phone}
            title="Koppel uw telefoonnummer"
            description="Laat de AI uw zakelijke telefoontjes beantwoorden. Klanten bellen uw bestaande nummer en worden automatisch geholpen."
            action={
              canEdit ? (
                <Button leftIcon={<Plus className="h-4 w-4" />} onClick={openWizard}>
                  Mijn nummer koppelen
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {phoneNumbers?.map((phone: any) => (
              <motion.div
                key={phone.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card>
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                          <Phone className="h-6 w-6 text-primary-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            {phone.friendly_name || 'Mijn bedrijf'}
                          </h3>
                          <p className="text-lg font-mono text-gray-700">
                            {formatPhoneNumber(phone.business_number || phone.number)}
                          </p>
                        </div>
                      </div>
                      <Badge variant={phone.is_active && phone.forwarding_verified ? 'success' : phone.setup_completed ? 'warning' : 'gray'}>
                        {phone.is_active && phone.forwarding_verified ? 'Actief' : phone.setup_completed ? 'Bijna klaar' : 'Instellen'}
                      </Badge>
                    </div>

                    {/* Status indicator */}
                    {phone.forwarding_verified ? (
                      <div className="mt-4 p-3 rounded-lg bg-green-50 border border-green-200">
                        <div className="flex items-center gap-2 text-sm text-green-700">
                          <CheckCircle2 className="h-4 w-4" />
                          <span>AI beantwoordt uw gesprekken</span>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200">
                        <div className="flex items-center gap-2 text-sm text-amber-700">
                          <HelpCircle className="h-4 w-4" />
                          <span>Doorschakelen nog niet ingesteld</span>
                        </div>
                      </div>
                    )}

                    {/* AI Worker */}
                    {phone.ai_worker_id && (
                      <div className="mt-4 p-3 rounded-lg bg-primary-50 border border-primary-100">
                        <div className="flex items-center gap-2 text-sm">
                          <Headphones className="h-4 w-4 text-primary-600" />
                          <span className="text-primary-700">
                            Beantwoord door: <strong>{getAIWorkerName(phone.ai_worker_id)}</strong>
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Business Hours Preview */}
                    <div className="mt-4 p-3 rounded-lg bg-gray-50">
                      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                        <Clock className="h-4 w-4" />
                        <span className="font-medium">Openingstijden</span>
                      </div>
                      {phone.business_hours && days.every((day) => {
                        const h = phone.business_hours[day.key]
                        return h?.enabled && h?.open === '00:00' && h?.close === '23:59'
                      }) ? (
                        <div className="flex items-center justify-center py-2">
                          <span className="px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm font-medium">
                            24/7 beschikbaar
                          </span>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                          {days.map((day) => {
                            const hours = phone.business_hours?.[day.key]
                            return (
                              <div key={day.key} className="flex justify-between">
                                <span className="text-gray-500">{day.label.slice(0, 2)}</span>
                                <span className={hours?.enabled ? 'text-gray-900' : 'text-gray-400'}>
                                  {hours?.enabled ? `${hours.open} - ${hours.close}` : 'Gesloten'}
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    {canEdit && (
                      <div className="mt-4 flex items-center gap-3 pt-4 border-t border-gray-100">
                        <Button
                          variant="outline"
                          size="sm"
                          leftIcon={<Settings className="h-4 w-4" />}
                          onClick={() => openSettings(phone)}
                        >
                          Instellingen
                        </Button>
                      </div>
                    )}
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {/* Upgrade Banner - shown when limit reached */}
        {!canAddPhone && phoneNumbers && phoneNumbers.length > 0 && (
          <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-4">
            <p className="text-sm text-amber-800">
              U heeft het maximum aantal telefoonnummers voor uw abonnement bereikt. 
              <a href="/dashboard/settings?tab=subscription" className="font-medium underline ml-1">
                Upgrade uw abonnement
              </a>
              {' '}voor meer nummers.
            </p>
          </div>
        )}
      </div>

      {/* Setup Wizard Modal */}
      <Modal
        isOpen={isWizardOpen}
        onClose={closeWizard}
        title=""
        size="lg"
      >
        <div className="py-2">
          {/* Progress indicator */}
          <div className="flex items-center justify-center mb-8">
            {[1, 2, 3, 4].map((step) => (
              <div key={step} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    wizardStep >= step
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {wizardStep > step ? <Check className="h-4 w-4" /> : step}
                </div>
                {step < 4 && (
                  <div
                    className={`w-12 h-1 ${
                      wizardStep > step ? 'bg-primary-600' : 'bg-gray-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {/* Step 1: Enter business number */}
            {wizardStep === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <h2 className="text-xl font-semibold text-gray-900">
                    Koppel uw telefoonnummer
                  </h2>
                  <p className="mt-2 text-gray-600">
                    Wat is het telefoonnummer van uw bedrijf?
                  </p>
                </div>

                <div className="space-y-4">
                  <Input
                    label="Telefoonnummer"
                    placeholder="020 123 4567"
                    value={businessNumber}
                    onChange={(e) => setBusinessNumber(e.target.value)}
                    className="text-lg"
                  />
                  <p className="text-sm text-gray-500">
                    Dit is het nummer dat klanten nu bellen.
                  </p>

                  <Input
                    label="Naam (optioneel)"
                    placeholder="bijv. Kapsalon De Schaar"
                    value={friendlyName}
                    onChange={(e) => setFriendlyName(e.target.value)}
                  />

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Koppel aan AI-medewerker
                    </label>
                    {availableWorkersForPhone.length === 0 ? (
                      <p className="text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
                        {!aiWorkers?.length
                          ? 'Maak eerst een AI-medewerker aan voordat u een telefoonnummer kunt koppelen.'
                          : 'Alle AI-medewerkers hebben al een telefoonnummer gekoppeld. Maak eerst een nieuwe medewerker aan of ontkoppel een bestaand nummer.'}
                      </p>
                    ) : (
                      <Select
                        value={selectedAIWorkerId}
                        onChange={(e) => setSelectedAIWorkerId(e.target.value)}
                      >
                        <option value="">Selecteer een medewerker...</option>
                        {availableWorkersForPhone.map((worker: any) => (
                          <option key={worker.id} value={worker.id}>
                            {worker.name} — {worker.role_title}
                          </option>
                        ))}
                      </Select>
                    )}
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <Button
                    onClick={handleStep1Submit}
                    isLoading={createMutation.isPending}
                    rightIcon={<ArrowRight className="h-4 w-4" />}
                  >
                    Volgende
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 2: AI number assigned */}
            {wizardStep === 2 && createdPhone && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
                    <CheckCircle2 className="h-6 w-6 text-green-600" />
                  </div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    Uw AI-telefoonnummer is klaar!
                  </h2>
                  <p className="mt-2 text-gray-600">
                    Dit nummer neemt straks uw gesprekken aan.
                  </p>
                </div>

                <div className="bg-gray-50 rounded-xl p-6 text-center">
                  <p className="text-sm text-gray-500 mb-2">Uw AI-telefoonnummer</p>
                  <p className="text-2xl font-mono font-semibold text-gray-900">
                    {formatPhoneNumber(createdPhone.number)}
                  </p>
                </div>

                <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-blue-800">
                    Nu moeten we uw nummer ({formatPhoneNumber(createdPhone.business_number)}) doorverbinden naar dit AI-nummer.
                  </p>
                </div>

                <div className="flex justify-between pt-4">
                  <Button variant="outline" onClick={() => setWizardStep(1)} leftIcon={<ArrowLeft className="h-4 w-4" />}>
                    Terug
                  </Button>
                  <Button onClick={() => setWizardStep(3)} rightIcon={<ArrowRight className="h-4 w-4" />}>
                    Volgende
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 3: Forwarding instructions */}
            {wizardStep === 3 && createdPhone && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <h2 className="text-xl font-semibold text-gray-900">
                    Doorschakelen activeren
                  </h2>
                  <p className="mt-2 text-gray-600">
                    Wie is uw telefoonprovider?
                  </p>
                </div>

                {/* Provider selection */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {providers.map((provider) => (
                    <button
                      key={provider.id}
                      onClick={() => handleProviderSelect(provider.id)}
                      className={`p-3 rounded-lg border-2 text-center transition-all ${
                        selectedProvider === provider.id
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="font-medium text-gray-900">{provider.name}</span>
                      <p className="text-xs text-gray-500 mt-1">{provider.note}</p>
                    </button>
                  ))}
                </div>

                {selectedProvider && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-4"
                  >
                    <div className="border-t border-gray-200 pt-6">
                      <p className="text-sm font-medium text-gray-700 mb-3">
                        Toets dit in op uw zakelijke telefoon:
                      </p>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-900 rounded-lg p-4">
                          <code className="text-xl font-mono text-white">
                            {getForwardingCode()}
                          </code>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(getForwardingCode())}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-3">Zo werkt het:</h4>
                      <ol className="space-y-2 text-sm text-gray-600">
                        <li className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-5 h-5 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-medium">1</span>
                          <span>Pak de telefoon van uw zaak</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-5 h-5 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-medium">2</span>
                          <span>Toets de code hierboven in</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-5 h-5 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-medium">3</span>
                          <span>Druk op de belknop</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="flex-shrink-0 w-5 h-5 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-medium">4</span>
                          <span>U hoort een bevestiging</span>
                        </li>
                      </ol>
                    </div>

                    <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
                      <p className="text-sm text-blue-800">
                        <strong>Tip:</strong> Doorschakelen uitzetten kan later met <code className="bg-blue-100 px-1 rounded">#21#</code>
                      </p>
                    </div>
                  </motion.div>
                )}

                <div className="flex justify-between pt-4">
                  <Button variant="outline" onClick={() => setWizardStep(2)} leftIcon={<ArrowLeft className="h-4 w-4" />}>
                    Terug
                  </Button>
                  <Button 
                    onClick={handleSetupComplete} 
                    disabled={!selectedProvider}
                    rightIcon={<ArrowRight className="h-4 w-4" />}
                  >
                    Ik heb dit gedaan
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 4: Test */}
            {wizardStep === 4 && createdPhone && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                <div className="text-center">
                  <div className="mx-auto w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center mb-4">
                    <PhoneCall className="h-6 w-6 text-primary-600" />
                  </div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    Bijna klaar! Laten we testen.
                  </h2>
                  <p className="mt-2 text-gray-600">
                    Bel nu met uw mobiel naar uw zaak.
                  </p>
                </div>

                <div className="bg-gray-50 rounded-xl p-6 text-center">
                  <p className="text-sm text-gray-500 mb-2">Bel dit nummer</p>
                  <p className="text-2xl font-mono font-semibold text-gray-900">
                    {formatPhoneNumber(createdPhone.business_number)}
                  </p>
                  <p className="text-sm text-gray-500 mt-2">
                    Als het goed is, neemt de AI op!
                  </p>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={handleVerifySuccess}
                    className="w-full flex items-center justify-center gap-3 p-4 rounded-lg border-2 border-green-200 bg-green-50 hover:bg-green-100 transition-colors"
                  >
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                    <span className="font-medium text-green-700">Het werkt!</span>
                  </button>
                  
                  <button
                    onClick={() => setWizardStep(3)}
                    className="w-full flex items-center justify-center gap-3 p-4 rounded-lg border-2 border-gray-200 hover:bg-gray-50 transition-colors"
                  >
                    <XCircle className="h-5 w-5 text-gray-500" />
                    <span className="font-medium text-gray-700">Het werkt niet, help mij</span>
                  </button>
                </div>

                <div className="flex justify-start pt-4">
                  <Button variant="outline" onClick={() => setWizardStep(3)} leftIcon={<ArrowLeft className="h-4 w-4" />}>
                    Terug
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Modal>

      {/* Settings Modal */}
      <Modal
        isOpen={!!selectedPhone}
        onClose={closeSettings}
        title={`Instellingen: ${selectedPhone?.friendly_name || formatPhoneNumber(selectedPhone?.business_number || selectedPhone?.number || '')}`}
        size="2xl"
      >
        {selectedPhone && settingsForm && (
          <div className="space-y-6">
            {/* AI Worker Link */}
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Wie neemt op?</h4>
              <div className="bg-primary-50 rounded-lg p-4 border border-primary-100">
                <Select
                  value={settingsForm.ai_worker_id}
                  onChange={(e) => setSettingsForm({ ...settingsForm, ai_worker_id: e.target.value })}
                >
                  <option value="">-- Selecteer AI-medewerker --</option>
                  {aiWorkers?.map((worker: any) => (
                    <option key={worker.id} value={worker.id}>
                      {worker.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {/* Business Hours */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-gray-900">Openingstijden</h4>
                <button
                  type="button"
                  onClick={() => {
                    const is24_7 = Object.values(settingsForm.business_hours).every(
                      (h: any) => h.enabled && h.open === '00:00' && h.close === '23:59'
                    )
                    if (is24_7) {
                      setSettingsForm({ ...settingsForm, business_hours: defaultBusinessHours })
                    } else {
                      const allDay = {
                        monday: { open: '00:00', close: '23:59', enabled: true },
                        tuesday: { open: '00:00', close: '23:59', enabled: true },
                        wednesday: { open: '00:00', close: '23:59', enabled: true },
                        thursday: { open: '00:00', close: '23:59', enabled: true },
                        friday: { open: '00:00', close: '23:59', enabled: true },
                        saturday: { open: '00:00', close: '23:59', enabled: true },
                        sunday: { open: '00:00', close: '23:59', enabled: true },
                      }
                      setSettingsForm({ ...settingsForm, business_hours: allDay })
                    }
                  }}
                  className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                    Object.values(settingsForm.business_hours).every(
                      (h: any) => h.enabled && h.open === '00:00' && h.close === '23:59'
                    )
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  24/7 modus
                </button>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="space-y-2">
                  {days.map((day) => {
                    const hours = settingsForm.business_hours?.[day.key] || {}
                    const isEnabled = hours.enabled ?? false
                    return (
                      <div 
                        key={day.key} 
                        className={`flex items-center py-2 px-3 rounded-md ${isEnabled ? 'bg-white border border-gray-200' : ''}`}
                      >
                        <span className={`w-24 text-sm font-medium ${isEnabled ? 'text-gray-900' : 'text-gray-400'}`}>
                          {day.label}
                        </span>
                        <div className="flex-1 flex items-center justify-end gap-3">
                          {isEnabled ? (
                            <>
                              <input
                                type="time"
                                className="px-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                                value={hours.open ?? '09:00'}
                                onChange={(e) => updateBusinessHours(day.key, 'open', e.target.value)}
                              />
                              <span className="text-gray-400 text-sm">tot</span>
                              <input
                                type="time"
                                className="px-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                                value={hours.close ?? '17:00'}
                                onChange={(e) => updateBusinessHours(day.key, 'close', e.target.value)}
                              />
                            </>
                          ) : (
                            <span className="text-sm text-gray-400 italic">Gesloten</span>
                          )}
                          <button
                            type="button"
                            onClick={() => toggleBusinessDay(day.key)}
                            className={`ml-2 relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                              isEnabled ? 'bg-primary-600' : 'bg-gray-200'
                            }`}
                          >
                            <span
                              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                isEnabled ? 'translate-x-4' : 'translate-x-0'
                              }`}
                            />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Voicemail */}
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Voicemail</h4>
              <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Voicemail inschakelen</p>
                    <p className="text-xs text-gray-500 mt-0.5">Bellers kunnen een bericht achterlaten</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, voicemail_enabled: !settingsForm.voicemail_enabled })}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      settingsForm.voicemail_enabled ? 'bg-primary-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        settingsForm.voicemail_enabled ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
                {settingsForm.voicemail_enabled && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">E-mail voor berichten</label>
                      <input
                        type="email"
                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        value={settingsForm.voicemail_email}
                        onChange={(e) => setSettingsForm({ ...settingsForm, voicemail_email: e.target.value })}
                        placeholder="voicemail@uwbedrijf.nl"
                      />
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* SMS Confirmation */}
            <div>
              <h4 className="font-medium text-gray-900 mb-3">SMS-bevestiging</h4>
              <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Bevestigings-SMS versturen</p>
                    <p className="text-xs text-gray-500 mt-0.5">Stuur automatisch een SMS na het inplannen van een afspraak</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, sms_confirmation_enabled: !settingsForm.sms_confirmation_enabled })}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      settingsForm.sms_confirmation_enabled ? 'bg-primary-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        settingsForm.sms_confirmation_enabled ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
                {settingsForm.sms_confirmation_enabled && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">SMS-tekst</label>
                    <textarea
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                      rows={2}
                      value={settingsForm.sms_confirmation_template}
                      onChange={(e) => setSettingsForm({ ...settingsForm, sms_confirmation_template: e.target.value })}
                      placeholder="Uw afspraak bij {bedrijfsnaam} is bevestigd op {datum} om {tijd}. Tot dan!"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Gebruik {'{bedrijfsnaam}'}, {'{datum}'} en {'{tijd}'} als variabelen.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Call Transfer */}
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Doorverbinden</h4>
              <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Doorverbinden toestaan</p>
                    <p className="text-xs text-gray-500 mt-0.5">Stuur het gesprek door naar een echt telefoonnummer wanneer de beller hierom vraagt of de AI niet kan helpen</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSettingsForm({ ...settingsForm, transfer_enabled: !settingsForm.transfer_enabled })}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      settingsForm.transfer_enabled ? 'bg-primary-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        settingsForm.transfer_enabled ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
                {settingsForm.transfer_enabled && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Telefoonnummer</label>
                    <input
                      type="tel"
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                      value={settingsForm.transfer_number}
                      onChange={(e) => setSettingsForm({ ...settingsForm, transfer_number: e.target.value })}
                      placeholder="0612345678"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Het nummer waarnaar gesprekken worden doorverbonden. Mobiel of vast, bijv. 06, 020, 088.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* After Hours */}
            <div>
              <h4 className="font-medium text-gray-900 mb-3">Buiten openingstijden</h4>
              <div className="bg-gray-50 rounded-lg p-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Bericht voor bellers</label>
                <textarea
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                  rows={2}
                  value={settingsForm.after_hours_message}
                  onChange={(e) => setSettingsForm({ ...settingsForm, after_hours_message: e.target.value })}
                  placeholder="Wij zijn momenteel gesloten. Onze openingstijden zijn..."
                />
              </div>
            </div>

            {/* Forwarding info */}
            {selectedPhone.number && (
              <div>
                <h4 className="font-medium text-gray-900 mb-3">Doorschakelen</h4>
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-100 space-y-4">
                  {/* Activation code */}
                  <div>
                    <p className="text-sm text-blue-800 mb-2 font-medium">
                      Aanzetten:
                    </p>
                    <code className="bg-blue-100 px-2 py-1 rounded font-mono text-blue-900">
                      {(() => {
                        const provider = providers.find(p => p.id === selectedPhone.provider)
                        const code = provider?.code || '*21*'
                        const number = selectedPhone.number.replace('+', '')
                        return `${code}${number}#`
                      })()}
                    </code>
                  </div>
                  {/* Deactivation code */}
                  <div>
                    <p className="text-sm text-blue-800 mb-2 font-medium">
                      Uitzetten:
                    </p>
                    <code className="bg-blue-100 px-2 py-1 rounded font-mono text-blue-900">#21#</code>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              {canEdit && (
                <Button
                  variant="danger"
                  size="sm"
                  leftIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => {
                    if (confirm('Weet u zeker dat u dit nummer wilt loskoppelen?')) {
                      deleteMutation.mutate(selectedPhone.id)
                    }
                  }}
                >
                  Loskoppelen
                </Button>
              )}
              <div className="flex gap-3">
                <Button variant="outline" onClick={closeSettings}>
                  Annuleren
                </Button>
                {canEdit && (
                  <Button 
                    onClick={handleSaveSettings}
                    isLoading={updateMutation.isPending}
                  >
                    Opslaan
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
