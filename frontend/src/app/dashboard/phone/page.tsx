'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, Phone, Settings, Clock, VoicemailIcon, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { phoneNumbersApi } from '@/lib/api'
import { formatPhoneNumber } from '@/lib/utils'

const days = [
  { key: 'monday', label: 'Maandag' },
  { key: 'tuesday', label: 'Dinsdag' },
  { key: 'wednesday', label: 'Woensdag' },
  { key: 'thursday', label: 'Donderdag' },
  { key: 'friday', label: 'Vrijdag' },
  { key: 'saturday', label: 'Zaterdag' },
  { key: 'sunday', label: 'Zondag' },
]

export default function PhonePage() {
  const queryClient = useQueryClient()
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedPhone, setSelectedPhone] = useState<any>(null)
  const [newNumber, setNewNumber] = useState('')
  const [newFriendlyName, setNewFriendlyName] = useState('')

  const { data: phoneNumbers, isLoading } = useQuery({
    queryKey: ['phone-numbers'],
    queryFn: phoneNumbersApi.list,
  })

  const createMutation = useMutation({
    mutationFn: phoneNumbersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Telefoonnummer toegevoegd')
      setIsAddModalOpen(false)
      setNewNumber('')
      setNewFriendlyName('')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij toevoegen')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      phoneNumbersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Instellingen opgeslagen')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: phoneNumbersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['phone-numbers'] })
      toast.success('Telefoonnummer verwijderd')
      setSelectedPhone(null)
    },
  })

  const handleAddNumber = () => {
    if (!newNumber.trim()) {
      toast.error('Voer een telefoonnummer in')
      return
    }
    createMutation.mutate({
      number: newNumber,
      friendly_name: newFriendlyName || undefined,
    })
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <Header
        title="Telefonie"
        description="Beheer uw telefoonnummers en openingstijden."
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsAddModalOpen(true)}
          >
            Nummer toevoegen
          </Button>
        }
      />

      <div className="p-6 space-y-6">
        {phoneNumbers?.length === 0 ? (
          <EmptyState
            icon={Phone}
            title="Geen telefoonnummers"
            description="Voeg een telefoonnummer toe om gesprekken te kunnen ontvangen."
            action={
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsAddModalOpen(true)}>
                Nummer toevoegen
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {phoneNumbers?.map((phone: any) => (
              <motion.div
                key={phone.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card>
                  <CardBody>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                          <Phone className="h-6 w-6 text-primary-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">
                            {formatPhoneNumber(phone.number)}
                          </h3>
                          <p className="text-sm text-gray-500">
                            {phone.friendly_name || 'Hoofdnummer'}
                          </p>
                        </div>
                      </div>
                      <Badge variant={phone.is_active ? 'success' : 'gray'}>
                        {phone.is_active ? 'Actief' : 'Inactief'}
                      </Badge>
                    </div>

                    {/* Business Hours Preview */}
                    <div className="mt-4 p-3 rounded-lg bg-gray-50">
                      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                        <Clock className="h-4 w-4" />
                        <span className="font-medium">Openingstijden</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {days.slice(0, 5).map((day) => {
                          const hours = phone.business_hours?.[day.key]
                          return (
                            <div key={day.key} className="flex justify-between">
                              <span className="text-gray-500">{day.label.slice(0, 2)}</span>
                              <span className="text-gray-900">
                                {hours?.enabled ? `${hours.open} - ${hours.close}` : 'Gesloten'}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    <div className="mt-4 flex items-center gap-3 pt-4 border-t border-gray-100">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<Settings className="h-4 w-4" />}
                        onClick={() => setSelectedPhone(phone)}
                      >
                        Instellingen
                      </Button>
                      <div className="flex-1" />
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <VoicemailIcon className="h-4 w-4" />
                        <span>{phone.voicemail_enabled ? 'Voicemail aan' : 'Voicemail uit'}</span>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Add Number Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Telefoonnummer toevoegen"
        description="Voeg een nieuw telefoonnummer toe aan uw account."
      >
        <div className="space-y-4">
          <Input
            label="Telefoonnummer"
            placeholder="+31 20 123 4567"
            value={newNumber}
            onChange={(e) => setNewNumber(e.target.value)}
          />
          <Input
            label="Naam (optioneel)"
            placeholder="bijv. Hoofdnummer, Support"
            value={newFriendlyName}
            onChange={(e) => setNewFriendlyName(e.target.value)}
          />
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
              onClick={handleAddNumber}
              isLoading={createMutation.isPending}
            >
              Toevoegen
            </Button>
          </div>
        </div>
      </Modal>

      {/* Settings Modal */}
      <Modal
        isOpen={!!selectedPhone}
        onClose={() => setSelectedPhone(null)}
        title={`Instellingen: ${selectedPhone?.friendly_name || formatPhoneNumber(selectedPhone?.number || '')}`}
        size="lg"
      >
        {selectedPhone && (
          <div className="space-y-6">
            {/* Business Hours */}
            <div>
              <h4 className="font-medium text-gray-900 mb-4">Openingstijden</h4>
              <div className="space-y-3">
                {days.map((day) => {
                  const hours = selectedPhone.business_hours?.[day.key] || {}
                  return (
                    <div key={day.key} className="flex items-center gap-4">
                      <div className="w-24">
                        <span className="text-sm text-gray-600">{day.label}</span>
                      </div>
                      <Toggle
                        enabled={hours.enabled ?? false}
                        onChange={() => {}}
                      />
                      {hours.enabled && (
                        <>
                          <Input
                            className="w-24"
                            type="time"
                            defaultValue={hours.open || '09:00'}
                          />
                          <span className="text-gray-400">-</span>
                          <Input
                            className="w-24"
                            type="time"
                            defaultValue={hours.close || '17:00'}
                          />
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Voicemail */}
            <div>
              <h4 className="font-medium text-gray-900 mb-4">Voicemail</h4>
              <div className="space-y-4">
                <Toggle
                  enabled={selectedPhone.voicemail_enabled}
                  onChange={() => {}}
                  label="Voicemail inschakelen"
                  description="Bellers kunnen een bericht achterlaten als alle AI-medewerkers bezet zijn."
                />
                <div>
                  <label className="label">Voicemail begroeting</label>
                  <textarea
                    className="input min-h-[80px] resize-none"
                    defaultValue={selectedPhone.voicemail_greeting}
                    placeholder="U kunt na de piep een bericht achterlaten..."
                  />
                </div>
                <Input
                  label="Voicemail e-mail"
                  type="email"
                  defaultValue={selectedPhone.voicemail_email}
                  placeholder="voicemail@uwbedrijf.nl"
                  helperText="Ontvang transcripties van voicemails per e-mail"
                />
              </div>
            </div>

            {/* After Hours */}
            <div>
              <h4 className="font-medium text-gray-900 mb-4">Buiten openingstijden</h4>
              <div>
                <label className="label">Bericht buiten openingstijden</label>
                <textarea
                  className="input min-h-[80px] resize-none"
                  defaultValue={selectedPhone.after_hours_message}
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => {
                  if (confirm('Weet u zeker dat u dit nummer wilt verwijderen?')) {
                    deleteMutation.mutate(selectedPhone.id)
                  }
                }}
              >
                Verwijderen
              </Button>
              <Button onClick={() => setSelectedPhone(null)}>
                Sluiten
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
