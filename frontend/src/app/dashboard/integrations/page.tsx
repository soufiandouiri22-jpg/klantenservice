'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Plus,
  Plug,
  RefreshCw,
  Settings,
  Trash2,
  Check,
  ExternalLink,
  Clock,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { crmApi, aiWorkersApi } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { useAuthStore } from '@/lib/store'

const providers = [
  {
    id: 'salesdock',
    name: 'Salesdock',
    description: 'Koppel uw Salesdock CRM voor contactherkenning en gespreksverslagen',
    color: 'bg-orange-50',
    logo: '/company-logos/salesdock.png',
    available: true,
    authType: 'api_key' as const,
  },
  {
    id: 'saleslane',
    name: 'Saleslane',
    description: 'Koppel uw Saleslane CRM voor contactherkenning bij inkomende gesprekken',
    color: 'bg-blue-50',
    logo: '/company-logos/saleslane.png',
    available: true,
    authType: 'saleslane_jwt' as const,
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'Koppel uw HubSpot CRM voor automatische contactherkenning',
    color: 'bg-orange-100',
    logo: '/company-logos/hubspot.png',
    available: true,
    authType: 'oauth' as const,
  },
]

export default function IntegrationsPage() {
  return (
    <Suspense>
      <IntegrationsPageInner />
    </Suspense>
  )
}

