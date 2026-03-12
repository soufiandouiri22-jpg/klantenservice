'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { useConversation } from '@elevenlabs/react'
import { Play, PhoneOff, Mic, MicOff, Loader2 } from 'lucide-react'
import { demoApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

type Phase = 'idle' | 'connecting' | 'active'

export function DemoCallWidget() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [workerName, setWorkerName] = useState('')
  const [micMuted, setMicMuted] = useState(false)
  const callLogIdRef = useRef<string | null>(null)
  const ringbackRef = useRef<HTMLAudioElement | null>(null)

  const conversation = useConversation({
    micMuted,
    onConnect: () => setPhase('active'),
    onDisconnect: () => {
      if (callLogIdRef.current) {
        demoApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      setPhase('idle')
    },
    onError: (error: any) => {
      console.error('Demo call error:', error)
      toast.error('Verbinding verbroken. Probeer het opnieuw.')
      if (ringbackRef.current) { ringbackRef.current.pause(); ringbackRef.current = null }
      if (callLogIdRef.current) {
        demoApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      setPhase('idle')
    },
  } as any)

  const startCall = useCallback(async () => {
    try {
      setPhase('connecting')

      await navigator.mediaDevices.getUserMedia({ audio: true })

      // Play ringback tone to warm up audio pipeline + give natural "ringing" UX
      const ringback = new Audio('/sounds/ringback.mp3')
      ringbackRef.current = ringback
      ringback.play().catch(() => {})
      await new Promise(resolve => setTimeout(resolve, 4000))
      ringback.pause()
      ringbackRef.current = null

      const data = await demoApi.getSignedUrl()
      setWorkerName(data.worker_name)
      callLogIdRef.current = data.call_log_id

      await conversation.startSession({
        signedUrl: data.signed_url,
        overrides: data.overrides,
        dynamicVariables: data.dynamic_variables,
      })
    } catch (err: any) {
      console.error('Failed to start demo call:', err)
      if (ringbackRef.current) { ringbackRef.current.pause(); ringbackRef.current = null }
      if (callLogIdRef.current) {
        demoApi.endCall(callLogIdRef.current).catch(() => {})
        callLogIdRef.current = null
      }
      if (err?.name === 'NotAllowedError') {
        toast.error('Microfoon is geblokkeerd. Sta toegang toe in je browser.')
      } else if (err?.response?.status === 429) {
        toast.error('Te veel verzoeken. Probeer het later opnieuw.')
      } else {
        toast.error('Kon demo niet starten. Probeer het later opnieuw.')
      }
      setPhase('idle')
    }
  }, [conversation])

  const endCall = useCallback(async () => {
    await conversation.endSession()
    setPhase('idle')
  }, [conversation])

  useEffect(() => {
    return () => {
      if (ringbackRef.current) { ringbackRef.current.pause(); ringbackRef.current = null }
      if (callLogIdRef.current) {
        demoApi.endCall(callLogIdRef.current).catch(() => {})
      }
    }
  }, [])

  // Idle state: show play button
  if (phase === 'idle') {
    return (
      <>
        <button
          onClick={startCall}
          className="relative z-10 flex items-center justify-center w-20 h-20 bg-primary-600 rounded-full shadow-lg shadow-primary-600/50 hover:bg-primary-500 hover:scale-105 transition-all group"
        >
          <Play className="h-8 w-8 text-white ml-1" fill="currentColor" />
        </button>
        <div className="absolute w-20 h-20 rounded-full border-2 border-primary-400 animate-ping opacity-20" />
      </>
    )
  }

  // Connecting state
  if (phase === 'connecting') {
    return (
      <div className="relative z-10 flex flex-col items-center gap-3">
        <div className="flex items-center justify-center w-20 h-20 bg-primary-600 rounded-full shadow-lg shadow-primary-600/50">
          <Loader2 className="h-8 w-8 text-white animate-spin" />
        </div>
        <span className="text-sm text-white/80">Verbinden...</span>
      </div>
    )
  }

  // Active call
  return (
    <div className="relative z-10 flex flex-col items-center gap-2 sm:gap-4">
      {/* Speaking indicator */}
      <div className="relative flex items-center justify-center w-16 h-16 sm:w-24 sm:h-24">
        <div className={cn(
          'absolute inset-0 rounded-full bg-primary-400/30 transition-transform duration-300',
          conversation.isSpeaking ? 'scale-125 animate-pulse' : 'scale-100'
        )} />
        <div className={cn(
          'absolute inset-2 rounded-full bg-primary-400/20 transition-transform duration-500',
          conversation.isSpeaking ? 'scale-110 animate-pulse' : 'scale-100'
        )} />
        <div className="relative bg-primary-600 rounded-full p-3 sm:p-5">
          <Mic className="h-5 w-5 sm:h-7 sm:w-7 text-white" />
        </div>
      </div>

      <p className="text-xs sm:text-sm text-white/90 font-medium">
        {conversation.isSpeaking ? `${workerName} spreekt...` : 'Luistert...'}
      </p>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setMicMuted(!micMuted)}
          className={cn(
            'rounded-full p-2.5 sm:p-3 transition-colors backdrop-blur-sm',
            micMuted
              ? 'bg-red-500/80 text-white hover:bg-red-500'
              : 'bg-white/10 text-white hover:bg-white/20'
          )}
        >
          {micMuted ? <MicOff className="h-4 w-4 sm:h-5 sm:w-5" /> : <Mic className="h-4 w-4 sm:h-5 sm:w-5" />}
        </button>
        <button
          onClick={endCall}
          className="rounded-full p-2.5 sm:p-3 bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          <PhoneOff className="h-4 w-4 sm:h-5 sm:w-5" />
        </button>
      </div>

      <p className="hidden sm:block text-xs text-white/50 max-w-xs text-center">
        Spreek live met onze AI-telefonist. Vraag naar onze diensten of plan een demo in.
      </p>
    </div>
  )
}
