'use client'

import { useState } from 'react'
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
  CreditCard,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import {
  format,
  startOfMonth,
  endOfMonth,
  subMonths,
  addMonths,
  isSameMonth,
} from 'date-fns'
import { nl } from 'date-fns/locale'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

function MonthPicker({ month, onChange }: { month: Date; onChange: (m: Date) => void }) {
  const isCurrentMonth = isSameMonth(month, new Date())
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange(subMonths(month, 1))}
        className="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
      >
        <ChevronLeft className="h-4 w-4 text-gray-500" />
      </button>
      <span className="text-sm font-medium text-gray-700 min-w-[140px] text-center capitalize">
        {format(month, 'MMMM yyyy', { locale: nl })}
      </span>
      <button
        onClick={() => onChange(addMonths(month, 1))}
        disabled={isCurrentMonth}
        className={`p-1.5 rounded-md transition-colors ${
          isCurrentMonth ? 'text-gray-300 cursor-not-allowed' : 'hover:bg-gray-100 text-gray-500'
        }`}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}

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
  const [costMonth, setCostMonth] = useState(() => new Date())

  const costStartStr = format(startOfMonth(costMonth), 'yyyy-MM-dd')
  const costEndStr = format(
    isSameMonth(costMonth, new Date()) ? new Date() : endOfMonth(costMonth),
    'yyyy-MM-dd'
  )

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
    queryKey: ['admin-metrics-costs', costStartStr, costEndStr],
    queryFn: () => adminApi.getCostMetrics(costStartStr, costEndStr),
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

  const totalCosts = (costs?.total_cost_today_cents || 0)
  const elCosts = (costs?.elevenlabs_cost_today_cents || 0)
  const twCosts = (costs?.twilio_cost_today_cents || 0)
  const elPct = totalCosts > 0 ? (elCosts / totalCosts) * 100 : 0
  const twPct = totalCosts > 0 ? (twCosts / totalCosts) * 100 : 0

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

      {/* API Costs — Dynamic */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-gray-500" />
              API-kosten
            </CardTitle>
            <MonthPicker month={costMonth} onChange={setCostMonth} />
          </div>
        </CardHeader>
        <CardBody>
          {costsLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : (
            <div className="flex flex-col lg:flex-row gap-8">
              {/* Left: totaal + stacked bar */}
              <div className="flex-shrink-0 lg:w-56 flex flex-col items-center justify-center">
                <p className="text-sm text-gray-500 mb-1">Totaal</p>
                <p className="text-4xl font-bold text-gray-900">{formatCurrency(totalCosts)}</p>
                <p className="text-xs text-gray-400 mt-1 capitalize">
                  {format(costMonth, 'MMMM yyyy', { locale: nl })}
                </p>
                {totalCosts > 0 && (
                  <div className="w-full mt-4 h-3 rounded-full overflow-hidden flex bg-gray-100">
                    <div className="bg-violet-500 transition-all" style={{ width: `${elPct}%` }} />
                    <div className="bg-red-400 transition-all" style={{ width: `${twPct}%` }} />
                  </div>
                )}
                <div className="flex gap-4 mt-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-500" />ElevenLabs</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Twilio</span>
                </div>
              </div>

              {/* Right: breakdown list */}
              <div className="flex-1 min-w-0">
                <div className="space-y-4">
                  {/* ElevenLabs */}
                  <div className="flex items-center justify-between py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50">
                        <img src="/app-icons/elevenlabs.svg" alt="ElevenLabs" className="h-5 w-5" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">ElevenLabs</p>
                        <p className="text-xs text-gray-400">{(costs?.elevenlabs_characters_today || 0).toLocaleString()} characters</p>
                      </div>
                    </div>
                    <span className="text-lg font-semibold text-gray-900">{formatCurrency(elCosts)}</span>
                  </div>

                  {/* Twilio — Calls */}
                  <div className="flex items-center justify-between py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50">
                        <Phone className="h-5 w-5 text-red-500" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Twilio — Belkosten</p>
                        <p className="text-xs text-gray-400">{costs?.twilio_calls_today || 0} calls · {costs?.twilio_minutes_today || 0} min</p>
                      </div>
                    </div>
                    <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.twilio_calls_cost_range_cents || 0)}</span>
                  </div>

                  {/* Twilio — Phone numbers */}
                  <div className="flex items-center justify-between py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50">
                        <Phone className="h-5 w-5 text-red-400" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Twilio — Telefoonnummers</p>
                        <p className="text-xs text-gray-400">{costs?.twilio_numbers_count_range || 0} nummers</p>
                      </div>
                    </div>
                    <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.twilio_numbers_cost_range_cents || 0)}</span>
                  </div>

                  {/* Optional rows */}
                  {(costs?.twilio_media_streams_cost_range_cents || 0) > 0 && (
                    <div className="flex items-center justify-between py-3 border-b border-gray-100">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-50">
                          <Phone className="h-5 w-5 text-gray-400" />
                        </div>
                        <p className="font-medium text-gray-900">Media Streams</p>
                      </div>
                      <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs.twilio_media_streams_cost_range_cents)}</span>
                    </div>
                  )}
                  {(costs?.twilio_recordings_cost_range_cents || 0) > 0 && (
                    <div className="flex items-center justify-between py-3 border-b border-gray-100">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-50">
                          <Phone className="h-5 w-5 text-gray-400" />
                        </div>
                        <p className="font-medium text-gray-900">Opnames</p>
                      </div>
                      <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs.twilio_recordings_cost_range_cents)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