function IntegrationsPageInner() {
  const queryClient = useQueryClient()
  const searchParams = useSearchParams()
  const { user } = useAuthStore()
  const canEdit = user?.role === 'owner' || user?.role === 'admin'
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedIntegration, setSelectedIntegration] = useState<any>(null)
  const [salesdockModal, setSalesdockModal] = useState(false)
  const [salesdockDomain, setSalesdockDomain] = useState('')
  const [salesdockApiKey, setSalesdockApiKey] = useState('')
  const [saleslaneModal, setSaleslaneModal] = useState(false)
  const [saleslanePrefix, setSaleslanePrefix] = useState('')
  const [saleslaneContextId, setSaleslaneContextId] = useState('')
  const [saleslanePrivateKey, setSaleslanePrivateKey] = useState('')

  useEffect(() => {
    if (searchParams.get('connected') === 'true') {
      toast.success('CRM succesvol gekoppeld!')
      queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
      window.history.replaceState({}, '', '/dashboard/integrations')
    }
  }, [searchParams, queryClient])

  const { data: integrations, isLoading } = useQuery({
    queryKey: ['crm-integrations'],
    queryFn: crmApi.list,
  })

  const { data: aiWorkers } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  const createMutation = useMutation({
    mutationFn: async ({ provider, apiKey, accountDomain, apiContextId }: { provider: string; apiKey?: string; accountDomain?: string; apiContextId?: string }) => {
      const providerInfo = providers.find((p) => p.id === provider)
      if (providerInfo?.authType === 'api_key' || providerInfo?.authType === 'saleslane_jwt') {
        await crmApi.create({
          name: providerInfo.name,
          provider,
          api_key: apiKey,
          account_domain: accountDomain,
          api_context_id: apiContextId,
        })
        queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
        toast.success('CRM succesvol gekoppeld!')
      } else {
        const crm = await crmApi.create({
          name: providerInfo?.name || 'CRM',
          provider,
        })
        const response = await crmApi.getOAuthUrl(provider, crm.id)
        window.location.href = response.auth_url
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij starten koppeling')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      crmApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
      toast.success('Instellingen opgeslagen')
    },
  })

  const testMutation = useMutation({
    mutationFn: crmApi.test,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
      toast.success('Verbinding succesvol!')
    },
    onError: () => {
      toast.error('Verbinding mislukt')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: crmApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
      toast.success('Integratie verwijderd')
      setSelectedIntegration(null)
    },
  })

  const getProviderInfo = (provider: string) => {
    return providers.find((p) => p.id === provider) || providers[0]
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
        title="Integraties"
        description="Koppel externe systemen zodat de AI uw klanten herkent en gespreksverslagen terugschrijft."
        hideSearch
        actions={canEdit ? (
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setIsAddModalOpen(true)}
          >
            Integratie toevoegen
          </Button>
        ) : undefined}
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Info */}
        <Card>
          <CardBody>
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-purple-100">
                <Plug className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Hoe werkt het?</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Koppel uw CRM-systeem zodat de AI bij inkomende gesprekken automatisch
                  de beller herkent en persoonlijk begroet. Nieuwe bellers worden automatisch
                  als contact aangemaakt. Na elk gesprek wordt een samenvatting teruggeschreven
                  naar uw CRM. Zo hoeft u niets meer handmatig over te typen.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Integrations List */}
        {integrations?.length === 0 ? (
          <EmptyState
            icon={Plug}
            title="Geen integraties gekoppeld"
            description="Koppel een CRM-systeem zodat de AI uw klanten herkent."
            action={canEdit ? (
              <Button
                leftIcon={<Plus className="h-4 w-4" />}
                onClick={() => setIsAddModalOpen(true)}
              >
                Integratie toevoegen
              </Button>
            ) : undefined}
          />
        ) : (
          <div className="space-y-4">
            {integrations?.map((integration: any) => {
              const providerInfo = getProviderInfo(integration.provider)
              return (
                <motion.div
                  key={integration.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <Card>
                    <CardBody>
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div
                            className={`flex h-12 w-12 items-center justify-center rounded-lg overflow-hidden ${providerInfo.color}`}
                          >
                            <img src={providerInfo.logo} alt={providerInfo.name} className="h-8 w-8 object-contain" />
                          </div>
                          <div>
                            <h3 className="font-medium text-gray-900">
                              {integration.name}
                            </h3>
                            <p className="text-sm text-gray-500">
                              {providerInfo.name} CRM
                            </p>
                            {integration.hubspot_portal_id && (
                              <p className="text-xs text-gray-400 mt-1">
                                Portal ID: {integration.hubspot_portal_id}
                              </p>
                            )}
                            {integration.account_domain && (
                              <p className="text-xs text-gray-400 mt-1">
                                {integration.provider === 'saleslane' ? 'Prefix' : 'Domein'}: {integration.account_domain}
                              </p>
                            )}
                            {integration.api_context_id && (
                              <p className="text-xs text-gray-400 mt-1">
                                Context ID: {integration.api_context_id.slice(0, 12)}...
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          {integration.sync_error ? (
                            <Badge variant="danger">Fout</Badge>
                          ) : integration.is_connected ? (
                            <Badge variant="success">
                              <Check className="h-3 w-3 mr-1" />
                              Verbonden
                            </Badge>
                          ) : (
                            <Badge variant="warning">Niet verbonden</Badge>
                          )}
                        </div>
                      </div>

                      {integration.sync_error && (
                        <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-100">
                          <p className="text-sm text-red-700">
                            {integration.sync_error}
                          </p>
                        </div>
                      )}

                      {/* Feature toggles */}
                      {integration.is_connected && (
                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                          <ToggleCard
                            label="Contact opzoeken"
                            description="Herken bellers automatisch"
                            enabled={integration.sync_contacts_on_call}
                            onChange={(val) =>
                              updateMutation.mutate({
                                id: integration.id,
                                data: { sync_contacts_on_call: val },
                              })
                            }
                          />
                          <ToggleCard
                            label="Gespreksverslag"
                            description="Schrijf samenvatting terug"
                            enabled={integration.write_call_notes}
                            onChange={(val) =>
                              updateMutation.mutate({
                                id: integration.id,
                                data: { write_call_notes: val },
                              })
                            }
                          />
                          <ToggleCard
                            label="Contacten aanmaken"
                            description="Maak nieuwe contacten aan"
                            enabled={integration.auto_create_contacts}
                            onChange={(val) =>
                              updateMutation.mutate({
                                id: integration.id,
                                data: { auto_create_contacts: val },
                              })
                            }
                          />
                        </div>
                      )}

                      <div className="mt-4 flex items-center gap-2 text-xs text-gray-400">
                        <Clock className="h-3 w-3" />
                        <span>
                          Laatst gesynchroniseerd:{' '}
                          {integration.last_sync_at
                            ? formatRelativeTime(integration.last_sync_at)
                            : 'Nooit'}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-3 pt-4 border-t border-gray-100">
                        {!integration.is_connected ? (
                          <Button
                            size="sm"
                            leftIcon={<ExternalLink className="h-4 w-4" />}
                            onClick={async () => {
                              if (providerInfo.authType === 'api_key') {
                                setSalesdockModal(true)
                                setSelectedIntegration(integration)
                                return
                              }
                              if (providerInfo.authType === 'saleslane_jwt') {
                                setSaleslaneModal(true)
                                setSelectedIntegration(integration)
                                return
                              }
                              try {
                                const res = await crmApi.getOAuthUrl(
                                  integration.provider,
                                  integration.id
                                )
                                window.location.href = res.auth_url
                              } catch {
                                toast.error('Fout bij starten OAuth')
                              }
                            }}
                          >
                            Verbinden met {providerInfo.name}
                          </Button>
                        ) : (
                          <>
                            {canEdit && (
                              <Button
                                variant="outline"
                                size="sm"
                                leftIcon={<RefreshCw className="h-4 w-4" />}
                                onClick={() => testMutation.mutate(integration.id)}
                                isLoading={testMutation.isPending}
                              >
                                Test verbinding
                              </Button>
                            )}
                          </>
                        )}
                        <div className="flex-1" />
                        {canEdit && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              if (
                                confirm(
                                  'Weet u zeker dat u deze integratie wilt verwijderen?'
                                )
                              ) {
                                deleteMutation.mutate(integration.id)
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </CardBody>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {/* Add Integration Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Integratie toevoegen"
        description="Kies een CRM-systeem om te koppelen."
        size="lg"
      >
        <div className="grid grid-cols-1 gap-4">
          {providers.map((provider) => (
            <button
              key={provider.id}
              disabled={!provider.available || createMutation.isPending}
              onClick={() => {
                if (!provider.available) return
                if (provider.authType === 'api_key') {
                  setIsAddModalOpen(false)
                  setSalesdockDomain('')
                  setSalesdockApiKey('')
                  setSalesdockModal(true)
                  setSelectedIntegration(null)
                } else if (provider.authType === 'saleslane_jwt') {
                  setIsAddModalOpen(false)
                  setSaleslanePrefix('')
                  setSaleslaneContextId('')
                  setSaleslanePrivateKey('')
                  setSaleslaneModal(true)
                  setSelectedIntegration(null)
                } else {
                  createMutation.mutate({ provider: provider.id })
                }
              }}
              className={`flex items-center gap-4 p-4 rounded-lg border text-left transition-colors ${
                provider.available
                  ? 'border-gray-200 hover:border-primary-300 hover:bg-primary-50 cursor-pointer'
                  : 'border-gray-100 bg-gray-50 cursor-not-allowed opacity-60'
              }`}
            >
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-lg overflow-hidden ${provider.color}`}
              >
                <img src={provider.logo} alt={provider.name} className="h-8 w-8 object-contain" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-gray-900">{provider.name}</h4>
                  {!provider.available && (
                    <Badge variant="gray">Binnenkort</Badge>
                  )}
                </div>
                <p className="text-sm text-gray-500">{provider.description}</p>
              </div>
            </button>
          ))}
        </div>
      </Modal>

      {/* Salesdock API Key Modal */}
      <Modal
        isOpen={salesdockModal}
        onClose={() => {
          setSalesdockModal(false)
          setSelectedIntegration(null)
        }}
        title="Salesdock koppelen"
        description="Voer uw Salesdock account domein en API key in."
        size="md"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            if (!salesdockDomain.trim() || !salesdockApiKey.trim()) {
              toast.error('Vul beide velden in')
              return
            }
            try {
              if (selectedIntegration) {
                await crmApi.update(selectedIntegration.id, {
                  api_key: salesdockApiKey.trim(),
                  account_domain: salesdockDomain.trim(),
                })
                queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
                toast.success('Salesdock gekoppeld!')
              } else {
                await createMutation.mutateAsync({
                  provider: 'salesdock',
                  apiKey: salesdockApiKey.trim(),
                  accountDomain: salesdockDomain.trim(),
                })
              }
              setSalesdockModal(false)
              setSalesdockDomain('')
              setSalesdockApiKey('')
              setSelectedIntegration(null)
            } catch (err: any) {
              toast.error(err.response?.data?.detail || 'Koppeling mislukt')
            }
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Account domein
            </label>
            <input
              type="text"
              value={salesdockDomain}
              onChange={(e) => setSalesdockDomain(e.target.value)}
              placeholder="bijv. mijnbedrijf"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">
              Het deel na de / in uw Salesdock URL (app.salesdock.nl/uw-domein)
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API key
            </label>
            <input
              type="password"
              value={salesdockApiKey}
              onChange={(e) => setSalesdockApiKey(e.target.value)}
              placeholder="Plak uw API token"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">
              Genereer een token via Account &gt; Gebruikers &gt; API Token
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              type="button"
              onClick={() => {
                setSalesdockModal(false)
                setSelectedIntegration(null)
              }}
            >
              Annuleren
            </Button>
            <Button type="submit" isLoading={createMutation.isPending}>
              Koppelen
            </Button>
          </div>
        </form>
      </Modal>

      {/* Saleslane JWT Modal */}
      <Modal
        isOpen={saleslaneModal}
        onClose={() => {
          setSaleslaneModal(false)
          setSelectedIntegration(null)
        }}
        title="Saleslane koppelen"
        description="Voer uw Saleslane client prefix, API Context ID en RSA private key in."
        size="md"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            if (!saleslanePrefix.trim() || !saleslaneContextId.trim() || !saleslanePrivateKey.trim()) {
              toast.error('Vul alle velden in')
              return
            }
            try {
              if (selectedIntegration) {
                await crmApi.update(selectedIntegration.id, {
                  api_key: saleslanePrivateKey.trim(),
                  account_domain: saleslanePrefix.trim(),
                  api_context_id: saleslaneContextId.trim(),
                })
                queryClient.invalidateQueries({ queryKey: ['crm-integrations'] })
                toast.success('Saleslane gekoppeld!')
              } else {
                await createMutation.mutateAsync({
                  provider: 'saleslane',
                  apiKey: saleslanePrivateKey.trim(),
                  accountDomain: saleslanePrefix.trim(),
                  apiContextId: saleslaneContextId.trim(),
                })
              }
              setSaleslaneModal(false)
              setSaleslanePrefix('')
              setSaleslaneContextId('')
              setSaleslanePrivateKey('')
              setSelectedIntegration(null)
            } catch (err: any) {
              toast.error(err.response?.data?.detail || 'Koppeling mislukt')
            }
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Client prefix
            </label>
            <input
              type="text"
              value={saleslanePrefix}
              onChange={(e) => setSaleslanePrefix(e.target.value)}
              placeholder="bijv. mijnbedrijf"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">
              Het deel voor .saleslane.nl in uw URL (mijnbedrijf.saleslane.nl)
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Context ID
            </label>
            <input
              type="text"
              value={saleslaneContextId}
              onChange={(e) => setSaleslaneContextId(e.target.value)}
              placeholder="Plak uw API Context ID"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">
              Te vinden in de Saleslane API App instellingen
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              RSA Private Key (PEM)
            </label>
            <textarea
              value={saleslanePrivateKey}
              onChange={(e) => setSaleslanePrivateKey(e.target.value)}
              placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
              rows={5}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none resize-none"
            />
            <p className="mt-1 text-xs text-gray-400">
              Genereer via: openssl genpkey -algorithm RSA -out private_key.pem -pkeyopt rsa_keygen_bits:2048
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              type="button"
              onClick={() => {
                setSaleslaneModal(false)
                setSelectedIntegration(null)
              }}
            >
              Annuleren
            </Button>
            <Button type="submit" isLoading={createMutation.isPending}>
              Koppelen
            </Button>
          </div>
        </form>
      </Modal>
    </DashboardLayout>
  )
}

function ToggleCard({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string
  description: string
  enabled: boolean
  onChange: (val: boolean) => void
}) {
  return (
    <div
      className="flex items-center justify-between p-3 rounded-lg border border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
      onClick={() => onChange(!enabled)}
    >
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <div
        className={`relative h-5 w-9 rounded-full transition-colors ${
          enabled ? 'bg-primary-600' : 'bg-gray-200'
        }`}
      >
        <div
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
            enabled ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </div>
    </div>
  )
}
