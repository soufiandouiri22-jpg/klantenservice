'use client'

import { useState, useEffect, useRef, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Calendar, RefreshCw, Settings, Trash2, Check, ExternalLink, Star, Video, Unlink } from 'lucide-react'
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
    logo: '/app-icons/google-calendar.png',
    description: 'Koppel uw Google Calendar account',
    color: 'bg-blue-100',
  },
  {
    id: 'microsoft',
    name: 'Microsoft Outlook',
    logo: '/app-icons/Outlook_2013_23477.png',
    description: 'Koppel uw Outlook/Office 365 agenda',
    color: 'bg-sky-100',
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
  return (
    <Suspense>
      <CalendarPageInner />
    </Suspense>
  )
}

function SettingsForm({
  calendar,
  onSave,
  onCancel,
  isSaving,
}: {
  calendar: any
  onSave: (data: any) => void
  onCancel: () => void
  isSaving: boolean
}) {
  const durationRef = useRef<HTMLInputElement>(null)
  const bufferRef = useRef<HTMLInputElement>(null)
  const noticeRef = useRef<HTMLInputElement>(null)
  const advanceRef = useRef<HTMLInputElement>(null)
  const meetRef = useRef<HTMLSelectElement>(null)
  const [connectingZoom, setConnectingZoom] = useState(false)
  const [connectingTeams, setConnectingTeams] = useState(false)
  const [connectingGmeet, setConnectingGmeet] = useState(false)
  const isGoogleCalendar = calendar.provider === 'google'

  const handleSave = () => {
    const selectedProvider = meetRef.current?.value || 'none'
    if (selectedProvider === 'zoom' && !calendar.zoom_connected) {
      toast.error('Koppel eerst uw Zoom-account voordat u Zoom selecteert')
      return
    }
    if (selectedProvider === 'teams' && !calendar.teams_connected) {
      toast.error('Koppel eerst uw Microsoft Teams-account voordat u Teams selecteert')
      return
    }
    if (selectedProvider === 'google_meet' && !isGoogleCalendar && !calendar.gmeet_connected) {
      toast.error('Koppel eerst uw Google-account voordat u Google Meet selecteert')
      return
    }
    onSave({
      availability_rules: {
        ...calendar.availability_rules,
        default_appointment_duration_minutes: Number(durationRef.current?.value) || 30,
        buffer_after_minutes: Number(bufferRef.current?.value) || 15,
        min_notice_hours: Number(noticeRef.current?.value) || 1,
        max_advance_days: Number(advanceRef.current?.value) || 60,
      },
      meeting_link_provider: selectedProvider,
    })
  }

  const handleConnectZoom = async () => {
    setConnectingZoom(true)
    try {
      const res = await calendarsApi.getZoomOAuthUrl(calendar.id)
      window.location.href = res.auth_url
    } catch {
      toast.error('Fout bij starten Zoom OAuth')
      setConnectingZoom(false)
    }
  }

  const handleDisconnectZoom = async () => {
    if (!confirm('Weet u zeker dat u Zoom wilt ontkoppelen?')) return
    try {
      await calendarsApi.disconnectZoom(calendar.id)
      toast.success('Zoom ontkoppeld')
      onCancel()
    } catch {
      toast.error('Fout bij ontkoppelen Zoom')
    }
  }

  const handleConnectTeams = async () => {
    setConnectingTeams(true)
    try {
      const res = await calendarsApi.getTeamsOAuthUrl(calendar.id)
      window.location.href = res.auth_url
    } catch {
      toast.error('Fout bij starten Microsoft Teams OAuth')
      setConnectingTeams(false)
    }
  }

  const handleDisconnectTeams = async () => {
    if (!confirm('Weet u zeker dat u Microsoft Teams wilt ontkoppelen?')) return
    try {
      await calendarsApi.disconnectTeams(calendar.id)
      toast.success('Microsoft Teams ontkoppeld')
      onCancel()
    } catch {
      toast.error('Fout bij ontkoppelen Microsoft Teams')
    }
  }

  const handleConnectGmeet = async () => {
    setConnectingGmeet(true)
    try {
      const res = await calendarsApi.getGmeetOAuthUrl(calendar.id)
      window.location.href = res.auth_url
    } catch {
      toast.error('Fout bij starten Google Meet OAuth')
      setConnectingGmeet(false)
    }
  }

  const handleDisconnectGmeet = async () => {
    if (!confirm('Weet u zeker dat u Google Meet wilt ontkoppelen?')) return
    try {
      await calendarsApi.disconnectGmeet(calendar.id)
      toast.success('Google Meet ontkoppeld')
      onCancel()
    } catch {
      toast.error('Fout bij ontkoppelen Google Meet')
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
        <Input
          ref={durationRef}
          label="Standaard afspraakduur (minuten)"
          type="number"
          defaultValue={calendar.availability_rules?.default_appointment_duration_minutes || 30}
        />
        <Input
          ref={bufferRef}
          label="Buffer na afspraak (minuten)"
          type="number"
          defaultValue={calendar.availability_rules?.buffer_after_minutes || 15}
        />
        <Input
          ref={noticeRef}
          label="Minimale vooraanmelding (uren)"
          type="number"
          defaultValue={calendar.availability_rules?.min_notice_hours || 1}
        />
        <Input
          ref={advanceRef}
          label="Max. dagen vooruit boeken"
          type="number"
          defaultValue={calendar.availability_rules?.max_advance_days || 60}
        />
      </div>

      <div>
        <Select
          ref={meetRef}
          label="Vergaderlink toevoegen aan afspraken"
          defaultValue={calendar.meeting_link_provider || 'none'}
        >
          <option value="none">Geen</option>
          <option value="google_meet">Google Meet</option>
          <option value="zoom">Zoom</option>
          <option value="teams">Microsoft Teams</option>
        </Select>
        <p className="mt-1 text-xs text-gray-400">
          Voegt automatisch een vergaderlink toe aan nieuwe afspraken.
        </p>
      </div>

      {/* Meeting provider connections */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-gray-700">Vergaderproviders</p>

        {/* Google Meet */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-green-100">
                <Video className="h-4 w-4 text-green-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Google Meet</p>
                <p className="text-xs text-gray-500">
                  {isGoogleCalendar
                    ? (calendar.last_sync_at ? 'Gekoppeld via Google Calendar' : 'Koppel eerst Google Calendar')
                    : (calendar.gmeet_connected ? 'Google-account gekoppeld' : 'Niet gekoppeld')}
                </p>
              </div>
            </div>
            {isGoogleCalendar ? (
              calendar.last_sync_at && (
                <Badge variant="success">
                  <Check className="h-3 w-3 mr-1" />
                  Gereed
                </Badge>
              )
            ) : calendar.gmeet_connected ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDisconnectGmeet}
              >
                <Unlink className="h-4 w-4 text-red-500 mr-1" />
                Ontkoppelen
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={handleConnectGmeet}
                isLoading={connectingGmeet}
              >
                <Video className="h-4 w-4 mr-1" />
                Koppel Google
              </Button>
            )}
          </div>
        </div>

        {/* Zoom */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100">
                <Video className="h-4 w-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Zoom</p>
                <p className="text-xs text-gray-500">
                  {calendar.zoom_connected ? 'Account gekoppeld' : 'Niet gekoppeld'}
                </p>
              </div>
            </div>
            {calendar.zoom_connected ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDisconnectZoom}
              >
                <Unlink className="h-4 w-4 text-red-500 mr-1" />
                Ontkoppelen
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={handleConnectZoom}
                isLoading={connectingZoom}
              >
                <Video className="h-4 w-4 mr-1" />
                Koppel Zoom
              </Button>
            )}
          </div>
        </div>

        {/* Microsoft Teams */}
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-100">
                <Video className="h-4 w-4 text-purple-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Microsoft Teams</p>
                <p className="text-xs text-gray-500">
                  {calendar.teams_connected ? 'Account gekoppeld' : 'Niet gekoppeld'}
                </p>
              </div>
            </div>
            {calendar.teams_connected ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDisconnectTeams}
              >
                <Unlink className="h-4 w-4 text-red-500 mr-1" />
                Ontkoppelen
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={handleConnectTeams}
                isLoading={connectingTeams}
              >
                <Video className="h-4 w-4 mr-1" />
                Koppel Teams
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
        <Button variant="outline" onClick={onCancel}>
          Annuleren
        </Button>
        <Button onClick={handleSave} isLoading={isSaving}>
          Opslaan
        </Button>
      </div>
    </div>
  )
}

