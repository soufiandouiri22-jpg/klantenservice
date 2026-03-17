'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, FileText, Search, Check, RotateCcw, Trash2, AlertTriangle, Phone, Mail, User } from 'lucide-react'
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
import { notesApi } from '@/lib/api'
import { formatRelativeTime, getPriorityLabel, getPriorityColor } from '@/lib/utils'
import { useAuthStore } from '@/lib/store'

export default function NotesPage() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role !== 'viewer'
  const [page, setPage] = useState(1)
  const [selectedNote, setSelectedNote] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showResolved, setShowResolved] = useState(false)
  const [actionRequiredOnly, setActionRequiredOnly] = useState(false)
  const [resolutionNotes, setResolutionNotes] = useState('')

  const { data: notesData, isLoading } = useQuery({
    queryKey: ['notes', page, searchQuery, showResolved, actionRequiredOnly],
    queryFn: () => notesApi.list({
      page,
      page_size: 20,
      search: searchQuery || undefined,
      is_resolved: showResolved ? undefined : false,
      action_required: actionRequiredOnly ? true : undefined,
    }),
  })

  const { data: actionRequired } = useQuery({
    queryKey: ['notes-action-required'],
    queryFn: notesApi.getActionRequired,
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      notesApi.resolve(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      queryClient.invalidateQueries({ queryKey: ['notes-action-required'] })
      toast.success('Notitie gemarkeerd als opgelost')
      setSelectedNote(null)
      setResolutionNotes('')
    },
  })

  const reopenMutation = useMutation({
    mutationFn: notesApi.reopen,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('Notitie heropend')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: notesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('Notitie verwijderd')
      setSelectedNote(null)
    },
  })

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const notes = notesData?.items || []

  return (
    <DashboardLayout>
      <Header
        title="Notities"
        description="Interne notities achtergelaten door de AI-medewerkers."
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Action Required Alert */}
        {actionRequired && actionRequired.length > 0 && !actionRequiredOnly && (
          <Card className="border-amber-200 bg-amber-50">
            <CardBody>
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-amber-900">
                    {actionRequired.length} notitie(s) vereisen actie
                  </h3>
                  <p className="mt-1 text-sm text-amber-700">
                    Er zijn terugbelverzoeken of andere acties die uw aandacht nodig hebben.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setActionRequiredOnly(true)}
                >
                  Bekijken
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Filters */}
        <Card>
          <CardBody>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Zoek in notities..."
                  className="input pl-10"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={actionRequiredOnly}
                    onChange={(e) => setActionRequiredOnly(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600">Alleen actie vereist</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={showResolved}
                    onChange={(e) => setShowResolved(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-600">Toon opgeloste</span>
                </label>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Notes List */}
        <Card>
          <CardHeader>
            <CardTitle>Notities ({notesData?.total || 0})</CardTitle>
          </CardHeader>
          <CardBody className="p-0">
            {notes.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={FileText}
                  title="Geen notities gevonden"
                  description="Er zijn nog geen notities of uw zoekopdracht leverde geen resultaten op."
                />
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {notes.map((note: any) => (
                  <motion.div
                    key={note.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={`p-4 hover:bg-gray-50 cursor-pointer ${note.is_resolved ? 'opacity-60' : ''}`}
                    onClick={() => setSelectedNote(note)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-gray-900">{note.title}</h3>
                          {note.action_required && !note.is_resolved && (
                            <Badge variant="warning">Actie vereist</Badge>
                          )}
                          {note.is_resolved && (
                            <Badge variant="success">
                              <Check className="h-3 w-3 mr-1" />
                              Opgelost
                            </Badge>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-gray-600 line-clamp-2">{note.content}</p>
                        <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                          {note.customer_name && (
                            <span className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {note.customer_name}
                            </span>
                          )}
                          {note.customer_phone && (
                            <span className="flex items-center gap-1">
                              <Phone className="h-3 w-3" />
                              {note.customer_phone}
                            </span>
                          )}
                          <span>{formatRelativeTime(note.created_at)}</span>
                        </div>
                      </div>
                      <Badge className={getPriorityColor(note.priority)}>
                        {getPriorityLabel(note.priority)}
                      </Badge>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Pagination */}
        {notesData && notesData.total_pages > 1 && (
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
              Pagina {page} van {notesData.total_pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page === notesData.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Volgende
            </Button>
          </div>
        )}
      </div>

      {/* Note Detail Modal */}
      <Modal
        isOpen={!!selectedNote}
        onClose={() => {
          setSelectedNote(null)
          setResolutionNotes('')
        }}
        title={selectedNote?.title || 'Notitie'}
        size="lg"
      >
        {selectedNote && (
          <div className="space-y-6">
            {/* Status & Priority */}
            <div className="flex items-center gap-3">
              <Badge className={getPriorityColor(selectedNote.priority)}>
                {getPriorityLabel(selectedNote.priority)}
              </Badge>
              {selectedNote.action_required && !selectedNote.is_resolved && (
                <Badge variant="warning">Actie vereist</Badge>
              )}
              {selectedNote.is_resolved && (
                <Badge variant="success">
                  <Check className="h-3 w-3 mr-1" />
                  Opgelost
                </Badge>
              )}
            </div>

            {/* Content */}
            <div>
              <p className="text-sm text-gray-500 mb-2">Inhoud</p>
              <div className="p-4 rounded-lg bg-gray-50">
                <p className="text-gray-700 whitespace-pre-wrap">{selectedNote.content}</p>
              </div>
            </div>

            {/* Action Description */}
            {selectedNote.action_description && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Gevraagde actie</p>
                <div className="p-4 rounded-lg bg-amber-50 border border-amber-100">
                  <p className="text-amber-800">{selectedNote.action_description}</p>
                </div>
              </div>
            )}

            {/* Customer Info */}
            {(selectedNote.customer_name || selectedNote.customer_phone || selectedNote.customer_email) && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Klantgegevens</p>
                <div className="space-y-2">
                  {selectedNote.customer_name && (
                    <div className="flex items-center gap-2 text-sm">
                      <User className="h-4 w-4 text-gray-400" />
                      <span>{selectedNote.customer_name}</span>
                    </div>
                  )}
                  {selectedNote.customer_phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-gray-400" />
                      <a href={`tel:${selectedNote.customer_phone}`} className="text-primary-600 hover:underline">
                        {selectedNote.customer_phone}
                      </a>
                    </div>
                  )}
                  {selectedNote.customer_email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="h-4 w-4 text-gray-400" />
                      <a href={`mailto:${selectedNote.customer_email}`} className="text-primary-600 hover:underline">
                        {selectedNote.customer_email}
                      </a>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Resolution Notes */}
            {selectedNote.is_resolved && selectedNote.resolution_notes && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Oplossing</p>
                <div className="p-4 rounded-lg bg-green-50 border border-green-100">
                  <p className="text-green-800">{selectedNote.resolution_notes}</p>
                </div>
              </div>
            )}

            {/* Resolve Form */}
            {!selectedNote.is_resolved && (
              <div>
                <label className="label">Notities bij oplossing (optioneel)</label>
                <textarea
                  className="input min-h-[80px] resize-none"
                  placeholder="Beschrijf wat u heeft gedaan..."
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                />
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              {canEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => {
                    if (confirm('Weet u zeker dat u deze notitie wilt verwijderen?')) {
                      deleteMutation.mutate(selectedNote.id)
                    }
                  }}
                >
                  <span className="hidden sm:inline">Verwijderen</span>
                </Button>
              )}
              <div className="flex items-center gap-2 sm:gap-3">
                <Button variant="outline" onClick={() => setSelectedNote(null)}>
                  Sluiten
                </Button>
                {canEdit && (selectedNote.is_resolved ? (
                  <Button
                    leftIcon={<RotateCcw className="h-4 w-4" />}
                    onClick={() => reopenMutation.mutate(selectedNote.id)}
                    isLoading={reopenMutation.isPending}
                  >
                    Heropenen
                  </Button>
                ) : (
                  <Button
                    leftIcon={<Check className="h-4 w-4" />}
                    onClick={() => resolveMutation.mutate({ id: selectedNote.id, notes: resolutionNotes })}
                    isLoading={resolveMutation.isPending}
                  >
                    Markeer als opgelost
                  </Button>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
