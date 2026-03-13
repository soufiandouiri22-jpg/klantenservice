'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardCheck,
  AlertTriangle,
  Wrench,
  ThumbsUp,
  Eye,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Search,
  MessageSquare,
} from 'lucide-react'
import { format } from 'date-fns'
import { nl } from 'date-fns/locale'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { adminApi } from '@/lib/api'
import toast from 'react-hot-toast'

// ── Types ───────────────────────────────────────────────────

interface EvaluationItem {
  id: string
  call_log_id: string
  company_id: string
  quality_score: number
  hallucination_detected: boolean
  wrong_tool_detected: boolean
  customer_helped: boolean
  needs_review: boolean
  latency_ms: number | null
  summary: string | null
  issues: Array<{ type: string; description: string; severity: string }>
  tool_usage: any[]
  langsmith_run_id: string | null
  evaluator_model: string | null
  evaluated_at: string
  created_at: string
  caller_number: string | null
  called_number: string | null
  call_started_at: string | null
  call_duration_seconds: number | null
  ai_worker_name: string | null
  company_name: string | null
}

interface EvaluationDetail extends EvaluationItem {
  transcript: Array<{ speaker: string; message: string; timestamp: string | null }>
}

interface Summary {
  total_evaluated: number
  average_score: number | null
  hallucination_rate: number | null
  wrong_tool_rate: number | null
  customer_helped_rate: number | null
  needs_review_count: number
}

// ── Helpers ─────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  if (score >= 80) return <Badge variant="success">{score}</Badge>
  if (score >= 60) return <Badge variant="warning">{score}</Badge>
  return <Badge variant="danger">{score}</Badge>
}

function BoolBadge({ value, trueLabel, falseLabel, invertColor = false }: {
  value: boolean; trueLabel: string; falseLabel: string; invertColor?: boolean
}) {
  if (invertColor) {
    return <Badge variant={value ? "success" : "gray"}>{value ? trueLabel : falseLabel}</Badge>
  }
  return <Badge variant={value ? "danger" : "gray"}>{value ? trueLabel : falseLabel}</Badge>
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
            {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
          </div>
          <div className={`p-3 rounded-lg ${statusColors[status]}`}>
            {icon}
          </div>
        </div>
      </CardBody>
    </Card>
  )
}

const PERIODS = [
  { value: '7d', label: '7 dagen' },
  { value: '30d', label: '30 dagen' },
  { value: '90d', label: '90 dagen' },
  { value: 'all', label: 'Alles' },
]

function periodToDateRange(period: string): { date_from?: string; date_to?: string } {
  if (period === 'all') return {}
  const days = parseInt(period)
  const from = new Date()
  from.setDate(from.getDate() - days)
  return { date_from: from.toISOString().split('T')[0] }
}

// ── Main Component ──────────────────────────────────────────

