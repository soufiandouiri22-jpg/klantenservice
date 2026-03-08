'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useConversation } from '@elevenlabs/react'
import { useQuery } from '@tanstack/react-query'
import { Phone, PhoneOff, Mic, MicOff, X, Loader2 } from 'lucide-react'
import { testCallApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

type Phase = 'idle' | 'connecting' | 'active'

export function TestCallWidget() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [workerName, setWorkerName] = useState('')
  const [micMuted, setMicMuted] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const callLogIdRef = useRef<string | null>(null)
  const firstMessageRef = useRef<string>('')

  const { data: checkData } = useQuery({
    queryKey: ['test-call-check'],
    queryFn: testCallApi.check,
    staleTime: 60_000,
  })

  const conversation = useConversation({
    micMuted,
    onConnect: () => setPhase('active'),
    onDisconnect: () => {
      if (callLogIdRef.current) {
        testCallApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      setPhase('idle')
      setExpanded(false)
    },
    onError: (error: any) => {
      console.error('Test call error:', error)
      toast.error('Verbinding verbroken. Probeer het opnieuw.')
      if (callLogIdRef.current) {
        testCallApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      setPhase('idle')
    },
  } as any)

  const startCall = useCallback(async () => {
    try {
      setPhase('connecting')
      setExpanded(true)

      await navigator.mediaDevices.getUserMedia({ audio: true })

      const data = await testCallApi.getSignedUrl()
      setWorkerName(data.worker_name)
      callLogIdRef.current = data.call_log_id
      firstMessageRef.current = data.first_message || ''

      await conversation.startSession({
        signedUrl: data.signed_url,
        overrides: data.overrides,
        dynamicVariables: data.dynamic_variables,
      })

      if (firstMessageRef.current) {
        conversation.sendContextualUpdate(
          `Begroet de beller met exact deze tekst: "${firstMessageRef.current}"`
        )
      }
    } catch (err: any) {
      console.error('Failed to start test call:', err)
      if (callLogIdRef.current) {
        testCallApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      if (err?.name === 'NotAllowedError') {
        toast.error('Microfoon is geblokkeerd. Sta toegang toe in je browser.')
      } else if (err?.response?.data?.detail) {
        toast.error(err.response.data.detail)
      } else {
        toast.error('Kon testgesprek niet starten.')
      }
      setPhase('idle')
      setExpanded(false)
    }
  }, [conversation])

  const endCall = useCallback(async () => {
    await conversation.endSession()
    setPhase('idle')
    setExpanded(false)
  }, [conversation])

  useEffect(() => {
    return () => {
      if (callLogIdRef.current) {
        testCallApi.endCall(callLogIdRef.current).catch(() => {})
      }
    }
  }, [])

  const hasWorker = checkData?.available ?? false

  if (!expanded) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        {!hasWorker && phase === 'idle' ? (
          <div className="relative group">
            <button
              disabled
              className="flex items-center gap-2 rounded-full px-5 py-3 text-sm font-medium text-white bg-gray-300 cursor-not-allowed shadow-lg"
            >
              <Phone className="h-4 w-4" />
              Test uw AI
            </button>
            <div className="absolute right-0 bottom-full mb-2 w-56 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all pointer-events-none">
              Maak eerst een AI-medewerker aan om te kunnen testen.
              <div className="absolute right-6 top-full w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-900" />
            </div>
          </div>
        ) : (
          <button
            onClick={startCall}
            disabled={phase === 'connecting'}
            className={cn(
              'flex items-center gap-2 rounded-full px-5 py-3 text-sm font-medium text-white shadow-lg transition-all hover:scale-105 active:scale-95',
              phase === 'connecting'
                ? 'bg-gray-400 cursor-wait'
                : 'bg-primary-600 hover:bg-primary-700'
            )}
          >
            {phase === 'connecting' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Phone className="h-4 w-4" />
            )}
            {phase === 'connecting' ? 'Verbinden...' : 'Test uw AI'}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-72 rounded-2xl bg-white shadow-2xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-primary-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <div className={cn(
            'h-2 w-2 rounded-full',
            phase === 'active' ? 'bg-green-400 animate-pulse' : 'bg-yellow-400 animate-pulse'
          )} />
          <span className="text-sm font-medium">
            {phase === 'connecting' ? 'Verbinden...' : `Gesprek met ${workerName}`}
          </span>
        </div>
        <button
          onClick={endCall}
          className="text-white/80 hover:text-white transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="p-4">
        {phase === 'connecting' && (
          <div className="flex flex-col items-center py-4 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            <p className="text-sm text-gray-500">Microfoon activeren...</p>
          </div>
        )}

        {phase === 'active' && (
          <div className="flex flex-col items-center gap-4">
            {/* Voice visualizer */}
            <div className="relative flex items-center justify-center w-20 h-20">
              <div className={cn(
                'absolute inset-0 rounded-full bg-primary-100 transition-transform duration-300',
                conversation.isSpeaking ? 'scale-110 animate-pulse' : 'scale-100'
              )} />
              <div className="relative bg-primary-600 rounded-full p-4">
                <Phone className="h-6 w-6 text-white" />
              </div>
            </div>

            <p className="text-xs text-gray-500">
              {conversation.isSpeaking ? `${workerName} spreekt...` : 'Luistert...'}
            </p>

            {/* Controls */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMicMuted(!micMuted)}
                className={cn(
                  'rounded-full p-3 transition-colors',
                  micMuted
                    ? 'bg-red-100 text-red-600 hover:bg-red-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {micMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
              </button>
              <button
                onClick={endCall}
                className="rounded-full p-3 bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                <PhoneOff className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer hint */}
      <div className="px-4 pb-3">
        <p className="text-[10px] text-gray-400 text-center">
          Dit is een testgesprek. Notities en afspraken worden opgeslagen.
        </p>
      </div>
    </div>
  )
}
