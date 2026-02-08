'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Phone, Search, Filter, Play, Clock, User, MessageSquare, X, ChevronDown } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { callsApi } from '@/lib/api'
import { formatDateTime, formatDuration, formatPhoneNumber, getStatusLabel, getStatusColor } from '@/lib/utils'

export default function CallsPage() {
  const [page, setPage] = useState(1)
  const [selectedCall, setSelectedCall] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('')

  const activeFilterCount = [statusFilter, outcomeFilter].filter(Boolean).length

  const { data: callsData, isLoading } = useQuery({
    queryKey: ['calls', page, searchQuery, statusFilter, outcomeFilter],
    queryFn: () => callsApi.list({
      page,
      page_size: 20,
      search: searchQuery || undefined,
      status: statusFilter || undefined,
      outcome: outcomeFilter || undefined,
    }),
  })

  const { data: callDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['call-detail', selectedCall?.id],
    queryFn: () => callsApi.get(selectedCall.id),
    enabled: !!selectedCall,
  })

  const { data: stats } = useQuery({
    queryKey: ['call-stats'],
    queryFn: () => callsApi.getStats(),
  })

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const calls = callsData?.items || []

  return (
    <DashboardLayout>
      <Header
        title="Gesprekken"
        description="Bekijk en analyseer alle telefoongesprekken."
      />

      <div className="p-6 space-y-6">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardBody className="text-center">
                <p className="text-3xl font-bold text-gray-900">{stats.total_calls}</p>
                <p className="text-sm text-gray-500">Totaal gesprekken</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="text-center">
                <p className="text-3xl font-bold text-green-600">{stats.completed_calls}</p>
                <p className="text-sm text-gray-500">Afgerond</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="text-center">
                <p className="text-3xl font-bold text-red-600">{stats.missed_calls}</p>
                <p className="text-sm text-gray-500">Gemist</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="text-center">
                <p className="text-3xl font-bold text-primary-600">{formatDuration(stats.average_duration_seconds)}</p>
                <p className="text-sm text-gray-500">Gem. duur</p>
              </CardBody>
            </Card>
          </div>
        )}

        {/* Search & Filter */}
        <Card>
          <CardBody className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Zoek op telefoonnummer of naam..."
                  className="input pl-10"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setPage(1) }}
                />
              </div>
              <Button
                variant={activeFilterCount > 0 ? 'primary' : 'outline'}
                leftIcon={<Filter className="h-4 w-4" />}
                onClick={() => setShowFilters(!showFilters)}
              >
                Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
              </Button>
            </div>

            {showFilters && (
              <div className="flex items-center gap-4 pt-2 border-t border-gray-100">
                <div className="flex-1">
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Status</label>
                  <select
                    className="input text-sm"
                    value={statusFilter}
                    onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
                  >
                    <option value="">Alle statussen</option>
                    <option value="completed">Afgerond</option>
                    <option value="missed">Gemist</option>
                    <option value="voicemail">Voicemail</option>
                    <option value="failed">Mislukt</option>
                    <option value="abandoned">Afgebroken</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-xs font-medium text-gray-500 mb-1 block">Uitkomst</label>
                  <select
                    className="input text-sm"
                    value={outcomeFilter}
                    onChange={(e) => { setOutcomeFilter(e.target.value); setPage(1) }}
                  >
                    <option value="">Alle uitkomsten</option>
                    <option value="handled">Afgehandeld</option>
                    <option value="appointment_made">Afspraak gemaakt</option>
                    <option value="appointment_cancelled">Afspraak geannuleerd</option>
                    <option value="info_provided">Info verstrekt</option>
                    <option value="note_left">Notitie achtergelaten</option>
                    <option value="callback_requested">Terugbelverzoek</option>
                    <option value="transferred">Doorverbonden</option>
                    <option value="no_action">Geen actie</option>
                  </select>
                </div>
                {activeFilterCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-5"
                    onClick={() => { setStatusFilter(''); setOutcomeFilter(''); setPage(1) }}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Wissen
                  </Button>
                )}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Calls List */}
        <Card>
          <CardHeader>
            <CardTitle>Gesprekken ({callsData?.total || 0})</CardTitle>
          </CardHeader>
          <CardBody className="p-0">
            {calls.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={Phone}
                  title="Geen gesprekken gevonden"
                  description="Er zijn nog geen gesprekken gevoerd of uw zoekopdracht leverde geen resultaten op."
                />
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {calls.map((call: any) => (
                  <motion.div
                    key={call.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center justify-between p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => setSelectedCall(call)}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-full ${getStatusColor(call.status)}`}>
                        <Phone className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">
                          {call.customer_name || formatPhoneNumber(call.caller_number)}
                        </p>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <Clock className="h-3 w-3" />
                          <span>{formatDateTime(call.started_at)}</span>
                          <span>•</span>
                          <span>{formatDuration(call.duration_seconds)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {call.outcome && (
                        <Badge variant="gray">{call.outcome.replace('_', ' ')}</Badge>
                      )}
                      <Badge
                        variant={
                          call.status === 'completed' ? 'success' :
                          call.status === 'missed' ? 'danger' :
                          call.status === 'voicemail' ? 'warning' : 'gray'
                        }
                      >
                        {getStatusLabel(call.status)}
                      </Badge>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Pagination */}
        {callsData && callsData.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Vorige
            </Button>
            <span className="text-sm text-gray-600">
              Pagina {page} van {callsData.total_pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page === callsData.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Volgende
            </Button>
          </div>
        )}
      </div>

      {/* Call Detail Modal */}
      <Modal
        isOpen={!!selectedCall}
        onClose={() => setSelectedCall(null)}
        title="Gespreksdetails"
        size="xl"
      >
        {detailLoading ? (
          <div className="py-8 flex justify-center">
            <PageLoader />
          </div>
        ) : callDetail ? (
          <div className="space-y-6">
            {/* Call Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Beller</p>
                <p className="font-medium text-gray-900">
                  {callDetail.customer_name || formatPhoneNumber(callDetail.caller_number)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Gebeld nummer</p>
                <p className="font-medium text-gray-900">{formatPhoneNumber(callDetail.called_number)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Datum/tijd</p>
                <p className="font-medium text-gray-900">{formatDateTime(callDetail.started_at)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Duur</p>
                <p className="font-medium text-gray-900">{formatDuration(callDetail.duration_seconds)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">AI-medewerker</p>
                <p className="font-medium text-gray-900">{callDetail.ai_worker_name || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Uitkomst</p>
                <p className="font-medium text-gray-900">{callDetail.outcome?.replace('_', ' ') || '-'}</p>
              </div>
            </div>

            {/* Summary */}
            {callDetail.summary && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Samenvatting</p>
                <div className="p-4 rounded-lg bg-gray-50">
                  <p className="text-sm text-gray-700">{callDetail.summary}</p>
                </div>
              </div>
            )}

            {/* Transcript */}
            {callDetail.transcripts && callDetail.transcripts.length > 0 && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Transcript</p>
                <div className="max-h-80 overflow-y-auto space-y-3 p-4 rounded-lg bg-gray-50">
                  {callDetail.transcripts.map((msg: any, i: number) => (
                    <div
                      key={i}
                      className={`flex ${msg.speaker === 'ai' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-2 ${
                          msg.speaker === 'ai'
                            ? 'bg-primary-100 text-primary-900'
                            : 'bg-white border border-gray-200 text-gray-900'
                        }`}
                      >
                        <p className="text-xs font-medium mb-1">
                          {msg.speaker === 'ai' ? 'AI' : 'Beller'}
                        </p>
                        <p className="text-sm">{msg.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recording */}
            {callDetail.recording_url && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Opname</p>
                <Button variant="outline" leftIcon={<Play className="h-4 w-4" />}>
                  Opname afspelen
                </Button>
              </div>
            )}
          </div>
        ) : null}
      </Modal>
    </DashboardLayout>
  )
}
