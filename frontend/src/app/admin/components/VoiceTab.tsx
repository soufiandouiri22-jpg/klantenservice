'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Mic, Save, RefreshCw, Volume2, ToggleLeft } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'
import { useState, useEffect } from 'react'

// Pod URL for fetching available voices
const POD_URL = process.env.NEXT_PUBLIC_PERSONAPLEX_POD_URL || ''

export function VoiceTab() {
  const queryClient = useQueryClient()
  
  const { data: configs, isLoading } = useQuery({
    queryKey: ['admin-global-configs'],
    queryFn: adminApi.getGlobalConfigs,
  })

  const [values, setValues] = useState<Record<string, any>>({})
  
  // State for available voices from pod
  const [availableVoices, setAvailableVoices] = useState<string[]>(['NATF0', 'NATF1', 'NATF2', 'NATF3', 'NATF4', 'NATF5'])
  const [voicesLoading, setVoicesLoading] = useState(false)

  // Fetch available voices from pod
  useEffect(() => {
    const fetchVoices = async () => {
      if (!POD_URL) {
        console.warn('NEXT_PUBLIC_PERSONAPLEX_POD_URL not set, using default voices')
        return
      }
      
      setVoicesLoading(true)
      try {
        const response = await fetch(`${POD_URL}/voices`)
        if (response.ok) {
          const data = await response.json()
          if (data.voices && data.voices.length > 0) {
            setAvailableVoices(data.voices)
          }
        }
      } catch (e) {
        console.warn('Could not fetch voices from pod, using defaults:', e)
      } finally {
        setVoicesLoading(false)
      }
    }
    fetchVoices()
  }, [])

  useEffect(() => {
    if (configs?.voice) {
      const initial: Record<string, any> = {}
      configs.voice.forEach((c: any) => {
        initial[c.key] = c.value
      })
      setValues(initial)
    }
  }, [configs])

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: any }) =>
      adminApi.updateGlobalConfig(key, { value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success('Instelling opgeslagen')
    },
    onError: () => {
      toast.error('Kon instelling niet opslaan')
    },
  })

  const seedMutation = useMutation({
    mutationFn: adminApi.seedGlobalConfigs,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success(`${data.created} nieuwe configs aangemaakt`)
    },
  })

  const handleSave = (key: string) => {
    updateMutation.mutate({ key, value: values[key] })
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  const voiceConfigs = configs?.voice || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Realtime Voice Tuning</h2>
          <p className="text-sm text-gray-500">
            Configureer audio processing voor een natuurlijk gesprek.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => seedMutation.mutate()}
          disabled={seedMutation.isPending}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
          Standaard configs laden
        </Button>
      </div>

      {voiceConfigs.length === 0 ? (
        <Card>
          <CardBody className="text-center py-12">
            <Mic className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Geen configuraties</h3>
            <p className="text-gray-500 mb-4">
              Laad de standaard configuraties om te beginnen.
            </p>
            <Button onClick={() => seedMutation.mutate()} disabled={seedMutation.isPending}>
              Configs laden
            </Button>
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Voice Preset - ADMIN ONLY */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Volume2 className="h-5 w-5" />
                Voice Preset
              </CardTitle>
              <CardDescription>
                PersonaPlex stem voor alle gesprekken platform-wide.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                {voicesLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Spinner size="sm" />
                    <span className="ml-2 text-sm text-gray-500">Voices laden...</span>
                  </div>
                ) : (
                  <select
                    value={values['voice_default_preset'] || 'NATF0'}
                    onChange={(e) => setValues({ ...values, voice_default_preset: e.target.value })}
                    className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                  >
                    {availableVoices.map((voice) => (
                      <option key={voice} value={voice}>{voice}</option>
                    ))}
                  </select>
                )}
                <p className="text-xs text-gray-500">
                  Voice IDs worden opgehaald van de PersonaPlex pod. 
                  Kies de stem die voor alle AI gesprekken gebruikt wordt.
                </p>
                <Button
                  onClick={() => handleSave('voice_default_preset')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Auto-Respond Toggle - ADMIN ONLY */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ToggleLeft className="h-5 w-5" />
                Automatic Respond
              </CardTitle>
              <CardDescription>
                VAD turn detection: automatisch detecteren wanneer beller klaar is.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <span className="text-sm font-medium text-gray-900">Auto-respond</span>
                    <p className="text-xs text-gray-500 mt-1">
                      {values['voice_auto_respond'] !== false 
                        ? 'AI detecteert automatisch einde van spraak' 
                        : 'AI wacht op expliciete trigger'}
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={values['voice_auto_respond'] !== false}
                    onClick={() => setValues({ ...values, voice_auto_respond: values['voice_auto_respond'] === false })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      values['voice_auto_respond'] !== false ? 'bg-primary-600' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm ${
                        values['voice_auto_respond'] !== false ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
                <p className="text-xs text-gray-500">
                  Aan: Voice Activity Detection actief - AI begint automatisch met antwoorden na stilte.
                  Uit: Handmatige controle vereist.
                </p>
                <Button
                  onClick={() => handleSave('voice_auto_respond')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Segment Duration */}
          <Card>
            <CardHeader>
              <CardTitle>Audio Segment Lengte</CardTitle>
              <CardDescription>
                Hoe lang audio wordt gebufferd voordat het wordt verwerkt.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <Input
                    type="range"
                    min="1000"
                    max="5000"
                    step="100"
                    value={values['voice_segment_ms'] || 2500}
                    onChange={(e) => setValues({ ...values, voice_segment_ms: parseInt(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>1s (snel)</span>
                    <span className="font-medium text-primary-600">
                      {(values['voice_segment_ms'] || 2500) / 1000}s
                    </span>
                    <span>5s (kwaliteit)</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Kortere segmenten = snellere response, langere = betere context.
                  Aanbevolen: 2-3 seconden.
                </p>
                <Button
                  onClick={() => handleSave('voice_segment_ms')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* VAD Sensitivity */}
          <Card>
            <CardHeader>
              <CardTitle>VAD Gevoeligheid</CardTitle>
              <CardDescription>
                Voice Activity Detection - detecteert wanneer iemand spreekt.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <Input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={values['voice_vad_sensitivity'] || 0.5}
                    onChange={(e) => setValues({ ...values, voice_vad_sensitivity: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>Laag (minder detectie)</span>
                    <span className="font-medium text-primary-600">
                      {values['voice_vad_sensitivity'] || 0.5}
                    </span>
                    <span>Hoog (meer detectie)</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Te hoog: achtergrondgeluid wordt als spraak gezien.
                  Te laag: zachte spraak wordt gemist.
                </p>
                <Button
                  onClick={() => handleSave('voice_vad_sensitivity')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Interrupt Policy */}
          <Card>
            <CardHeader>
              <CardTitle>Interrupt Policy</CardTitle>
              <CardDescription>
                Wat gebeurt er als de beller de AI onderbreekt?
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <select
                  value={values['voice_interrupt_policy'] || 'allow'}
                  onChange={(e) => setValues({ ...values, voice_interrupt_policy: e.target.value })}
                  className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                >
                  <option value="allow">Toestaan - AI stopt meteen</option>
                  <option value="queue">Queue - AI maakt zin af</option>
                  <option value="ignore">Negeren - AI praat door</option>
                </select>
                <p className="text-xs text-gray-500">
                  "Toestaan" is het meest natuurlijk maar kan abrupt klinken.
                  "Queue" is een goede balans.
                </p>
                <Button
                  onClick={() => handleSave('voice_interrupt_policy')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Latency Budget */}
          <Card>
            <CardHeader>
              <CardTitle>Max Latency Budget</CardTitle>
              <CardDescription>
                Maximum tijd voordat de AI moet beginnen met antwoorden.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Input
                  label="Maximum latency (ms)"
                  type="number"
                  min="1000"
                  max="10000"
                  step="500"
                  value={values['voice_max_latency_ms'] || 3000}
                  onChange={(e) => setValues({ ...values, voice_max_latency_ms: parseInt(e.target.value) })}
                  helperText="Aanbevolen: 2000-3000ms voor natuurlijke conversatie"
                />
                <Input
                  label="Queue max size"
                  type="number"
                  min="1"
                  max="20"
                  value={values['voice_queue_max_size'] || 5}
                  onChange={(e) => setValues({ ...values, voice_queue_max_size: parseInt(e.target.value) })}
                  helperText="Max aantal audio chunks in de queue (backpressure)"
                />
                <Button
                  onClick={() => {
                    handleSave('voice_max_latency_ms')
                    handleSave('voice_queue_max_size')
                  }}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}
