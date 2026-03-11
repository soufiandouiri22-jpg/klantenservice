'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Phone,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  Eye,
  User,
  Bot,
  Zap,
  Lock,
  Unlock,
  MessageSquare,
} from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

// ── Types ───────────────────────────────────────────────────────

interface VoiceSession {
  id: string
  call_log_id: string | null
  call_sid: string | null
  company_id: string | null
  phase: string
  turn_count: number
  last_customer_intent: string | null
  goodbye_said_by_agent: boolean
  goodbye_said_by_customer: boolean
  goodbye_handshake_ok: boolean | null
  escalation_requested: boolean
  transfer_executed: boolean
  low_confidence_count: number
  repeat_topic_count: number
  hangup_reason: string | null
  ended_by: string | null
  created_at: string | null
  updated_at: string | null
}

interface PolicyDecision {
  id: string
  turn_number: number
  trigger_tool: string
  trigger_reason: string
  phase_before: string
  phase_after: string
  detected_intent: string | null
  intent_confidence: number | null
  policy_name: string
  allowed: boolean
  required_action: string
  reason_code: string
  instruction_nl: string | null
  model_complied: boolean | null
  violation: boolean
  violation_type: string | null
  created_at: string | null
}

interface PolicyTrace {
  call_id: string
  call_sid: string | null
  call_status: string | null
  call_outcome: string | null
  hangup_reason: string | null
  goodbye_handshake_ok: boolean | null
  ended_by: string | null
  policy_violations_count: number
  session: {
    phase: string | null
    turn_count: number
    goodbye_said_by_agent: boolean | null
    goodbye_said_by_customer: boolean | null
    escalation_requested: boolean | null
  } | null
  decisions: Array<{
    turn: number
    tool: string
    reason: string
    intent: string | null
    confidence: number | null
    policy: string
    allowed: boolean
    action: string
    code: string
    instruction: string | null
    violation: boolean
    phase: string
    at: string | null
  }>
  violations: Array<{
    turn: number
    policy: string
    type: string | null
    at: string | null
  }>
  total_decisions: number
  total_violations: number
}

// ── Rule Enforcement Registry ───────────────────────────────────

interface RuleEntry {
  name: string
  description: string
  enforcement: 'backend' | 'prompt' | 'provider'
  policyName: string | null
  status: 'active' | 'planned'
}

const RULES: RuleEntry[] = [
  {
    name: 'Goodbye Handshake',
    description: 'Wacht tot de klant ook afscheid neemt voordat het gesprek wordt beëindigd',
    enforcement: 'backend',
    policyName: 'goodbye_handshake',
    status: 'active',
  },
  {
    name: 'Escalatie bij boosheid',
    description: 'Bied doorverbinden aan bij gefrustreerde klant + eerdere mislukkingen',
    enforcement: 'backend',
    policyName: 'escalation',
    status: 'active',
  },
  {
    name: 'Off-topic blokkade',
    description: 'Weiger vragen die niet over het bedrijf gaan',
    enforcement: 'backend',
    policyName: 'scope_guard',
    status: 'active',
  },
  {
    name: 'Stilte reprompt',
    description: 'Vraag opnieuw bij stilte van de klant',
    enforcement: 'backend',
    policyName: 'silence_handler',
    status: 'active',
  },
  {
    name: 'Lage betrouwbaarheid',
    description: 'Niet raden bij laag zoekvertrouwen — eerlijk zeggen',
    enforcement: 'backend',
    policyName: 'low_confidence',
    status: 'active',
  },
  {
    name: 'Herhaalde mislukkingen',
    description: 'Escaleer na meerdere keren dezelfde vraag niet beantwoorden',
    enforcement: 'backend',
    policyName: 'repeated_failure',
    status: 'active',
  },
  {
    name: 'Nooit verzinnen',
    description: 'AI verzint nooit prijzen, tijden of feiten',
    enforcement: 'prompt',
    policyName: null,
    status: 'active',
  },
  {
    name: 'Geen AI-identiteit onthullen',
    description: 'AI noemt zichzelf nooit robot, bot of AI-assistent',
    enforcement: 'prompt',
    policyName: null,
    status: 'active',
  },
  {
    name: 'Privacy — geen BSN/creditcard',
    description: 'Nooit persoonlijke gegevens herhalen',
    enforcement: 'prompt',
    policyName: null,
    status: 'active',
  },
  {
    name: 'Geen medisch/juridisch advies',
    description: 'Nooit medisch, juridisch of financieel advies geven',
    enforcement: 'prompt',
    policyName: null,
    status: 'active',
  },
  {
    name: 'Maximaal 1-2 zinnen per beurt',
    description: 'Korte antwoorden, natuurlijk spreektempo',
    enforcement: 'prompt',
    policyName: null,
    status: 'active',
  },
  {
    name: 'STT / Spraakherkenning',
    description: 'Transcriptie-kwaliteit, spelling patience, taalinstelling',
    enforcement: 'provider',
    policyName: null,
    status: 'active',
  },
  {
    name: 'TTS / Stem',
    description: 'Stemkeuze, snelheid, stability — ElevenLabs dashboard',
    enforcement: 'provider',
    policyName: null,
    status: 'active',
  },
  {
    name: 'Turn-taking',
    description: 'Hoe lang ElevenLabs wacht voordat het de beurt pakt',
    enforcement: 'provider',
    policyName: null,
    status: 'active',
  },
]

