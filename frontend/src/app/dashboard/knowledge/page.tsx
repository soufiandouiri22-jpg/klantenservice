'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Globe, RefreshCw, Search, Check, AlertCircle, Clock, Trash2, ExternalLink } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Select'
import { websitesApi, aiWorkersApi } from '@/lib/api'
import { formatRelativeTime, getStatusLabel } from '@/lib/utils'

export default function KnowledgePage() {
  const queryClient = useQueryClient()
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isTestModalOpen, setIsTestModalOpen] = useState(false)
  const [selectedWebsite, setSelectedWebsite] = useState<any>(null)
  const [newUrl, setNewUrl] = useState('')
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>('')
  const [testQuestion, setTestQuestion] = useState('')
  const [testResult, setTestResult] = useState<any>(null)

  const { data: websites, isLoading } = useQuery({
    queryKey: ['websites'],
    queryFn: websitesApi.list,
    refetchInterval: (query) => {
      const data = query.state.data as any[] | undefined
      return data?.some((w: any) => w.status === 'indexing') ? 3000 : false
    },
  })

  const { data: workers } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  // Filter workers that don't already have a website linked
  const availableWorkers = workers?.filter((w: any) => !w.linked_website) || []

  const createMutation = useMutation({
    mutationFn: websitesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('Website toegevoegd en indexering gestart')
      setIsAddModalOpen(false)
      setNewUrl('')
      setSelectedWorkerId('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij toevoegen')
    },
  })

  const reindexMutation = useMutation({
    mutationFn: websitesApi.reindex,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      toast.success('Opnieuw indexeren gestart')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij indexeren')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: websitesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['websites'] })
      toast.success('Website verwijderd')
    },
  })

  const testMutation = useMutation({
    mutationFn: ({ id, question }: { id: string; question: string }) =>
      websitesApi.testQuestion(id, question),
    onSuccess: (data) => {
      setTestResult(data)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij testen')
    },
  })

  const handleAddWebsite = () => {
    if (!newUrl.trim()) {
      toast.error('Voer een URL in')
      return
    }
    if (!selectedWorkerId) {
      toast.error('Selecteer een AI-medewerker')
      return
    }
    
    // Auto-add https:// if no protocol specified
    let url = newUrl.trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'https://' + url
    }
    
    createMutation.mutate({ base_url: url, ai_worker_id: selectedWorkerId })
  }

  const handleTestQuestion = () => {
    if (!testQuestion.trim() || !selectedWebsite) return
    testMutation.mutate({ id: selectedWebsite.id, question: testQuestion })
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'gray'> = {
      completed: 'success',
      indexing: 'warning',
      pending: 'gray',
      failed: 'danger',
    }
    return variants[status] || 'gray'
  }

  return (
    <DashboardLayout>
      <Header
        title="Website-kennis"
        description="Beheer de websites waarvan de AI leert."
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsAddModalOpen(true)}
          >
            Website toevoegen
          </Button>
        }
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Info Card */}
        <Card>
          <CardBody>
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary-100">
                <Globe className="h-5 w-5 text-primary-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Hoe werkt het?</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Voeg uw website toe en de AI indexeert automatisch alle publieke pagina's. 
                  De AI gebruikt deze informatie om vragen van bellers te beantwoorden over uw 
                  diensten, prijzen, openingstijden en meer.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Websites List */}
        {websites?.length === 0 ? (
          <EmptyState
            icon={Globe}
            title="Geen websites gekoppeld"
            description="Voeg uw website toe zodat de AI automatisch kan leren van uw content."
            action={
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsAddModalOpen(true)}>
                Website toevoegen
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            {websites?.map((website: any) => (
              <motion.div
                key={website.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card>
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4 min-w-0">
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-gray-100">
                          <Globe className="h-6 w-6 text-gray-600" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium text-gray-900 truncate">{website.base_url}</h3>
                            <a
                              href={website.base_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex-shrink-0 text-gray-400 hover:text-gray-600"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </div>
                          <div className="mt-1 flex items-center gap-4 text-sm text-gray-500">
                            <span>{website.pages_indexed} pagina's geïndexeerd</span>
                            <span>•</span>
                            <span>{website.chunks_created} tekstblokken</span>
                          </div>
                          {website.last_indexed_at && (
                            <p className="mt-1 text-xs text-gray-400">
                              Laatst geïndexeerd: {formatRelativeTime(website.last_indexed_at)}
                            </p>
                          )}
                          <p className="mt-1 text-xs text-gray-400">
                            Gekoppeld aan: {workers?.find((w: any) => w.id === website.ai_worker_id)?.name || 'Geen medewerker'}
                          </p>
                        </div>
                      </div>
                      <div className="flex-shrink-0 ml-3">
                        <Badge variant={getStatusBadge(website.status)}>
                          {website.status === 'completed' && <Check className="h-3 w-3 mr-1" />}
                          {website.status === 'indexing' && <RefreshCw className="h-3 w-3 mr-1 animate-spin" />}
                          {website.status === 'failed' && <AlertCircle className="h-3 w-3 mr-1" />}
                          {getStatusLabel(website.status)}
                        </Badge>
                      </div>
                    </div>

                    {website.last_error && (
                      <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-100 overflow-hidden">
                        <p className="text-sm text-red-700 break-words">{website.last_error}</p>
                      </div>
                    )}

                    <div className="mt-4 flex flex-wrap items-center gap-3 pt-4 border-t border-gray-100">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<Search className="h-4 w-4" />}
                        onClick={() => {
                          setSelectedWebsite(website)
                          setIsTestModalOpen(true)
                          setTestResult(null)
                          setTestQuestion('')
                        }}
                        disabled={website.status !== 'completed'}
                      >
                        Testvraag
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<RefreshCw className="h-4 w-4" />}
                        onClick={() => reindexMutation.mutate(website.id)}
                        disabled={website.status === 'indexing'}
                      >
                        Herindexeren
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (confirm('Weet u zeker dat u deze website wilt verwijderen?')) {
                            deleteMutation.mutate(website.id)
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Add Website Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Website toevoegen"
        description="Voer de URL van uw website in. De AI indexeert automatisch alle publieke pagina's."
      >
        <div className="space-y-4">
          <Input
            label="Website URL"
            placeholder="https://www.uwwebsite.nl"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Koppel aan AI-medewerker
            </label>
            {availableWorkers.length === 0 ? (
              <p className="text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
                Alle AI-medewerkers hebben al een website gekoppeld. Maak eerst een nieuwe medewerker aan of ontkoppel een bestaande website.
              </p>
            ) : (
              <Select
                value={selectedWorkerId}
                onChange={(e) => setSelectedWorkerId(e.target.value)}
              >
                <option value="">Selecteer een medewerker...</option>
                {availableWorkers.map((w: any) => (
                  <option key={w.id} value={w.id}>{w.name} — {w.role_title}</option>
                ))}
              </Select>
            )}
          </div>
          <div className="rounded-lg bg-gray-50 p-4">
            <p className="text-sm text-gray-600">
              <strong>Let op:</strong> De AI respecteert uw robots.txt en indexeert alleen publieke pagina's. 
              Elke AI-medewerker kan aan maximaal 1 website worden gekoppeld.
            </p>
          </div>
          <div className="flex gap-3 pt-4">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => setIsAddModalOpen(false)}
            >
              Annuleren
            </Button>
            <Button
              className="flex-1"
              onClick={handleAddWebsite}
              isLoading={createMutation.isPending}
              disabled={!selectedWorkerId || availableWorkers.length === 0}
            >
              Toevoegen & Indexeren
            </Button>
          </div>
        </div>
      </Modal>

      {/* Test Question Modal */}
      <Modal
        isOpen={isTestModalOpen}
        onClose={() => {
          setIsTestModalOpen(false)
          setTestResult(null)
        }}
        title="Testvraag stellen"
        description="Test of de AI uw vraag kan beantwoorden op basis van de geïndexeerde content."
        size="lg"
      >
        <div className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Stel een vraag..."
              value={testQuestion}
              onChange={(e) => setTestQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleTestQuestion()}
            />
            <Button
              onClick={handleTestQuestion}
              isLoading={testMutation.isPending}
            >
              Verstuur
            </Button>
          </div>

          {testResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <div className="p-4 rounded-lg bg-primary-50 border border-primary-100">
                <p className="text-sm font-medium text-primary-900 mb-2">Antwoord:</p>
                <p className="text-primary-800">{testResult.answer}</p>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Bronnen:</p>
                <div className="space-y-2">
                  {testResult.sources?.map((source: any, i: number) => (
                    <div key={i} className="p-3 rounded-lg bg-gray-50 text-sm">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 hover:underline"
                      >
                        {source.url}
                      </a>
                      <p className="mt-1 text-gray-500">{source.snippet}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>Betrouwbaarheid: {Math.round(testResult.confidence * 100)}%</span>
              </div>
            </motion.div>
          )}
        </div>
      </Modal>
    </DashboardLayout>
  )
}