function CalendarPageInner() {
  const queryClient = useQueryClient()
  const searchParams = useSearchParams()
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)

  useEffect(() => {
    if (searchParams.get('connected') === 'true') {
      toast.success('Google Calendar succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      window.history.replaceState({}, '', '/dashboard/calendar')
    }
    if (searchParams.get('microsoft_connected') === 'true') {
      toast.success('Microsoft Outlook succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      window.history.replaceState({}, '', '/dashboard/calendar')
    }
    if (searchParams.get('zoom_connected') === 'true') {
      toast.success('Zoom succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      window.history.replaceState({}, '', '/dashboard/calendar')
    }
    if (searchParams.get('teams_connected') === 'true') {
      toast.success('Microsoft Teams succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      window.history.replaceState({}, '', '/dashboard/calendar')
    }
    if (searchParams.get('gmeet_connected') === 'true') {
      toast.success('Google Meet succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['calendars'] })
      window.history.replaceState({}, '', '/dashboard/calendar')
    }
  }, [searchParams, queryClient])
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
    if (!selectedWorkerId) {
      toast.error('Selecteer eerst een AI-medewerker')
      return
    }
    try {
      const providerInfo = providers.find((p) => p.id === provider)
      const calendar = await calendarsApi.create({
        name: providerInfo?.name || provider,
        provider,
        ai_worker_id: selectedWorkerId,
      })
      const response = await calendarsApi.getOAuthUrl(provider, calendar.id)
      window.location.href = response.auth_url
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Fout bij starten OAuth')
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
        hideSearch
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
                          <div className={`flex h-12 w-12 items-center justify-center rounded-lg overflow-hidden ${providerInfo.color}`}>
                            {providerInfo.logo ? (
                              <img src={providerInfo.logo} alt={providerInfo.name} className="h-8 w-8 object-contain" />
                            ) : (
                              <span className="text-2xl">{providerInfo.icon}</span>
                            )}
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
                          ) : calendar.last_sync_at ? (
                            <Badge variant="success">
                              <Check className="h-3 w-3 mr-1" />
                              Gekoppeld
                            </Badge>
                          ) : (
                            <Badge variant="warning">Niet verbonden</Badge>
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
                        {!calendar.last_sync_at && calendar.provider !== 'caldav' ? (
                          <Button
                            size="sm"
                            leftIcon={<ExternalLink className="h-4 w-4" />}
                            onClick={async () => {
                              try {
                                const res = await calendarsApi.getOAuthUrl(calendar.provider, calendar.id)
                                window.location.href = res.auth_url
                              } catch {
                                toast.error('Fout bij starten OAuth')
                              }
                            }}
                          >
                            {calendar.provider === 'microsoft' ? 'Verbind met Microsoft' : 'Verbind met Google'}
                          </Button>
                        ) : (
                          <>
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
                          </>
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
                    <div className={`flex h-12 w-12 items-center justify-center rounded-lg overflow-hidden ${provider.color}`}>
                      {provider.logo ? (
                        <img src={provider.logo} alt={provider.name} className="h-8 w-8 object-contain" />
                      ) : (
                        <span className="text-2xl">{provider.icon}</span>
                      )}
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
          <SettingsForm
            calendar={selectedCalendar}
            onSave={(data: any) => {
              updateMutation.mutate(
                { id: selectedCalendar.id, data },
                { onSuccess: () => setSelectedCalendar(null) },
              )
            }}
            onCancel={() => setSelectedCalendar(null)}
            isSaving={updateMutation.isPending}
          />
        )}
      </Modal>
    </DashboardLayout>
  )
}