// ── Helpers ──────────────────────────────────────────────────────

function phaseBadgeColor(phase: string | null): 'primary' | 'success' | 'danger' | 'warning' | 'gray' {
  switch (phase) {
    case 'greeting': return 'gray'
    case 'discovery': return 'primary'
    case 'answering': return 'primary'
    case 'clarifying': return 'warning'
    case 'action': return 'primary'
    case 'closing': return 'warning'
    case 'waiting_goodbye': return 'warning'
    case 'escalating': return 'danger'
    case 'ended': return 'success'
    default: return 'gray'
  }
}

function intentBadgeColor(intent: string | null): 'primary' | 'success' | 'danger' | 'warning' | 'gray' {
  switch (intent) {
    case 'goodbye': return 'success'
    case 'anger': return 'danger'
    case 'transfer_request': return 'danger'
    case 'complaint': return 'warning'
    case 'off_topic': return 'warning'
    case 'silence': return 'gray'
    case 'pricing': return 'primary'
    case 'question': return 'primary'
    case 'greeting': return 'gray'
    default: return 'gray'
  }
}

function enforcementBadge(type: string) {
  switch (type) {
    case 'backend':
      return <Badge variant="success"><Lock className="h-3 w-3 mr-1" />Backend</Badge>
    case 'prompt':
      return <Badge variant="warning"><MessageSquare className="h-3 w-3 mr-1" />Prompt</Badge>
    case 'provider':
      return <Badge variant="primary"><Zap className="h-3 w-3 mr-1" />Provider</Badge>
    default:
      return <Badge variant="gray">{type}</Badge>
  }
}

