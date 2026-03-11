'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  FileText, 
  Clock, 
  User,
  Bot,
  Wrench,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Phone
} from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

interface RecentCall {
  id: string
  company_name: string
  caller_number: string
  called_number: string
  status: string
  outcome: string | null
  duration_seconds: number
  has_error: boolean
  created_at: string
}

interface ContextLog {
  turn_id: number
  user_transcript: string | null
  assistant_transcript: string | null
  detected_intent: string | null
  intent_confidence: number | null
  tool_calls: Array<{
    name: string
    arguments: Record<string, any>
    result: Record<string, any>
    latency_ms: number
  }>
  facts: string | null
  instructions: string | null
  model_used: string | null
  was_escalated: number
}

interface LatencyLog {
  turn_id: number
  stt_latency_ms: number | null
  orchestrator_latency_ms: number | null
  pod_latency_ms: number | null
  total_latency_ms: number | null
}

interface CallTrace {
  call_id: string
  company_name: string
  ai_worker_name: string | null
  caller_number: string
  called_number: string
  status: string
  outcome: string | null
  started_at: string
  ended_at: string | null
  duration_seconds: number
  transcripts: Array<{
    speaker: string
    message: string
    timestamp: string
  }>
  context_logs: ContextLog[]
  latency_logs: LatencyLog[]
  total_turns: number
  total_tool_calls: number
  error_message: string | null
  // Policy enrichment (from call_logs columns)
  hangup_reason?: string | null
  goodbye_handshake_ok?: boolean | null
  ended_by?: string | null
  policy_violations_count?: number
}

