'use client'

import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Headphones, Settings, Trash2, Mic, Play, Square, Loader2, Sparkles, Phone, Globe, Calendar } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { aiWorkersApi } from '@/lib/api'
import { getStatusLabel, getStatusColor } from '@/lib/utils'
import { useAuthStore } from '@/lib/store'

interface Voice {
  id: string
  name: string
  description: string
  gender: string
}

export default function AIWorkersPage() {
  const queryClient = useQueryClient()
  const { company } = useAuthStore()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [selectedWorker, setSelectedWorker] = useState<any>(null)
  const [newWorkerName, setNewWorkerName] = useState('')
  const [newWorkerRole, setNewWorkerRole] = useState('Klantenservice medewerker')

  // Voice preview state
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)
  const [playingVoice, setPlayingVoice] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  const { data: workers, isLoading } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  // Fetch voices for the settings modal
  const { data: voicesData } = useQuery({
    queryKey: ['worker-voices'],
    queryFn: aiWorkersApi.getVoices,
    enabled: !!selectedWorker,
  })

  const voices: Voice[] = voicesData?.voices || []

  const createMutation = useMutation({
    mutationFn: aiWorkersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('AI-medewerker aangemaakt')
      setIsCreateModalOpen(false)
      setNewWorkerName('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij aanmaken')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: aiWorkersApi.toggleStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('Status bijgewerkt')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij bijwerken status')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: aiWorkersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('AI-medewerker verwijderd')
      setSelectedWorker(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij verwijderen')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => aiWorkersApi.update(id, data),
    onSuccess: (updatedWorker) => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      setSelectedWorker(updatedWorker)
      toast.success('Instellingen opgeslagen')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij opslaan')
    },
  })

  // Cleanup audio on unmount or modal close
  useEffect(() => {
    return () => {
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current)
      if (audioRef.current) audioRef.current.pause()
    }
  }, [])

  // Stop playback when modal closes
  useEffect(() => {
    if (!selectedWorker) {
      stopPlayback()
    }
  }, [selectedWorker])

  const stopPlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current)
      blobUrlRef.current = null
    }
    setPlayingVoice(null)
  }

  const playVoiceSample = async (voiceId: string) => {
    stopPlayback()
    if (playingVoice === voiceId) return

    setPreviewLoading(voiceId)
    try {
      const blob = await aiWorkersApi.getVoicePreview(voiceId)
      const url = URL.createObjectURL(blob)
      blobUrlRef.current = url

      const audio = new Audio(url)
      audioRef.current = audio

      audio.onended = () => {
        setPlayingVoice(null)
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current)
          blobUrlRef.current = null
        }
      }
      audio.onerror = () => {
        toast.error('Kon audio niet afspelen')
        setPlayingVoice(null)
      }

      await audio.play()
      setPlayingVoice(voiceId)
    } catch {
      toast.error('Kon voice preview niet laden')
    } finally {
      setPreviewLoading(null)
    }
  }

  const handleSettingChange = (field: string, value: any) => {
    if (!selectedWorker) return
    
    if (field.startsWith('behavior_settings.')) {
      const settingKey = field.replace('behavior_settings.', '')
      const newBehaviorSettings = {
        ...selectedWorker.behavior_settings,
        [settingKey]: value,
      }
      updateMutation.mutate({
        id: selectedWorker.id,
        data: { behavior_settings: newBehaviorSettings },
      })
    } else {
      updateMutation.mutate({
        id: selectedWorker.id,
        data: { [field]: value },
      })
    }
  }

  const handleCreate = () => {
    if (!newWorkerName.trim()) {
      toast.error('Voer een naam in')
      return
    }
    createMutation.mutate({
      name: newWorkerName,
      role_title: newWorkerRole,
    })
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const canAddWorker = workers?.length < (company?.max_ai_workers || 1)

  return (
    <DashboardLayout>
      <Header
        title="AI-medewerkers"
        description={`${workers?.length || 0} van ${company?.max_ai_workers || 1} medewerkers actief`}
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsCreateModalOpen(true)}
            disabled={!canAddWorker}
          >
            Nieuwe medewerker
          </Button>
        }
      />

      <div className="p-6">
        {workers?.length === 0 ? (
          <EmptyState
            icon={Headphones}
            title="Geen AI-medewerkers"
            description="Maak uw eerste AI-medewerker aan om gesprekken te kunnen voeren."
            action={
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsCreateModalOpen(true)}>
                Eerste medewerker aanmaken
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workers?.map((worker: any, index: number) => (
              <motion.div
                key={worker.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="hover:shadow-soft-lg transition-shadow">
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-100">
                          <Headphones className="h-7 w-7 text-primary-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{worker.name}</h3>
                          <p className="text-sm text-gray-500">{worker.role_title}</p>
                        </div>
                      </div>
                      <Badge
                        variant={
                          worker.status === 'available' ? 'success' :
                          worker.status === 'busy' ? 'warning' : 'gray'
                        }
                      >
                        {getStatusLabel(worker.status)}
                      </Badge>
                    </div>

                    {/* Linked resources */}
                    <div className="mt-4 space-y-2">
                      <div className="flex items-center gap-2.5 text-sm">
                        <Phone className={`h-4 w-4 ${worker.linked_phone ? 'text-green-500' : 'text-gray-300'}`} />
                        <span className={worker.linked_phone ? 'text-gray-700' : 'text-gray-400'}>
                          {worker.linked_phone ? worker.linked_phone.number : 'Geen nummer gekoppeld'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-sm">
                        <Globe className={`h-4 w-4 ${worker.linked_website ? 'text-green-500' : 'text-gray-300'}`} />
                        <span className={`${worker.linked_website ? 'text-gray-700' : 'text-gray-400'} truncate`}>
                          {worker.linked_website ? worker.linked_website.base_url.replace(/^https?:\/\//, '') : 'Geen website gekoppeld'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2.5 text-sm">
                        <Calendar className={`h-4 w-4 ${worker.linked_calendar ? 'text-green-500' : 'text-gray-300'}`} />
                        <span className={worker.linked_calendar ? 'text-gray-700' : 'text-gray-400'}>
                          {worker.linked_calendar ? worker.linked_calendar.name : 'Geen agenda gekoppeld'}
                        </span>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="mt-4 grid grid-cols-2 gap-4 text-center">
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-2xl font-bold text-gray-900">{worker.total_calls_handled}</p>
                        <p className="text-xs text-gray-500">Gesprekken</p>
                      </div>
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-2xl font-bold text-gray-900">{worker.total_appointments_made}</p>
                        <p className="text-xs text-gray-500">Afspraken</p>
                      </div>
                    </div>

                    <div className="mt-4 flex items-center justify-between pt-4 border-t border-gray-100">
                      <Toggle
                        enabled={worker.is_active}
                        onChange={() => toggleMutation.mutate(worker.id)}
                        label={worker.is_active ? 'Actief' : 'Inactief'}
                      />
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<Settings className="h-4 w-4" />}
                          onClick={() => setSelectedWorker(worker)}
                        >
                          Instellingen
                        </Button>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {!canAddWorker && workers?.length > 0 && (
          <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-4">
            <p className="text-sm text-amber-800">
              U heeft het maximum aantal AI-medewerkers voor uw abonnement bereikt. 
              <a href="/dashboard/settings?tab=subscription" className="font-medium underline ml-1">
                Upgrade uw abonnement
              </a>
              {' '}voor meer medewerkers.
            </p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nieuwe AI-medewerker"
        description="Geef uw nieuwe AI-medewerker een naam en rol."
      >
        <div className="space-y-4">
          <Input
            label="Naam"
            placeholder="bijv. Anna"
            value={newWorkerName}
            onChange={(e) => setNewWorkerName(e.target.value)}
          />
          <Input
            label="Rol / Functie"
            placeholder="bijv. Klantenservice medewerker"
            value={newWorkerRole}
            onChange={(e) => setNewWorkerRole(e.target.value)}
          />
          <div className="flex gap-3 pt-4">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Annuleren
            </Button>
            <Button
              className="flex-1"
              onClick={handleCreate}
              isLoading={createMutation.isPending}
            >
              Aanmaken
            </Button>
          </div>
        </div>
      </Modal>

      {/* Settings Modal */}
      <Modal
        isOpen={!!selectedWorker}
        onClose={() => setSelectedWorker(null)}
        title={`Instellingen: ${selectedWorker?.name}`}
        size="lg"
      >
        {selectedWorker && (
          <div className="space-y-6">
            {/* Voice Selection */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-900">Stem</h4>
              <p className="text-sm text-gray-500">Kies de stem voor deze AI-medewerker.</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {voices.map((voice) => (
                  <div
                    key={voice.id}
                    onClick={() => handleSettingChange('voice_id', voice.id)}
                    className={`relative flex flex-col p-3 rounded-xl border-2 cursor-pointer transition-all ${
                      selectedWorker.voice_id === voice.id
                        ? 'border-primary-500 bg-primary-50 shadow-sm'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {/* Selected indicator */}
                    {selectedWorker.voice_id === voice.id && (
                      <div className="absolute top-2 right-2">
                        <Sparkles className="h-4 w-4 text-primary-500" />
                      </div>
                    )}

                    {/* Voice info */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className={`flex items-center justify-center h-7 w-7 rounded-full ${
                        selectedWorker.voice_id === voice.id ? 'bg-primary-100' : 'bg-gray-100'
                      }`}>
                        <Mic className={`h-3.5 w-3.5 ${
                          selectedWorker.voice_id === voice.id ? 'text-primary-600' : 'text-gray-500'
                        }`} />
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-gray-900">{voice.name}</span>
                      </div>
                    </div>

                    <p className="text-xs text-gray-500 mb-2 flex-1">{voice.description}</p>

                    {/* Play button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        playVoiceSample(voice.id)
                      }}
                      disabled={previewLoading !== null}
                      className={`flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg text-xs font-medium transition-all ${
                        playingVoice === voice.id
                          ? 'bg-red-50 text-red-600 border border-red-200'
                          : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50 hover:text-gray-900'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {previewLoading === voice.id ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Laden...
                        </>
                      ) : playingVoice === voice.id ? (
                        <>
                          <Square className="h-3 w-3" />
                          Stop
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Beluister
                        </>
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Behavior Settings */}
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Gedragsinstellingen</h4>
              <Toggle
                enabled={selectedWorker.behavior_settings?.apologize_on_complaints ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.apologize_on_complaints', value)}
                label="Excuses bij klachten"
                description="Bied automatisch excuses aan bij klachten"
              />
              <Toggle
                enabled={selectedWorker.behavior_settings?.always_offer_alternatives ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.always_offer_alternatives', value)}
                label="Altijd alternatieven aanbieden"
                description="Bied een alternatief aan als iets niet mogelijk is"
              />
              <Toggle
                enabled={selectedWorker.behavior_settings?.never_guess ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.never_guess', value)}
                label="Nooit gokken"
                description="Geef alleen antwoord als de AI zeker is"
              />
            </div>

            {/* Permissions */}
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Rechten</h4>
              <Toggle
                enabled={selectedWorker.can_make_appointments}
                onChange={(value) => handleSettingChange('can_make_appointments', value)}
                label="Afspraken maken"
                description="Mag afspraken inplannen in de agenda"
              />
              <Toggle
                enabled={selectedWorker.can_cancel_appointments}
                onChange={(value) => handleSettingChange('can_cancel_appointments', value)}
                label="Afspraken annuleren"
                description="Mag bestaande afspraken annuleren"
              />
              <Toggle
                enabled={selectedWorker.can_leave_notes}
                onChange={(value) => handleSettingChange('can_leave_notes', value)}
                label="Notities achterlaten"
                description="Mag interne notities maken"
              />
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => {
                  if (confirm('Weet u zeker dat u deze medewerker wilt verwijderen?')) {
                    deleteMutation.mutate(selectedWorker.id)
                  }
                }}
              >
                Verwijderen
              </Button>
              <Button onClick={() => setSelectedWorker(null)}>
                Sluiten
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