function formatTime(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ── Component ───────────────────────────────────────────────────

export function PolicyTraceTab() {
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [view, setView] = useState<'sessions' | 'rules'>('sessions')
  const [expandedTurns, setExpandedTurns] = useState<Set<number>>(new Set())

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['admin-voice-sessions'],
    queryFn: () => adminApi.getVoiceSessions({ limit: 50 }),
    refetchInterval: 30000,
  })

  const { data: policyTrace, isLoading: traceLoading } = useQuery({
    queryKey: ['admin-policy-trace', selectedCallId],
    queryFn: () => adminApi.getCallPolicyTrace(selectedCallId!),
    enabled: !!selectedCallId,
  })

  const sessions: VoiceSession[] = sessionsData?.sessions || []

  const toggleTurn = (turn: number) => {
    const next = new Set(expandedTurns)
    if (next.has(turn)) next.delete(turn)
    else next.add(turn)
    setExpandedTurns(next)
  }

  // ── Violation flags ─────────────────────────────────────────

  function getCallFlags(trace: PolicyTrace | null) {
    if (!trace) return []
    const flags: Array<{ label: string; severity: 'danger' | 'warning' }> = []

    if (trace.goodbye_handshake_ok === false) {
      flags.push({ label: 'Goodbye handshake mislukt', severity: 'danger' })
    }

    const deniedButProceeded = trace.decisions.filter(
      d => !d.allowed && d.action !== 'proceed'
    )
    if (deniedButProceeded.length > 0) {
      const hasViolation = trace.decisions.some(d => d.violation)
      if (hasViolation) {
        flags.push({ label: 'Policy overtreden door model', severity: 'danger' })
      }
    }

    if (trace.session?.escalation_requested && !trace.decisions.some(d => d.action === 'escalate')) {
      flags.push({ label: 'Escalatie had moeten plaatsvinden', severity: 'warning' })
    }

    if ((trace.policy_violations_count || 0) > 0) {
      flags.push({ label: `${trace.policy_violations_count} policy violation(s)`, severity: 'danger' })
    }

    return flags
  }

  return (
    <div className="space-y-6">
      {/* Header + View Toggle */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Policy Engine & Call Control</h2>
          <p className="text-sm text-gray-500">
            Bekijk gespreksstatus, intents, policy-beslissingen en violations per beurt.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setView('sessions')}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              view === 'sessions'
                ? 'bg-primary-100 text-primary-700'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Shield className="h-4 w-4 inline mr-1" />
            Sessies & Traces
          </button>
          <button
            onClick={() => setView('rules')}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              view === 'rules'
                ? 'bg-primary-100 text-primary-700'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Lock className="h-4 w-4 inline mr-1" />
            Rule Enforcement
          </button>
        </div>
      </div>

      {/* ── Rule Enforcement View ──────────────────────────────── */}
      {view === 'rules' && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Rule Enforcement Overzicht</CardTitle>
              <CardDescription>
                Per regel: hoe wordt deze afgedwongen?
              </CardDescription>
            </CardHeader>
            <CardBody className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase">
                    <th className="px-4 py-3">Regel</th>
                    <th className="px-4 py-3">Beschrijving</th>
                    <th className="px-4 py-3">Handhaving</th>
                    <th className="px-4 py-3">Policy</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {RULES.map((rule, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{rule.name}</td>
                      <td className="px-4 py-3 text-gray-600">{rule.description}</td>
                      <td className="px-4 py-3">{enforcementBadge(rule.enforcement)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-500">
                        {rule.policyName || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={rule.status === 'active' ? 'success' : 'gray'}>
                          {rule.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  {enforcementBadge('backend')}
                  <span className="text-gray-600">Deterministisch afgedwongen door de backend. Kan niet worden omzeild door het LLM.</span>
                </div>
              </div>
              <div className="flex gap-6 text-sm mt-2">
                <div className="flex items-center gap-2">
                  {enforcementBadge('prompt')}
                  <span className="text-gray-600">Instructie in de system prompt. Het LLM kan dit theoretisch negeren.</span>
                </div>
              </div>
              <div className="flex gap-6 text-sm mt-2">
                <div className="flex items-center gap-2">
                  {enforcementBadge('provider')}
                  <span className="text-gray-600">Geconfigureerd in het ElevenLabs dashboard. Niet zichtbaar in onze code.</span>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      )}

      {/* ── Sessions & Policy Trace View ───────────────────────── */}
      {view === 'sessions' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Session List */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Voice Sessions</CardTitle>
                <CardDescription>Klik om policy trace te bekijken</CardDescription>
              </CardHeader>
              <CardBody className="p-0 max-h-[700px] overflow-y-auto">
                {sessionsLoading ? (
                  <div className="flex justify-center py-8"><Spinner /></div>
                ) : sessions.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Shield className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                    <p>Geen voice sessions</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {sessions.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => {
                          setSelectedCallId(s.call_log_id)
                          setExpandedTurns(new Set())
                        }}
                        className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                          selectedCallId === s.call_log_id
                            ? 'bg-primary-50 border-l-2 border-primary-500'
                            : ''
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <Badge variant={phaseBadgeColor(s.phase)}>{s.phase}</Badge>
                          <span className="text-xs text-gray-400">
                            {s.turn_count} turns
                          </span>
                        </div>
                        <div className="mt-1 text-xs text-gray-500 truncate">
                          {s.call_sid || s.id.substring(0, 12)}
                        </div>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          {s.goodbye_handshake_ok === false && (
                            <Badge variant="danger">
                              <XCircle className="h-3 w-3 mr-1" />Handshake fail
                            </Badge>
                          )}
                          {s.goodbye_handshake_ok === true && (
                            <Badge variant="success">
                              <CheckCircle className="h-3 w-3 mr-1" />Handshake OK
                            </Badge>
                          )}
                          {s.escalation_requested && (
                            <Badge variant="danger">Escalatie</Badge>
                          )}
                          {s.ended_by && (
                            <Badge variant="gray">{s.ended_by}</Badge>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">
                          {s.created_at ? formatTime(s.created_at) : ''}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </CardBody>
            </Card>
          </div>

          {/* Policy Trace Detail */}
          <div className="lg:col-span-2">
            {!selectedCallId ? (
              <Card>
                <CardBody className="text-center py-12">
                  <Shield className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Selecteer een sessie</h3>
                  <p className="text-gray-500">Klik op een voice session om de policy trace te bekijken.</p>
                </CardBody>
              </Card>
            ) : traceLoading ? (
              <div className="flex justify-center py-12"><Spinner size="lg" /></div>
            ) : policyTrace ? (
              <div className="space-y-4">
                {/* Call Summary */}
                <Card>
                  <CardBody className="p-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Status</p>
                        <Badge variant={policyTrace.call_status === 'completed' ? 'success' : 'gray'}>
                          {policyTrace.call_status || '-'}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-gray-500">Hangup Reason</p>
                        <p className="font-medium">{policyTrace.hangup_reason || '-'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Ended By</p>
                        <p className="font-medium">{policyTrace.ended_by || '-'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Goodbye Handshake</p>
                        {policyTrace.goodbye_handshake_ok === true ? (
                          <Badge variant="success"><CheckCircle className="h-3 w-3 mr-1" />OK</Badge>
                        ) : policyTrace.goodbye_handshake_ok === false ? (
                          <Badge variant="danger"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </div>
                    </div>

                    {/* Session state */}
                    {policyTrace.session && (
                      <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                        <div className="bg-gray-50 rounded p-2">
                          <p className="text-gray-500">Phase</p>
                          <Badge variant={phaseBadgeColor(policyTrace.session.phase)}>
                            {policyTrace.session.phase || '-'}
                          </Badge>
                        </div>
                        <div className="bg-gray-50 rounded p-2">
                          <p className="text-gray-500">Turns</p>
                          <p className="font-medium">{policyTrace.session.turn_count}</p>
                        </div>
                        <div className="bg-gray-50 rounded p-2">
                          <p className="text-gray-500">Agent bye</p>
                          <p className="font-medium">{policyTrace.session.goodbye_said_by_agent ? 'Ja' : 'Nee'}</p>
                        </div>
                        <div className="bg-gray-50 rounded p-2">
                          <p className="text-gray-500">Klant bye</p>
                          <p className="font-medium">{policyTrace.session.goodbye_said_by_customer ? 'Ja' : 'Nee'}</p>
                        </div>
                        <div className="bg-gray-50 rounded p-2">
                          <p className="text-gray-500">Escalatie</p>
                          <p className="font-medium">{policyTrace.session.escalation_requested ? 'Ja' : 'Nee'}</p>
                        </div>
                      </div>
                    )}

                    {/* Flags */}
                    {(() => {
                      const flags = getCallFlags(policyTrace)
                      if (flags.length === 0) return null
                      return (
                        <div className="mt-4 space-y-2">
                          {flags.map((f, i) => (
                            <div
                              key={i}
                              className={`flex items-center gap-2 p-2 rounded text-sm ${
                                f.severity === 'danger'
                                  ? 'bg-red-50 text-red-700'
                                  : 'bg-yellow-50 text-yellow-700'
                              }`}
                            >
                              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                              {f.label}
                            </div>
                          ))}
                        </div>
                      )
                    })()}

                    {/* Stats bar */}
                    <div className="mt-4 flex gap-4 text-xs text-gray-500">
                      <span>{policyTrace.total_decisions} policy beslissingen</span>
                      <span>·</span>
                      <span className={policyTrace.total_violations > 0 ? 'text-red-600 font-medium' : ''}>
                        {policyTrace.total_violations} violations
                      </span>
                    </div>
                  </CardBody>
                </Card>

                {/* Turn-by-turn Policy Decisions */}
                <Card>
                  <CardHeader>
                    <CardTitle>Policy Beslissingen per Beurt</CardTitle>
                  </CardHeader>
                  <CardBody className="p-0">
                    {policyTrace.decisions.length === 0 ? (
                      <div className="text-center py-8 text-gray-500">
                        Geen policy beslissingen gelogd
                      </div>
                    ) : (
                      <div className="divide-y divide-gray-100">
                        {policyTrace.decisions.map((d, i) => {
                          const isExpanded = expandedTurns.has(i)
                          return (
                            <div key={i} className={`${d.violation ? 'bg-red-50' : ''}`}>
                              <button
                                onClick={() => toggleTurn(i)}
                                className="w-full flex items-center justify-between text-left p-4 hover:bg-gray-50/50"
                              >
                                <div className="flex items-center gap-3 flex-wrap">
                                  {isExpanded ? (
                                    <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                  )}
                                  <span className="text-sm font-medium text-gray-600">
                                    Turn {d.turn}
                                  </span>
                                  {d.intent && (
                                    <Badge variant={intentBadgeColor(d.intent)}>{d.intent}</Badge>
                                  )}
                                  <Badge variant={d.allowed ? 'success' : 'danger'}>
                                    {d.allowed ? (
                                      <><Unlock className="h-3 w-3 mr-1" />Allowed</>
                                    ) : (
                                      <><Lock className="h-3 w-3 mr-1" />Denied</>
                                    )}
                                  </Badge>
                                  <span className="text-xs text-gray-400 font-mono">{d.policy}</span>
                                  {d.violation && (
                                    <Badge variant="danger">
                                      <ShieldAlert className="h-3 w-3 mr-1" />VIOLATION
                                    </Badge>
                                  )}
                                </div>
                                <span className="text-xs text-gray-400">{d.at ? formatTime(d.at) : ''}</span>
                              </button>

                              {isExpanded && (
                                <div className="px-4 pb-4 pl-11 space-y-3">
                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div>
                                      <p className="text-gray-500">Tool</p>
                                      <p className="font-mono font-medium">{d.tool}</p>
                                    </div>
                                    <div>
                                      <p className="text-gray-500">Trigger</p>
                                      <p className="font-mono">{d.reason}</p>
                                    </div>
                                    <div>
                                      <p className="text-gray-500">Action</p>
                                      <p className="font-medium">{d.action}</p>
                                    </div>
                                    <div>
                                      <p className="text-gray-500">Reason Code</p>
                                      <p className="font-mono">{d.code}</p>
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-2 text-xs">
                                    <span className="text-gray-500">Phase:</span>
                                    <span className="font-mono">{d.phase}</span>
                                  </div>

                                  {d.confidence !== null && (
                                    <div className="text-xs text-gray-500">
                                      Intent confidence: {((d.confidence || 0) * 100).toFixed(0)}%
                                    </div>
                                  )}

                                  {d.instruction && (
                                    <div className="bg-blue-50 rounded p-3 text-sm text-blue-800">
                                      <p className="text-xs font-medium text-blue-600 mb-1">
                                        Instructie aan AI:
                                      </p>
                                      {d.instruction}
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

                {/* Violations Summary */}
                {policyTrace.violations.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-red-700">
                        <ShieldX className="h-5 w-5 inline mr-2" />
                        Violations
                      </CardTitle>
                    </CardHeader>
                    <CardBody className="p-0">
                      <div className="divide-y divide-red-100">
                        {policyTrace.violations.map((v, i) => (
                          <div key={i} className="p-4 bg-red-50">
                            <div className="flex items-center gap-3">
                              <AlertTriangle className="h-4 w-4 text-red-500" />
                              <span className="font-medium text-red-700">Turn {v.turn}</span>
                              <span className="font-mono text-sm text-red-600">{v.policy}</span>
                              {v.type && <Badge variant="danger">{v.type}</Badge>}
                              <span className="text-xs text-red-400 ml-auto">
                                {v.at ? formatTime(v.at) : ''}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
