'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Headphones, MoreVertical, Settings, Trash2, Power } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { aiWorkersApi } from '@/lib/api'
import { getStatusLabel, getStatusColor } from '@/lib/utils'
import { useAuthStore } from '@/lib/store'

export default function AIWorkersPage() {
  const queryClient = useQueryClient()
  const { company } = useAuthStore()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [selectedWorker, setSelectedWorker] = useState<any>(null)
  const [newWorkerName, setNewWorkerName] = useState('')
  const [newWorkerRole, setNewWorkerRole] = useState('Klantenservice medewerker')

  const { data: workers, isLoading } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  const createMutation = useMutation({
    mutationFn: aiWorkersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('AI-medewerker aangemaakt')
      setIsCreateModalOpen(false)
      setNewWorkerName('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij aanmaken')
    },
  })

  const toggleMutation = useMutation({
    mutationFn: aiWorkersApi.toggleStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('Status bijgewerkt')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij bijwerken status')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: aiWorkersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      toast.success('AI-medewerker verwijderd')
      setSelectedWorker(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij verwijderen')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => aiWorkersApi.update(id, data),
    onSuccess: (updatedWorker) => {
      queryClient.invalidateQueries({ queryKey: ['ai-workers'] })
      setSelectedWorker(updatedWorker)
      toast.success('Instellingen opgeslagen')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij opslaan')
    },
  })

  const handleSettingChange = (field: string, value: any) => {
    if (!selectedWorker) return
    
    // Check if it's a behavior setting or a direct field
    if (field.startsWith('behavior_settings.')) {
      const settingKey = field.replace('behavior_settings.', '')
      const newBehaviorSettings = {
        ...selectedWorker.behavior_settings,
        [settingKey]: value,
      }
      updateMutation.mutate({
        id: selectedWorker.id,
        data: { behavior_settings: newBehaviorSettings },
      })
    } else {
      updateMutation.mutate({
        id: selectedWorker.id,
        data: { [field]: value },
      })
    }
  }

  const handleCreate = () => {
    if (!newWorkerName.trim()) {
      toast.error('Voer een naam in')
      return
    }
    createMutation.mutate({
      name: newWorkerName,
      role_title: newWorkerRole,
    })
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const canAddWorker = workers?.length < (company?.max_ai_workers || 1)

  return (
    <DashboardLayout>
      <Header
        title="AI-medewerkers"
        description={`${workers?.length || 0} van ${company?.max_ai_workers || 1} medewerkers actief`}
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsCreateModalOpen(true)}
            disabled={!canAddWorker}
          >
            Nieuwe medewerker
          </Button>
        }
      />

      <div className="p-6">
        {workers?.length === 0 ? (
          <EmptyState
            icon={Headphones}
            title="Geen AI-medewerkers"
            description="Maak uw eerste AI-medewerker aan om gesprekken te kunnen voeren."
            action={
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsCreateModalOpen(true)}>
                Eerste medewerker aanmaken
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workers?.map((worker: any, index: number) => (
              <motion.div
                key={worker.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="hover:shadow-soft-lg transition-shadow">
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-100">
                          <Headphones className="h-7 w-7 text-primary-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{worker.name}</h3>
                          <p className="text-sm text-gray-500">{worker.role_title}</p>
                        </div>
                      </div>
                      <Badge
                        variant={
                          worker.status === 'available' ? 'success' :
                          worker.status === 'busy' ? 'warning' : 'gray'
                        }
                      >
                        {getStatusLabel(worker.status)}
                      </Badge>
                    </div>

                    <div className="mt-6 grid grid-cols-2 gap-4 text-center">
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-2xl font-bold text-gray-900">{worker.total_calls_handled}</p>
                        <p className="text-xs text-gray-500">Gesprekken</p>
                      </div>
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-2xl font-bold text-gray-900">{worker.total_appointments_made}</p>
                        <p className="text-xs text-gray-500">Afspraken</p>
                      </div>
                    </div>

                    <div className="mt-6 flex items-center justify-between pt-4 border-t border-gray-100">
                      <Toggle
                        enabled={worker.is_active}
                        onChange={() => toggleMutation.mutate(worker.id)}
                        label={worker.is_active ? 'Actief' : 'Inactief'}
                      />
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<Settings className="h-4 w-4" />}
                          onClick={() => setSelectedWorker(worker)}
                        >
                          Instellingen
                        </Button>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </div>
        )}

        {!canAddWorker && workers?.length > 0 && (
          <div className="mt-6 rounded-lg bg-amber-50 border border-amber-200 p-4">
            <p className="text-sm text-amber-800">
              U heeft het maximum aantal AI-medewerkers voor uw abonnement bereikt. 
              <a href="/dashboard/settings" className="font-medium underline ml-1">
                Upgrade uw abonnement
              </a>
              {' '}voor meer medewerkers.
            </p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nieuwe AI-medewerker"
        description="Geef uw nieuwe AI-medewerker een naam en rol."
      >
        <div className="space-y-4">
          <Input
            label="Naam"
            placeholder="bijv. Anna"
            value={newWorkerName}
            onChange={(e) => setNewWorkerName(e.target.value)}
          />
          <Input
            label="Rol / Functie"
            placeholder="bijv. Klantenservice medewerker"
            value={newWorkerRole}
            onChange={(e) => setNewWorkerRole(e.target.value)}
          />
          <div className="flex gap-3 pt-4">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Annuleren
            </Button>
            <Button
              className="flex-1"
              onClick={handleCreate}
              isLoading={createMutation.isPending}
            >
              Aanmaken
            </Button>
          </div>
        </div>
      </Modal>

      {/* Settings Modal */}
      <Modal
        isOpen={!!selectedWorker}
        onClose={() => setSelectedWorker(null)}
        title={`Instellingen: ${selectedWorker?.name}`}
        size="lg"
      >
        {selectedWorker && (
          <div className="space-y-6">
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Gedragsinstellingen</h4>
              <Toggle
                enabled={selectedWorker.behavior_settings?.apologize_on_complaints ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.apologize_on_complaints', value)}
                label="Excuses bij klachten"
                description="Bied automatisch excuses aan bij klachten"
              />
              <Toggle
                enabled={selectedWorker.behavior_settings?.always_offer_alternatives ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.always_offer_alternatives', value)}
                label="Altijd alternatieven aanbieden"
                description="Bied een alternatief aan als iets niet mogelijk is"
              />
              <Toggle
                enabled={selectedWorker.behavior_settings?.never_guess ?? true}
                onChange={(value) => handleSettingChange('behavior_settings.never_guess', value)}
                label="Nooit gokken"
                description="Geef alleen antwoord als de AI zeker is"
              />
            </div>

            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Rechten</h4>
              <Toggle
                enabled={selectedWorker.can_make_appointments}
                onChange={(value) => handleSettingChange('can_make_appointments', value)}
                label="Afspraken maken"
                description="Mag afspraken inplannen in de agenda"
              />
              <Toggle
                enabled={selectedWorker.can_cancel_appointments}
                onChange={(value) => handleSettingChange('can_cancel_appointments', value)}
                label="Afspraken annuleren"
                description="Mag bestaande afspraken annuleren"
              />
              <Toggle
                enabled={selectedWorker.can_leave_notes}
                onChange={(value) => handleSettingChange('can_leave_notes', value)}
                label="Notities achterlaten"
                description="Mag interne notities maken"
              />
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => {
                  if (confirm('Weet u zeker dat u deze medewerker wilt verwijderen?')) {
                    deleteMutation.mutate(selectedWorker.id)
                  }
                }}
              >
                Verwijderen
              </Button>
              <Button onClick={() => setSelectedWorker(null)}>
                Sluiten
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