export function LogsTab() {
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [expandedTurns, setExpandedTurns] = useState<Set<number>>(new Set())

  const { data: recentCalls, isLoading: callsLoading } = useQuery({
    queryKey: ['admin-recent-calls'],
    queryFn: () => adminApi.getRecentCalls(50),
    refetchInterval: 30000,
  })

  const { data: callTrace, isLoading: traceLoading } = useQuery({
    queryKey: ['admin-call-trace', selectedCallId],
    queryFn: () => adminApi.getCallTrace(selectedCallId!),
    enabled: !!selectedCallId,
  })

  const toggleTurn = (turnId: number) => {
    const newExpanded = new Set(expandedTurns)
    if (newExpanded.has(turnId)) {
      newExpanded.delete(turnId)
    } else {
      newExpanded.add(turnId)
    }
    setExpandedTurns(newExpanded)
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleTimeString('nl-NL', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const calls: RecentCall[] = recentCalls?.calls || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Logs & Debug</h2>
        <p className="text-sm text-gray-500">
          Bekijk call traces, tool calls, en context payloads voor debugging.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Call List */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>Recente Calls</CardTitle>
              <CardDescription>Klik om details te bekijken</CardDescription>
            </CardHeader>
            <CardBody className="p-0 max-h-[600px] overflow-y-auto">
              {callsLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : calls.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <Phone className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                  <p>Geen recente calls</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {calls.map((call) => (
                    <button
                      key={call.id}
                      onClick={() => setSelectedCallId(call.id)}
                      className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                        selectedCallId === call.id ? 'bg-primary-50 border-l-2 border-primary-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900 text-sm truncate">
                          {call.company_name}
                        </span>
                        {call.has_error && (
                          <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                        <span>{call.caller_number}</span>
                        <span>·</span>
                        <span>{formatDuration(call.duration_seconds)}</span>
                        <span>·</span>
                        <span>{formatTime(call.created_at)}</span>
                      </div>
                      <div className="mt-2">
                        <Badge
                          variant={
                            call.status === 'completed' ? 'success' :
                            call.status === 'in_progress' ? 'primary' :
                            call.status === 'failed' ? 'danger' : 'gray'
                          }
                        >
                          {call.status}
                        </Badge>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Call Trace Detail */}
        <div className="lg:col-span-2">
          {!selectedCallId ? (
            <Card>
              <CardBody className="text-center py-12">
                <FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Selecteer een call</h3>
                <p className="text-gray-500">
                  Klik op een call in de lijst om de trace te bekijken.
                </p>
              </CardBody>
            </Card>
          ) : traceLoading ? (
            <div className="flex justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : callTrace ? (
            <div className="space-y-4">
              {/* Call Info */}
              <Card>
                <CardBody className="p-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500">Bedrijf</p>
                      <p className="font-medium">{callTrace.company_name}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">AI Worker</p>
                      <p className="font-medium">{callTrace.ai_worker_name || '-'}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Duur</p>
                      <p className="font-medium">{formatDuration(callTrace.duration_seconds)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Turns / Tool Calls</p>
                      <p className="font-medium">
                        {callTrace.total_turns} / {callTrace.total_tool_calls}
                      </p>
                    </div>
                  </div>
                  {/* Policy flags */}
                  {(callTrace.goodbye_handshake_ok === false ||
                    (callTrace.policy_violations_count || 0) > 0) && (
                    <div className="mt-4 flex gap-2 flex-wrap">
                      {callTrace.goodbye_handshake_ok === false && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-700 text-xs rounded-full">
                          <AlertTriangle className="h-3 w-3" /> Goodbye handshake mislukt
                        </span>
                      )}
                      {(callTrace.policy_violations_count || 0) > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-50 text-red-700 text-xs rounded-full">
                          <AlertTriangle className="h-3 w-3" /> {callTrace.policy_violations_count} policy violation(s)
                        </span>
                      )}
                      {callTrace.ended_by && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          Ended by: {callTrace.ended_by}
                        </span>
                      )}
                      {callTrace.hangup_reason && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                          Reason: {callTrace.hangup_reason}
                        </span>
                      )}
                    </div>
                  )}
                  {callTrace.error_message && (
                    <div className="mt-4 p-3 bg-red-50 rounded-lg text-sm text-red-700">
                      <strong>Error:</strong> {callTrace.error_message}
                    </div>
                  )}
                </CardBody>
              </Card>

              {/* Context Logs (per turn) */}
              <Card>
                <CardHeader>
                  <CardTitle>Conversation Trace</CardTitle>
                </CardHeader>
                <CardBody className="p-0">
                  {callTrace.context_logs.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      Geen context logs beschikbaar
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {callTrace.context_logs.map((log: ContextLog) => {
                        const latency = callTrace.latency_logs.find((l: LatencyLog) => l.turn_id === log.turn_id)
                        const isExpanded = expandedTurns.has(log.turn_id)

                        return (
                          <div key={log.turn_id} className="p-4">
                            {/* Turn Header */}
                            <button
                              onClick={() => toggleTurn(log.turn_id)}
                              className="w-full flex items-center justify-between text-left"
                            >
                              <div className="flex items-center gap-3">
                                {isExpanded ? (
                                  <ChevronDown className="h-4 w-4 text-gray-400" />
                                ) : (
                                  <ChevronRight className="h-4 w-4 text-gray-400" />
                                )}
                                <span className="font-medium text-gray-900">
                                  Turn {log.turn_id}
                                </span>
                                {log.detected_intent && (
                                  <Badge variant="primary">{log.detected_intent}</Badge>
                                )}
                                {log.was_escalated > 0 && (
                                  <Badge variant="danger">Escalated</Badge>
                                )}
                              </div>
                              {latency?.total_latency_ms && (
                                <span className="text-xs text-gray-400">
                                  {latency.total_latency_ms}ms
                                </span>
                              )}
                            </button>

                            {/* Turn Content */}
                            {isExpanded && (
                              <div className="mt-4 space-y-4 pl-7">
                                {/* Transcript */}
                                {log.user_transcript && (
                                  <div className="flex items-start gap-2">
                                    <User className="h-4 w-4 text-gray-400 mt-0.5" />
                                    <div>
                                      <p className="text-xs font-medium text-gray-500">Klant</p>
                                      <p className="text-sm text-gray-700">{log.user_transcript}</p>
                                    </div>
                                  </div>
                                )}
                                {log.assistant_transcript && (
                                  <div className="flex items-start gap-2">
                                    <Bot className="h-4 w-4 text-primary-500 mt-0.5" />
                                    <div>
                                      <p className="text-xs font-medium text-gray-500">AI</p>
                                      <p className="text-sm text-gray-700">{log.assistant_transcript}</p>
                                    </div>
                                  </div>
                                )}

                                {/* Tool Calls */}
                                {log.tool_calls && log.tool_calls.length > 0 && (
                                  <div className="flex items-start gap-2">
                                    <Wrench className="h-4 w-4 text-orange-500 mt-0.5" />
                                    <div className="flex-1">
                                      <p className="text-xs font-medium text-gray-500 mb-2">Tool Calls</p>
                                      <div className="space-y-2">
                                        {log.tool_calls.map((tc, i) => (
                                          <div key={i} className="bg-gray-50 rounded p-2 text-xs">
                                            <div className="flex items-center justify-between">
                                              <span className="font-mono font-medium">{tc.name}</span>
                                              <span className="text-gray-400">{tc.latency_ms}ms</span>
                                            </div>
                                            <pre className="mt-1 text-gray-600 overflow-x-auto">
                                              {JSON.stringify(tc.arguments, null, 2)}
                                            </pre>
                                            {tc.result && (
                                              <pre className="mt-1 text-green-600 overflow-x-auto">
                                                → {JSON.stringify(tc.result, null, 2).substring(0, 200)}...
                                              </pre>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {/* Context Injection */}
                                {(log.facts || log.instructions) && (
                                  <div className="bg-primary-50 rounded p-3">
                                    <p className="text-xs font-medium text-primary-700 mb-2">
                                      Context Injection → ElevenLabs AI
                                    </p>
                                    {log.facts && (
                                      <div className="mb-2">
                                        <span className="text-xs text-primary-600">Facts:</span>
                                        <p className="text-sm text-primary-800">{log.facts}</p>
                                      </div>
                                    )}
                                    {log.instructions && (
                                      <div>
                                        <span className="text-xs text-primary-600">Instructions:</span>
                                        <p className="text-sm text-primary-800">{log.instructions}</p>
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Latency Breakdown */}
                                {latency && (
                                  <div className="flex items-center gap-4 text-xs text-gray-500">
                                    <Clock className="h-3 w-3" />
                                    <span>STT: {latency.stt_latency_ms || 0}ms</span>
                                    <span>Orch: {latency.orchestrator_latency_ms || 0}ms</span>
                                    <span>Pod: {latency.pod_latency_ms || 0}ms</span>
                                    <span className="font-medium">
                                      Total: {latency.total_latency_ms || 0}ms
                                    </span>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </CardBody>
              </Card>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
