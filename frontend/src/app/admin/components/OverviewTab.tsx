'use client'

import { useQuery } from '@tanstack/react-query'
import { 
  Phone, 
  AlertTriangle, 
  HelpCircle,
  DollarSign,
  Clock,
  RefreshCw,
  Users,
  TrendingUp,
  UserPlus,
  UserMinus,
  UserCheck,
  UserX,
  CreditCard
} from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  status?: 'success' | 'warning' | 'error' | 'neutral'
}

function MetricCard({ title, value, subtitle, icon, status = 'neutral' }: MetricCardProps) {
  const statusColors = {
    success: 'bg-green-100 text-green-600',
    warning: 'bg-yellow-100 text-yellow-600',
    error: 'bg-red-100 text-red-600',
    neutral: 'bg-gray-100 text-gray-600',
  }

  return (
    <Card>
      <CardBody className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="mt-2 text-3xl font-semibold text-gray-900">{value}</p>
            {subtitle && (
              <p className="mt-1 text-sm text-gray-500">{subtitle}</p>
            )}
          </div>
          <div className={`p-3 rounded-lg ${statusColors[status]}`}>
            {icon}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

export function OverviewTab() {
  const { data: overview, isLoading: overviewLoading, refetch: refetchOverview } = useQuery({
    queryKey: ['admin-metrics-overview'],
    queryFn: () => adminApi.getMetricsOverview(),
    refetchInterval: 10000,
  })

  const { data: latency, isLoading: latencyLoading, refetch: refetchLatency } = useQuery({
    queryKey: ['admin-metrics-latency'],
    queryFn: () => adminApi.getLatencyMetrics(24),
    refetchInterval: 30000,
  })

  const { data: costs, isLoading: costsLoading, refetch: refetchCosts } = useQuery({
    queryKey: ['admin-metrics-costs'],
    queryFn: () => adminApi.getCostMetrics(),
    refetchInterval: 60000,
  })

  const { data: business, isLoading: businessLoading, refetch: refetchBusiness } = useQuery({
    queryKey: ['admin-metrics-business'],
    queryFn: () => adminApi.getBusinessMetrics(),
    refetchInterval: 60000,
  })

  const refreshAll = () => {
    refetchOverview()
    refetchLatency()
    refetchCosts()
    refetchBusiness()
  }

  const formatCurrency = (cents: number) => {
    return `€${(cents / 100).toFixed(2)}`
  }

  if (overviewLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Real-time Overzicht</h2>
        <Button variant="outline" size="sm" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Vernieuwen
        </Button>
      </div>

      {/* Main Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Actieve Calls"
          value={overview?.active_calls || 0}
          subtitle={`${overview?.calls_today || 0} vandaag`}
          icon={<Phone className="h-6 w-6" />}
          status={overview?.active_calls > 0 ? 'success' : 'neutral'}
        />
        
        <MetricCard
          title="Gem. Gespreksduur"
          value={overview?.avg_duration_today ? `${Math.floor(overview.avg_duration_today / 60)}m ${overview.avg_duration_today % 60}s` : '0s'}
          subtitle="Vandaag"
          icon={<Clock className="h-6 w-6" />}
          status="neutral"
        />
        
        <MetricCard
          title="Errors Vandaag"
          value={overview?.errors_today || 0}
          subtitle={`${overview?.error_rate_today?.toFixed(1) || 0}% error rate`}
          icon={<AlertTriangle className="h-6 w-6" />}
          status={overview?.error_rate_today > 5 ? 'error' : overview?.error_rate_today > 1 ? 'warning' : 'success'}
        />
        
        <MetricCard
          title="Onbekende Vragen"
          value={overview?.unknown_questions_today || 0}
          subtitle={`${overview?.unknown_rate_today?.toFixed(1) || 0}% unknown rate`}
          icon={<HelpCircle className="h-6 w-6" />}
          status={overview?.unknown_rate_today > 20 ? 'warning' : 'neutral'}
        />
      </div>

      {/* Business Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-600" />
            Business Metrics
          </CardTitle>
        </CardHeader>
        <CardBody>
          {businessLoading ? (
            <Spinner />
          ) : (
            <div className="space-y-6">
              {/* Revenue */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg p-4 border border-green-100">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="h-5 w-5 text-green-600" />
                    <p className="text-sm font-medium text-green-700">MRR</p>
                  </div>
                  <p className="text-3xl font-bold text-green-900">
                    {formatCurrency(business?.mrr_cents || 0)}
                  </p>
                  <p className="text-xs text-green-600 mt-1">Monthly Recurring Revenue</p>
                </div>
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="h-5 w-5 text-blue-600" />
                    <p className="text-sm font-medium text-blue-700">ARR</p>
                  </div>
                  <p className="text-3xl font-bold text-blue-900">
                    {formatCurrency(business?.arr_cents || 0)}
                  </p>
                  <p className="text-xs text-blue-600 mt-1">Annual Recurring Revenue</p>
                </div>
                <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-lg p-4 border border-purple-100">
                  <div className="flex items-center gap-2 mb-2">
                    <CreditCard className="h-5 w-5 text-purple-600" />
                    <p className="text-sm font-medium text-purple-700">Conversie Rate</p>
                  </div>
                  <p className="text-3xl font-bold text-purple-900">
                    {business?.trial_to_paid_rate?.toFixed(1) || 0}%
                  </p>
                  <p className="text-xs text-purple-600 mt-1">Trial naar Betaald</p>
                </div>
              </div>

              {/* Customer Counts */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="bg-gray-50 rounded-lg p-4 flex flex-col items-center">
                  <Users className="h-5 w-5 text-gray-600 mb-2" />
                  <p className="text-2xl font-bold text-gray-900">{business?.total_customers || 0}</p>
                  <p className="text-xs text-gray-500">Totaal</p>
                </div>
                <div className="bg-green-50 rounded-lg p-4 flex flex-col items-center">
                  <UserCheck className="h-5 w-5 text-green-600 mb-2" />
                  <p className="text-2xl font-bold text-green-700">{business?.active_customers || 0}</p>
                  <p className="text-xs text-green-600">Actief</p>
                </div>
                <div className="bg-amber-50 rounded-lg p-4 flex flex-col items-center">
                  <Clock className="h-5 w-5 text-amber-600 mb-2" />
                  <p className="text-2xl font-bold text-amber-700">{business?.trialing_customers || 0}</p>
                  <p className="text-xs text-amber-600">Proefperiode</p>
                </div>
                <div className="bg-gray-100 rounded-lg p-4 flex flex-col items-center">
                  <UserX className="h-5 w-5 text-gray-500 mb-2" />
                  <p className="text-2xl font-bold text-gray-600">{business?.pending_customers || 0}</p>
                  <p className="text-xs text-gray-500">Pending</p>
                </div>
                <div className="bg-red-50 rounded-lg p-4 flex flex-col items-center">
                  <UserMinus className="h-5 w-5 text-red-500 mb-2" />
                  <p className="text-2xl font-bold text-red-600">{business?.churned_this_month || 0}</p>
                  <p className="text-xs text-red-500">Churn deze maand</p>
                </div>
              </div>

              {/* Plan Distribution */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-3">Klanten per Plan</p>
                <div className="grid grid-cols-3 gap-4">
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-gray-600">Starter</span>
                        <p className="text-xs text-gray-400">€149/mo • €1.490/jr</p>
                      </div>
                      <span className="text-lg font-semibold">{business?.starter_customers || 0}</span>
                    </div>
                    <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${business?.active_customers ? (business.starter_customers / business.active_customers * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-gray-600">Business</span>
                        <p className="text-xs text-gray-400">€299/mo • €2.990/jr</p>
                      </div>
                      <span className="text-lg font-semibold">{business?.business_customers || 0}</span>
                    </div>
                    <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-purple-500 rounded-full"
                        style={{ width: `${business?.active_customers ? (business.business_customers / business.active_customers * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-sm text-gray-600">Enterprise</span>
                        <p className="text-xs text-gray-400">Op aanvraag</p>
                      </div>
                      <span className="text-lg font-semibold">{business?.enterprise_customers || 0}</span>
                    </div>
                    <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-amber-500 rounded-full"
                        style={{ width: `${business?.active_customers ? (business.enterprise_customers / business.active_customers * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Growth */}
              <div className="flex gap-4">
                <div className="flex-1 border rounded-lg p-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                    <UserPlus className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{business?.new_customers_this_month || 0}</p>
                    <p className="text-xs text-gray-500">Nieuwe klanten deze maand</p>
                  </div>
                </div>
                <div className="flex-1 border rounded-lg p-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100">
                    <UserMinus className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{business?.churned_this_month || 0}</p>
                    <p className="text-xs text-gray-500">Opgezegd deze maand</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Latency Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Latency (laatste 24 uur)</CardTitle>
        </CardHeader>
        <CardBody>
          {latencyLoading ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div>
                <p className="text-sm font-medium text-gray-500">STT (Whisper)</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {latency?.stt_p95 || 0}ms
                </p>
                <p className="text-xs text-gray-400">p95</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Orchestrator</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {latency?.orchestrator_p95 || 0}ms
                </p>
                <p className="text-xs text-gray-400">p95</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">ElevenLabs AI</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {latency?.pod_p95 || 0}ms
                </p>
                <p className="text-xs text-gray-400">p95</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Totaal E2E</p>
                <p className="mt-1 text-2xl font-semibold text-gray-900">
                  {latency?.total_p95 || 0}ms
                </p>
                <p className="text-xs text-gray-400">p95 ({latency?.sample_count || 0} samples)</p>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Cost Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>API-kosten</CardTitle>
        </CardHeader>
        <CardBody>
          {costsLoading ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-4">Vandaag</h4>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <img src="/app-icons/elevenlabs.svg" alt="ElevenLabs" className="h-4 w-4" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      <span className="text-gray-600">ElevenLabs</span>
                    </div>
                    <div className="text-right">
                      <span className="font-medium">{formatCurrency(costs?.elevenlabs_cost_today_cents || 0)}</span>
                      <p className="text-xs text-gray-400">{(costs?.elevenlabs_characters_today || 0).toLocaleString()} chars</p>
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-red-500" />
                      <span className="text-gray-600">Twilio</span>
                    </div>
                    <div className="text-right">
                      <span className="font-medium">{formatCurrency(costs?.twilio_cost_today_cents || 0)}</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_calls_today || 0} calls · {costs?.twilio_minutes_today || 0} min</p>
                    </div>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-gray-900 font-medium">Totaal</span>
                    <span className="font-semibold text-primary-600">
                      {formatCurrency(costs?.total_cost_today_cents || 0)}
                    </span>
                  </div>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-4">Deze Maand</h4>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <img src="/app-icons/elevenlabs.svg" alt="ElevenLabs" className="h-4 w-4" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      <span className="text-gray-600">ElevenLabs</span>
                    </div>
                    <div className="text-right">
                      <span className="font-medium">{formatCurrency(costs?.elevenlabs_cost_month_cents || 0)}</span>
                      <p className="text-xs text-gray-400">{(costs?.elevenlabs_characters_month || 0).toLocaleString()} chars</p>
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Belkosten</span>
                    <div className="text-right">
                      <span className="font-medium">{formatCurrency(costs?.twilio_calls_cost_month_cents || 0)}</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_calls_month || 0} calls · {costs?.twilio_minutes_month || 0} min</p>
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Telefoonnummers</span>
                    <div className="text-right">
                      <span className="font-medium">{formatCurrency(costs?.twilio_numbers_cost_month_cents || 0)}</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_numbers_count_month || 0} nummers</p>
                    </div>
                  </div>
                  {(costs?.twilio_media_streams_cost_month_cents || 0) > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Media Streams</span>
                      <span className="font-medium">{formatCurrency(costs?.twilio_media_streams_cost_month_cents || 0)}</span>
                    </div>
                  )}
                  {(costs?.twilio_recordings_cost_month_cents || 0) > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">Opnames</span>
                      <span className="font-medium">{formatCurrency(costs?.twilio_recordings_cost_month_cents || 0)}</span>
                    </div>
                  )}
                  {(costs?.twilio_tts_cost_month_cents || 0) > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-gray-600">TTS (Polly)</span>
                      <span className="font-medium">{formatCurrency(costs?.twilio_tts_cost_month_cents || 0)}</span>
                    </div>
                  )}
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-gray-900 font-medium">Totaal</span>
                    <span className="font-semibold text-primary-600">
                      {formatCurrency(costs?.total_cost_month_cents || 0)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardBody className="p-6">
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Calls vandaag</p>
                <p className="text-xl font-semibold">{overview?.calls_today || 0}</p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="p-6">
            <div className="flex items-center gap-3">
              <Phone className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Calls deze maand</p>
                <p className="text-xl font-semibold">{overview?.calls_this_month || 0}</p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="p-6">
            <div className="flex items-center gap-3">
              <DollarSign className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm text-gray-500">Gem. kosten/call</p>
                <p className="text-xl font-semibold">
                  {(costs?.twilio_calls_month || 0) > 0
                    ? formatCurrency((costs!.twilio_calls_cost_month_cents + costs!.twilio_media_streams_cost_month_cents + (costs!.elevenlabs_cost_month_cents || 0)) / costs!.twilio_calls_month)
                    : '€0.00'
                  }
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
