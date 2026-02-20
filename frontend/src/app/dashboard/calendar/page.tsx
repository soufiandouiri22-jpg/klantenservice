'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Calendar, RefreshCw, Settings, Trash2, Check, ExternalLink, Star } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Select'
import { calendarsApi, aiWorkersApi } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

const providers = [
  {
    id: 'google',
    name: 'Google Calendar',
    icon: '📅',
    description: 'Koppel uw Google Calendar account',
    color: 'bg-blue-100 text-blue-700',
  },
  {
    id: 'microsoft',
    name: 'Microsoft Outlook',
    icon: '📧',
    description: 'Koppel uw Outlook/Office 365 agenda',
    color: 'bg-sky-100 text-sky-700',
  },
  {
    id: 'caldav',
    name: 'CalDAV',
    icon: '🔗',
    description: 'Koppel een CalDAV-compatibele agenda',
    color: 'bg-gray-100 text-gray-700',
  },
]

export default function CalendarPage() {
  const queryClient = useQueryClient()
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedCalendar, setSelectedCalendar] = useState<any>(null)
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

  // CalDAV form state
  const [caldavName, setCaldavName] = useState('')
  const [caldavUrl, setCaldavUrl] = useState('')
  const [caldavUsername, setCaldavUsername] = useState('')
  const [caldavPassword, setCaldavPassword] = useState('')

  const [selectedWorkerId, setSelectedWorkerId] = useState<string>('')

  const { data: calendars, isLoading } = useQuery({
    queryKey: ['calendars'],
    queryFn: calendarsApi.list,
  })

  const { data: workers } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  // Filter workers that don't already have a calendar linked
  const availableWorkers = workers?.filter((w: any) => !w.linked_calendar) || []

  const createMutation = useMutation({
    mutationFn: calendarsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('Agenda toegevoegd')
      setIsAddModalOpen(false)
      resetForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij toevoegen')
    },
  })

  const syncMutation = useMutation({
    mutationFn: calendarsApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      toast.success('Synchronisatie gestart')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      calendarsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      toast.success('Instellingen opgeslagen')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: calendarsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      toast.success('Agenda ontkoppeld')
      setSelectedCalendar(null)
    },
  })

  const resetForm = () => {
    setSelectedProvider(null)
    setSelectedWorkerId('')
    setCaldavName('')
    setCaldavUrl('')
    setCaldavUsername('')
    setCaldavPassword('')
  }

  const handleConnectOAuth = async (provider: string) => {
    try {
      const response = await calendarsApi.getOAuthUrl(provider)
      // In production, redirect to OAuth URL
      toast.success(`Koppeling voor ${provider} gestart`)
      setIsAddModalOpen(false)
    } catch (error) {
      toast.error('Fout bij starten OAuth')
    }
  }

  const handleConnectCalDAV = () => {
    if (!caldavName || !caldavUrl || !caldavUsername || !caldavPassword) {
      toast.error('Vul alle velden in')
      return
    }
    if (!selectedWorkerId) {
      toast.error('Selecteer een AI-medewerker')
      return
    }
    createMutation.mutate({
      name: caldavName,
      provider: 'caldav',
      ai_worker_id: selectedWorkerId,
      caldav_url: caldavUrl,
      caldav_username: caldavUsername,
      caldav_password: caldavPassword,
    })
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const getProviderInfo = (provider: string) => {
    return providers.find((p) => p.id === provider) || providers[2]
  }

  return (
    <DashboardLayout>
      <Header
        title="Agenda"
        description="Beheer uw agenda-integraties voor het inplannen van afspraken."
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsAddModalOpen(true)}
          >
            Agenda koppelen
          </Button>
        }
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Info */}
        <Card>
          <CardBody>
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
                <Calendar className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Hoe werkt het?</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Koppel uw agenda zodat de AI-medewerkers beschikbaarheid kunnen controleren 
                  en direct afspraken kunnen inplannen. U bepaalt zelf de regels: openingstijden, 
                  afspraakduur, buffers en meer.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Calendars List */}
        {calendars?.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="Geen agenda's gekoppeld"
            description="Koppel een agenda zodat de AI afspraken kan maken."
            action={
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsAddModalOpen(true)}>
                Agenda koppelen
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            {calendars?.map((calendar: any) => {
              const providerInfo = getProviderInfo(calendar.provider)
              return (
                <motion.div
                  key={calendar.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <Card>
                    <CardBody>
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div className={`flex h-12 w-12 items-center justify-center rounded-lg text-2xl ${providerInfo.color}`}>
                            {providerInfo.icon}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-medium text-gray-900">{calendar.name}</h3>
                              {calendar.is_primary && (
                                <Badge variant="primary">
                                  <Star className="h-3 w-3 mr-1" />
                                  Primair
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-500">{providerInfo.name}</p>
                            {calendar.external_calendar_name && (
                              <p className="text-xs text-gray-400 mt-1">
                                {calendar.external_calendar_name}
                              </p>
                            )}
                            <p className="text-xs text-gray-400 mt-1">
                              Gekoppeld aan: {workers?.find((w: any) => w.id === calendar.ai_worker_id)?.name || 'Geen medewerker'}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          {calendar.sync_error ? (
                            <Badge variant="danger">Sync fout</Badge>
                          ) : (
                            <Badge variant="success">
                              <Check className="h-3 w-3 mr-1" />
                              Gekoppeld
                            </Badge>
                          )}
                        </div>
                      </div>

                      {calendar.sync_error && (
                        <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-100">
                          <p className="text-sm text-red-700">{calendar.sync_error}</p>
                        </div>
                      )}

                      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-500">Standaard duur</p>
                          <p className="font-medium text-gray-900">
                            {calendar.availability_rules?.default_appointment_duration_minutes || 30} min
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-500">Buffer na afspraak</p>
                          <p className="font-medium text-gray-900">
                            {calendar.availability_rules?.buffer_after_minutes || 15} min
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-500">Laatst gesynchroniseerd</p>
                          <p className="font-medium text-gray-900">
                            {calendar.last_sync_at ? formatRelativeTime(calendar.last_sync_at) : 'Nooit'}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-3 pt-4 border-t border-gray-100">
                        <Button
                          variant="outline"
                          size="sm"
                          leftIcon={<RefreshCw className="h-4 w-4" />}
                          onClick={() => syncMutation.mutate(calendar.id)}
                        >
                          Synchroniseren
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          leftIcon={<Settings className="h-4 w-4" />}
                          onClick={() => setSelectedCalendar(calendar)}
                        >
                          Instellingen
                        </Button>
                        {!calendar.is_primary && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => updateMutation.mutate({ id: calendar.id, data: { is_primary: true } })}
                          >
                            Als primair instellen
                          </Button>
                        )}
                        <div className="flex-1" />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm('Weet u zeker dat u deze agenda wilt ontkoppelen?')) {
                              deleteMutation.mutate(calendar.id)
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </CardBody>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {/* Add Calendar Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false)
          resetForm()
        }}
        title="Agenda koppelen"
        description="Kies een agenda-provider om te koppelen."
        size="lg"
      >
        {!selectedProvider ? (
          <div className="space-y-5">
            {/* Worker selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Koppel aan AI-medewerker
              </label>
              {availableWorkers.length === 0 ? (
                <p className="text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
                  Alle AI-medewerkers hebben al een agenda gekoppeld. Maak eerst een nieuwe medewerker aan of ontkoppel een bestaande agenda.
                </p>
              ) : (
                <Select
                  value={selectedWorkerId}
                  onChange={(e) => setSelectedWorkerId(e.target.value)}
                >
                  <option value="">Selecteer een medewerker...</option>
                  {availableWorkers.map((w: any) => (
                    <option key={w.id} value={w.id}>{w.name} — {w.role_title}</option>
                  ))}
                </Select>
              )}
            </div>

            {/* Provider selection */}
            {selectedWorkerId && (
              <div className="grid grid-cols-1 gap-4">
                {providers.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => {
                      if (provider.id === 'caldav') {
                        setSelectedProvider('caldav')
                      } else {
                        handleConnectOAuth(provider.id)
                      }
                    }}
                    className="flex items-center gap-4 p-4 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-left"
                  >
                    <div className={`flex h-12 w-12 items-center justify-center rounded-lg text-2xl ${provider.color}`}>
                      {provider.icon}
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">{provider.name}</h4>
                      <p className="text-sm text-gray-500">{provider.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" onClick={() => setSelectedProvider(null)}>
              ← Terug
            </Button>
            <Input
              label="Naam"
              placeholder="bijv. Werk agenda"
              value={caldavName}
              onChange={(e) => setCaldavName(e.target.value)}
            />
            <Input
              label="CalDAV URL"
              placeholder="https://caldav.example.com/calendar"
              value={caldavUrl}
              onChange={(e) => setCaldavUrl(e.target.value)}
            />
            <Input
              label="Gebruikersnaam"
              value={caldavUsername}
              onChange={(e) => setCaldavUsername(e.target.value)}
            />
            <Input
              label="Wachtwoord"
              type="password"
              value={caldavPassword}
              onChange={(e) => setCaldavPassword(e.target.value)}
            />
            <div className="flex gap-3 pt-4">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setIsAddModalOpen(false)
                  resetForm()
                }}
              >
                Annuleren
              </Button>
              <Button
                className="flex-1"
                onClick={handleConnectCalDAV}
                isLoading={createMutation.isPending}
              >
                Koppelen
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Settings Modal */}
      <Modal
        isOpen={!!selectedCalendar}
        onClose={() => setSelectedCalendar(null)}
        title={`Instellingen: ${selectedCalendar?.name}`}
        size="lg"
      >
        {selectedCalendar && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Standaard afspraakduur (minuten)"
                type="number"
                defaultValue={selectedCalendar.availability_rules?.default_appointment_duration_minutes || 30}
              />
              <Input
                label="Buffer na afspraak (minuten)"
                type="number"
                defaultValue={selectedCalendar.availability_rules?.buffer_after_minutes || 15}
              />
              <Input
                label="Minimale vooraanmelding (uren)"
                type="number"
                defaultValue={selectedCalendar.availability_rules?.min_notice_hours || 1}
              />
              <Input
                label="Max. dagen vooruit boeken"
                type="number"
                defaultValue={selectedCalendar.availability_rules?.max_advance_days || 60}
              />
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
              <Button variant="outline" onClick={() => setSelectedCalendar(null)}>
                Annuleren
              </Button>
              <Button onClick={() => setSelectedCalendar(null)}>
                Opslaan
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
