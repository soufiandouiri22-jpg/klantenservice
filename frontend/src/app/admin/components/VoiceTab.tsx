'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Mic, Save, RefreshCw, Volume2, Play, Square, Loader2, User, Sparkles } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'
import { useState, useEffect, useRef } from 'react'

// Voice type from backend
interface Voice {
  id: string
  name: string
  description: string
  gender: string
}

export function VoiceTab() {
  const queryClient = useQueryClient()

  // Fetch global configs
  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ['admin-global-configs'],
    queryFn: adminApi.getGlobalConfigs,
  })

  // Fetch available voices from backend
  const { data: voicesData, isLoading: voicesLoading } = useQuery({
    queryKey: ['admin-voices'],
    queryFn: adminApi.getVoices,
  })

  const [selectedVoice, setSelectedVoice] = useState<string>('alloy')

  // Voice preview state
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)
  const [playingVoice, setPlayingVoice] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  // Initialize selected voice from config
  useEffect(() => {
    if (configs?.voice) {
      const voiceConfig = configs.voice.find((c: any) => c.key === 'voice_default')
      if (voiceConfig) {
        setSelectedVoice(voiceConfig.value)
      }
    }
  }, [configs])

  const voices: Voice[] = voicesData?.voices || []

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: any }) =>
      adminApi.updateGlobalConfig(key, { value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success('Stem opgeslagen')
    },
    onError: () => {
      toast.error('Kon stem niet opslaan')
    },
  })

  const seedMutation = useMutation({
    mutationFn: adminApi.seedGlobalConfigs,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success(`${data.created} nieuwe configs aangemaakt`)
    },
  })

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
      }
      if (audioRef.current) {
        audioRef.current.pause()
      }
    }
  }, [])

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
    // Stop current playback
    stopPlayback()

    // If clicking the same voice, just stop
    if (playingVoice === voiceId) {
      return
    }

    setPreviewLoading(voiceId)

    try {
      const blob = await adminApi.getVoicePreview(voiceId)
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
    } catch (error: any) {
      console.error('Voice preview error:', error)
      if (error?.response?.status === 422) {
        toast('Deze stem werkt tijdens gesprekken, maar heeft geen preview', { icon: 'ℹ️' })
      } else {
        toast.error('Kon voice preview niet laden')
      }
    } finally {
      setPreviewLoading(null)
    }
  }

  const handleSave = () => {
    updateMutation.mutate({ key: 'voice_default', value: selectedVoice })
  }

  if (configsLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Voice Instellingen</h2>
          <p className="text-sm text-gray-500">
            Kies de standaard stem voor AI gesprekken. Powered by OpenAI Realtime API.
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

      {/* Voice Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            Standaard Stem
          </CardTitle>
          <CardDescription>
            Kies de stem die platform-wide gebruikt wordt voor alle AI medewerkers
            (tenzij een medewerker een eigen stem heeft ingesteld).
          </CardDescription>
        </CardHeader>
        <CardBody>
          {voicesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Spinner size="sm" />
              <span className="ml-2 text-sm text-gray-500">Stemmen laden...</span>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Voice Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {voices.map((voice) => (
                  <div
                    key={voice.id}
                    onClick={() => setSelectedVoice(voice.id)}
                    className={`relative flex flex-col p-4 rounded-xl border-2 cursor-pointer transition-all ${
                      selectedVoice === voice.id
                        ? 'border-primary-500 bg-primary-50 shadow-sm'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {/* Selected indicator */}
                    {selectedVoice === voice.id && (
                      <div className="absolute top-2 right-2">
                        <Sparkles className="h-4 w-4 text-primary-500" />
                      </div>
                    )}

                    {/* Voice info */}
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`flex items-center justify-center h-8 w-8 rounded-full ${
                        selectedVoice === voice.id ? 'bg-primary-100' : 'bg-gray-100'
                      }`}>
                        <Mic className={`h-4 w-4 ${
                          selectedVoice === voice.id ? 'text-primary-600' : 'text-gray-500'
                        }`} />
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-gray-900">{voice.name}</span>
                        <span className="ml-1.5 text-xs text-gray-400">
                          {voice.gender === 'male' ? '♂' : voice.gender === 'female' ? '♀' : '◎'}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-gray-500 mb-3">{voice.description}</p>

                    {/* Play button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        playVoiceSample(voice.id)
                      }}
                      disabled={previewLoading !== null}
                      className={`flex items-center justify-center gap-1.5 w-full py-2 rounded-lg text-xs font-medium transition-all ${
                        playingVoice === voice.id
                          ? 'bg-red-50 text-red-600 border border-red-200'
                          : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50 hover:text-gray-900'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {previewLoading === voice.id ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Laden...
                        </>
                      ) : playingVoice === voice.id ? (
                        <>
                          <Square className="h-3.5 w-3.5" />
                          Stop
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5" />
                          Beluister
                        </>
                      )}
                    </button>
                  </div>
                ))}
              </div>

              {/* Currently selected */}
              <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">Geselecteerd:</span>
                  <span className="text-sm font-semibold text-primary-600 capitalize">{selectedVoice}</span>
                </div>
                <Button
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {updateMutation.isPending ? 'Opslaan...' : 'Opslaan'}
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Info card */}
      <Card>
        <CardBody>
          <div className="flex gap-3">
            <div className="flex-shrink-0 mt-0.5">
              <Sparkles className="h-5 w-5 text-primary-500" />
            </div>
            <div className="text-sm text-gray-600">
              <p className="font-medium text-gray-900 mb-1">OpenAI gpt-realtime</p>
              <p>
                Alle stemmen ondersteunen Nederlands en zijn full-duplex:
                de AI kan luisteren terwijl het spreekt en stopt automatisch als de beller
                iets zegt (barge-in). Geen vertraging bij het starten van een gesprek.
                Sommige stemmen hebben geen preview maar werken wel tijdens gesprekken.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