export function EvaluationsTab() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [period, setPeriod] = useState('30d')
  const [hallucinationOnly, setHallucinationOnly] = useState(false)
  const [wrongToolOnly, setWrongToolOnly] = useState(false)
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false)
  const [scoreRange, setScoreRange] = useState<string>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const dateRange = periodToDateRange(period)

  const scoreParams = (() => {
    switch (scoreRange) {
      case '<50': return { min_score: 0, max_score: 49 }
      case '50-75': return { min_score: 50, max_score: 75 }
      case '75+': return { min_score: 75 }
      default: return {}
    }
  })()

  // ── Queries ──

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['evaluations-summary', period],
    queryFn: () => adminApi.getEvaluationSummary(dateRange),
  })

  const { data: evaluations, isLoading: listLoading } = useQuery({
    queryKey: ['evaluations', page, period, hallucinationOnly, wrongToolOnly, needsReviewOnly, scoreRange],
    queryFn: () => adminApi.getEvaluations({
      page,
      page_size: 20,
      ...dateRange,
      hallucination_only: hallucinationOnly || undefined,
      wrong_tool_only: wrongToolOnly || undefined,
      needs_review_only: needsReviewOnly || undefined,
      ...scoreParams,
    }),
  })

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['evaluation-detail', selectedId],
    queryFn: () => adminApi.getEvaluationDetail(selectedId!),
    enabled: !!selectedId,
  })

  const syncMutation = useMutation({
    mutationFn: () => adminApi.syncEvaluations({ limit: 100 }),
    onSuccess: () => {
      toast.success('Evaluatie sync gestart')
      queryClient.invalidateQueries({ queryKey: ['evaluations'] })
      queryClient.invalidateQueries({ queryKey: ['evaluations-summary'] })
    },
    onError: () => toast.error('Sync mislukt'),
  })

  const summaryData: Summary = summary || {
    total_evaluated: 0, average_score: null, hallucination_rate: null,
    wrong_tool_rate: null, customer_helped_rate: null, needs_review_count: 0,
  }

  const items: EvaluationItem[] = evaluations?.items || []
  const totalPages = evaluations?.total_pages || 1

  // ── Render ──

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">AI Evaluaties</h2>
          <p className="text-sm text-gray-500">Kwaliteitsbeoordeling van AI-gesprekken via GPT-evaluator</p>
        </div>
        <Button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          variant="outline"
          size="sm"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
          Sync evaluaties
        </Button>
      </div>

      {/* KPI Cards */}
      {summaryLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <MetricCard
            title="Geevalueerd"
            value={summaryData.total_evaluated}
            icon={<ClipboardCheck className="h-5 w-5" />}
          />
          <MetricCard
            title="Gem. score"
            value={summaryData.average_score != null ? `${summaryData.average_score}` : '–'}
            icon={<ThumbsUp className="h-5 w-5" />}
            status={summaryData.average_score != null ? (summaryData.average_score >= 75 ? 'success' : summaryData.average_score >= 50 ? 'warning' : 'error') : 'neutral'}
          />
          <MetricCard
            title="Hallucinatie %"
            value={summaryData.hallucination_rate != null ? `${summaryData.hallucination_rate}%` : '–'}
            icon={<AlertTriangle className="h-5 w-5" />}
            status={summaryData.hallucination_rate != null ? (summaryData.hallucination_rate <= 5 ? 'success' : summaryData.hallucination_rate <= 15 ? 'warning' : 'error') : 'neutral'}
          />
          <MetricCard
            title="Verkeerd tool %"
            value={summaryData.wrong_tool_rate != null ? `${summaryData.wrong_tool_rate}%` : '–'}
            icon={<Wrench className="h-5 w-5" />}
            status={summaryData.wrong_tool_rate != null ? (summaryData.wrong_tool_rate <= 5 ? 'success' : summaryData.wrong_tool_rate <= 15 ? 'warning' : 'error') : 'neutral'}
          />
          <MetricCard
            title="Klant geholpen %"
            value={summaryData.customer_helped_rate != null ? `${summaryData.customer_helped_rate}%` : '–'}
            icon={<ThumbsUp className="h-5 w-5" />}
            status={summaryData.customer_helped_rate != null ? (summaryData.customer_helped_rate >= 90 ? 'success' : summaryData.customer_helped_rate >= 70 ? 'warning' : 'error') : 'neutral'}
          />
          <MetricCard
            title="Review nodig"
            value={summaryData.needs_review_count}
            icon={<Eye className="h-5 w-5" />}
            status={summaryData.needs_review_count > 0 ? 'warning' : 'neutral'}
          />
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardBody className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Period */}
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => { setPeriod(p.value); setPage(1) }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    period === p.value
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Toggle filters */}
            <button
              onClick={() => { setHallucinationOnly(!hallucinationOnly); setPage(1) }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                hallucinationOnly
                  ? 'bg-red-50 border-red-200 text-red-700'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <AlertTriangle className="h-3 w-3 inline mr-1" />
              Hallucinaties
            </button>

            <button
              onClick={() => { setWrongToolOnly(!wrongToolOnly); setPage(1) }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                wrongToolOnly
                  ? 'bg-orange-50 border-orange-200 text-orange-700'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <Wrench className="h-3 w-3 inline mr-1" />
              Verkeerd tool
            </button>

            <button
              onClick={() => { setNeedsReviewOnly(!needsReviewOnly); setPage(1) }}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                needsReviewOnly
                  ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <Eye className="h-3 w-3 inline mr-1" />
              Review nodig
            </button>

            {/* Score range */}
            <select
              value={scoreRange}
              onChange={(e) => { setScoreRange(e.target.value); setPage(1) }}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-600"
            >
              <option value="all">Alle scores</option>
              <option value="<50">Score &lt; 50</option>
              <option value="50-75">Score 50–75</option>
              <option value="75+">Score 75+</option>
            </select>
          </div>
        </CardBody>
      </Card>

      {/* Table */}
      <Card>
        <CardBody className="p-0">
          {listLoading ? (
            <div className="flex justify-center py-12"><Spinner /></div>
          ) : items.length === 0 ? (
            <EmptyState
              icon={ClipboardCheck}
              title="Geen evaluaties gevonden"
              description="Er zijn nog geen gesprekken geevalueerd. Klik op 'Sync evaluaties' om te starten."
              action={
                <Button variant="primary" size="sm" onClick={() => syncMutation.mutate()}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Evaluaties starten
                </Button>
              }
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50">
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Datum</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Beller</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AI Worker</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hallucinatie</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Verkeerd tool</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Geholpen</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Review</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {items.map((ev) => (
                      <tr
                        key={ev.id}
                        onClick={() => setSelectedId(ev.id)}
                        className="hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {ev.call_started_at
                            ? format(new Date(ev.call_started_at), 'd MMM yyyy HH:mm', { locale: nl })
                            : format(new Date(ev.evaluated_at), 'd MMM yyyy HH:mm', { locale: nl })
                          }
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {ev.caller_number || '–'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {ev.ai_worker_name || '–'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <ScoreBadge score={ev.quality_score} />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <BoolBadge value={ev.hallucination_detected} trueLabel="Ja" falseLabel="Nee" />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <BoolBadge value={ev.wrong_tool_detected} trueLabel="Ja" falseLabel="Nee" />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <BoolBadge value={ev.customer_helped} trueLabel="Ja" falseLabel="Nee" invertColor />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {ev.needs_review
                            ? <Badge variant="warning">Review</Badge>
                            : <Badge variant="gray">OK</Badge>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200">
                  <p className="text-sm text-gray-500">
                    Pagina {page} van {totalPages} ({evaluations?.total || 0} resultaten)
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(Math.max(1, page - 1))}
                      disabled={page <= 1}
                      className="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setPage(Math.min(totalPages, page + 1))}
                      disabled={page >= totalPages}
                      className="p-1.5 rounded-md hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardBody>
      </Card>

      {/* Detail Modal */}
      <Modal
        isOpen={!!selectedId}
        onClose={() => setSelectedId(null)}
        title="Evaluatie detail"
        description={detail?.caller_number ? `Beller: ${detail.caller_number}` : undefined}
        size="2xl"
      >
        {detailLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : detail ? (
          <div className="space-y-6">
            {/* Score + meta */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="text-center p-3 rounded-lg bg-gray-50">
                <p className="text-xs text-gray-500 mb-1">Score</p>
                <p className="text-2xl font-bold"><ScoreBadge score={detail.quality_score} /></p>
              </div>
              <div className="text-center p-3 rounded-lg bg-gray-50">
                <p className="text-xs text-gray-500 mb-1">Hallucinatie</p>
                <BoolBadge value={detail.hallucination_detected} trueLabel="Ja" falseLabel="Nee" />
              </div>
              <div className="text-center p-3 rounded-lg bg-gray-50">
                <p className="text-xs text-gray-500 mb-1">Verkeerd tool</p>
                <BoolBadge value={detail.wrong_tool_detected} trueLabel="Ja" falseLabel="Nee" />
              </div>
              <div className="text-center p-3 rounded-lg bg-gray-50">
                <p className="text-xs text-gray-500 mb-1">Klant geholpen</p>
                <BoolBadge value={detail.customer_helped} trueLabel="Ja" falseLabel="Nee" invertColor />
              </div>
            </div>

            {/* Summary */}
            {detail.summary && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Samenvatting</h4>
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">{detail.summary}</p>
              </div>
            )}

            {/* Issues */}
            {detail.issues && detail.issues.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Problemen ({detail.issues.length})</h4>
                <div className="space-y-2">
                  {detail.issues.map((issue: any, i: number) => (
                    <div key={i} className="flex items-start gap-3 bg-red-50 rounded-lg p-3">
                      <Badge variant={issue.severity === 'high' ? 'danger' : issue.severity === 'medium' ? 'warning' : 'gray'}>
                        {issue.severity}
                      </Badge>
                      <div>
                        <p className="text-xs font-medium text-gray-700">{issue.type}</p>
                        <p className="text-sm text-gray-600">{issue.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Transcript */}
            {detail.transcript && detail.transcript.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  <MessageSquare className="h-4 w-4 inline mr-1" />
                  Transcript ({detail.transcript.length} berichten)
                </h4>
                <div className="space-y-2 max-h-80 overflow-y-auto bg-gray-50 rounded-lg p-3">
                  {detail.transcript.map((msg: any, i: number) => (
                    <div key={i} className={`flex gap-2 ${msg.speaker === 'ai' ? '' : ''}`}>
                      <span className={`text-xs font-medium min-w-[40px] ${
                        msg.speaker === 'caller' ? 'text-blue-600' : 'text-green-600'
                      }`}>
                        {msg.speaker === 'caller' ? 'Klant' : 'AI'}
                      </span>
                      <p className="text-sm text-gray-700">{msg.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tool usage */}
            {detail.tool_usage && detail.tool_usage.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  <Wrench className="h-4 w-4 inline mr-1" />
                  Tools gebruikt ({detail.tool_usage.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {detail.tool_usage.map((tool: any, i: number) => (
                    <Badge key={i} variant="gray">
                      {typeof tool === 'string' ? tool : tool.tool || tool.name || JSON.stringify(tool)}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Meta */}
            <div className="border-t border-gray-200 pt-4 text-xs text-gray-400 space-y-1">
              <p>Bedrijf: {detail.company_name || '–'} | AI Worker: {detail.ai_worker_name || '–'}</p>
              <p>Duur: {detail.call_duration_seconds ? `${detail.call_duration_seconds}s` : '–'} | Model: {detail.evaluator_model || '–'}</p>
              {detail.langsmith_run_id && <p>LangSmith Run: {detail.langsmith_run_id}</p>}
            </div>
          </div>
        ) : (
          <EmptyState icon={ClipboardCheck} title="Geen data" />
        )}
      </Modal>
    </div>
  )
}
