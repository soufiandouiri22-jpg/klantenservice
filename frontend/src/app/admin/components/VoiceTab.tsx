'use client'

import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Mic, Volume2, Play, Square, Loader2, Sparkles } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'
import { useState, useEffect, useRef } from 'react'

interface Voice {
  id: string
  name: string
  description: string
  gender: string
}

export function VoiceTab() {
  const { data: voicesData, isLoading: voicesLoading } = useQuery({
    queryKey: ['admin-voices'],
    queryFn: adminApi.getVoices,
  })

  // Voice preview state
  const [previewLoading, setPreviewLoading] = useState<string | null>(null)
  const [playingVoice, setPlayingVoice] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  const voices: Voice[] = voicesData?.voices || []

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
    stopPlayback()

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Voice Preview</h2>
        <p className="text-sm text-gray-500">
          Beluister alle beschikbare stemmen. Klanten kiezen hun stem bij hun AI-medewerker.
        </p>
      </div>

      {/* Voice Grid */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5" />
            Beschikbare Stemmen
          </CardTitle>
          <CardDescription>
            Alle OpenAI Realtime stemmen. Sommige stemmen hebben geen preview maar werken wel tijdens gesprekken.
          </CardDescription>
        </CardHeader>
        <CardBody>
          {voicesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Spinner size="sm" />
              <span className="ml-2 text-sm text-gray-500">Stemmen laden...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {voices.map((voice) => (
                <div
                  key={voice.id}
                  className="flex flex-col p-4 rounded-xl border-2 border-gray-200"
                >
                  {/* Voice info */}
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex items-center justify-center h-8 w-8 rounded-full bg-gray-100">
                      <Mic className="h-4 w-4 text-gray-500" />
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-gray-900">{voice.name}</span>
                      <span className="ml-1.5 text-xs text-gray-400">
                        {voice.gender === 'male' ? '♂' : voice.gender === 'female' ? '♀' : '◎'}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-gray-500 mb-3 flex-1">{voice.description}</p>

                  {/* Play button */}
                  <button
                    onClick={() => playVoiceSample(voice.id)}
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
                iets zegt (barge-in). Sommige stemmen hebben geen preview maar werken wel tijdens gesprekken.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
