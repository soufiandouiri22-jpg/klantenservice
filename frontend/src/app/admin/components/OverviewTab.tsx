'use client'

import { useQuery } from '@tanstack/react-query'
import { 
  Phone, 
  Server, 
  AlertTriangle, 
  HelpCircle,
  DollarSign,
  Clock,
  RefreshCw
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
    queryFn: adminApi.getMetricsOverview,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: latency, isLoading: latencyLoading } = useQuery({
    queryKey: ['admin-metrics-latency'],
    queryFn: () => adminApi.getLatencyMetrics(24),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const { data: costs, isLoading: costsLoading } = useQuery({
    queryKey: ['admin-metrics-costs'],
    queryFn: adminApi.getCostMetrics,
    refetchInterval: 60000, // Refresh every minute
  })

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
        <Button variant="outline" size="sm" onClick={() => refetchOverview()}>
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
          title="Pod Status"
          value={overview?.pod_online ? 'Online' : 'Offline'}
          subtitle={overview?.pod_url ? 'RunPod GPU' : 'Niet geconfigureerd'}
          icon={<Server className="h-6 w-6" />}
          status={overview?.pod_online ? 'success' : 'error'}
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
                <p className="text-sm font-medium text-gray-500">Pod (PersonaPlex)</p>
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
          <CardTitle>Kosten</CardTitle>
        </CardHeader>
        <CardBody>
          {costsLoading ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-4">Vandaag</h4>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">STT (Whisper)</span>
                    <span className="font-medium">{formatCurrency(costs?.stt_cost_today_cents || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">LLM (Orchestrator)</span>
                    <span className="font-medium">{formatCurrency(costs?.llm_cost_today_cents || 0)}</span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-gray-900 font-medium">Totaal</span>
                    <span className="font-semibold text-primary-600">
                      {formatCurrency(costs?.total_cost_today_cents || 0)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {costs?.tokens_today?.toLocaleString() || 0} tokens
                  </p>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-4">Deze Maand</h4>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">STT (Whisper)</span>
                    <span className="font-medium">{formatCurrency(costs?.stt_cost_month_cents || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">LLM (Orchestrator)</span>
                    <span className="font-medium">{formatCurrency(costs?.llm_cost_month_cents || 0)}</span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="text-gray-900 font-medium">Totaal</span>
                    <span className="font-semibold text-primary-600">
                      {formatCurrency(costs?.total_cost_month_cents || 0)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {costs?.tokens_month?.toLocaleString() || 0} tokens
                  </p>
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
                  {overview?.calls_today > 0 
                    ? formatCurrency((costs?.total_cost_today_cents || 0) / overview.calls_today)
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
