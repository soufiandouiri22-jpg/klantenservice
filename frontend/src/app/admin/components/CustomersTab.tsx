'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Search,
  AlertTriangle,
  Power,
  Settings,
  ExternalLink,
  Phone,
  DollarSign
} from 'lucide-react'
import toast from 'react-hot-toast'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

interface Customer {
  id: string
  name: string
  slug: string
  email: string
  subscription_plan: string
  subscription_status: string
  is_active: boolean
  is_kill_switched: boolean
  created_at: string
  stats: {
    calls_today: number
    calls_this_month: number
    errors_today: number
    error_rate: number
    unknown_questions_today: number
    unknown_rate: number
    spend_today_cents: number
    spend_month_cents: number
  }
}

interface CustomerDetail extends Customer {
  phone?: string
  stripe_customer_id?: string
  is_verified: boolean
  feature_flags: Record<string, any>
  admin_overrides: Record<string, any>
  updated_at: string
}

export function CustomersTab() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null)

  const { data: customersData, isLoading } = useQuery({
    queryKey: ['admin-customers'],
    queryFn: adminApi.getCustomers,
  })

  const { data: customerDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['admin-customer-detail', selectedCustomer],
    queryFn: () => adminApi.getCustomerDetail(selectedCustomer!),
    enabled: !!selectedCustomer,
  })

  const killSwitchMutation = useMutation({
    mutationFn: ({ customerId, enabled }: { customerId: string; enabled: boolean }) =>
      adminApi.toggleKillSwitch(customerId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-customers'] })
      queryClient.invalidateQueries({ queryKey: ['admin-customer-detail'] })
      toast.success('Kill switch bijgewerkt')
    },
    onError: () => {
      toast.error('Kon kill switch niet bijwerken')
    },
  })

  const updateOverridesMutation = useMutation({
    mutationFn: ({ customerId, overrides }: { customerId: string; overrides: any }) =>
      adminApi.updateCustomerOverrides(customerId, overrides),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-customer-detail'] })
      toast.success('Overrides opgeslagen')
    },
    onError: () => {
      toast.error('Kon overrides niet opslaan')
    },
  })

  const customers: Customer[] = customersData?.customers || []

  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.slug.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const formatCurrency = (cents: number) => `€${(cents / 100).toFixed(2)}`

  const getPlanBadge = (plan: string) => {
    const colors: Record<string, 'success' | 'primary' | 'warning' | 'gray'> = {
      starter: 'success',
      business: 'primary',
      enterprise: 'warning',
    }
    return <Badge variant={colors[plan] || 'gray'}>{plan}</Badge>
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Zoek op naam, email of slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Badge variant="gray">{filteredCustomers.length} klanten</Badge>
      </div>

      {/* Customers Table */}
      <Card>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Klant
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Plan
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Calls Vandaag
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Errors
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Unknown
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Spend Maand
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Acties
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredCustomers.map((customer) => (
                  <tr key={customer.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="font-medium text-gray-900">{customer.name}</p>
                        <p className="text-sm text-gray-500">{customer.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getPlanBadge(customer.subscription_plan)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <Phone className="h-4 w-4 text-gray-400" />
                        <span>{customer.stats.calls_today}</span>
                        <span className="text-gray-400 text-sm">
                          ({customer.stats.calls_this_month} maand)
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {customer.stats.errors_today > 0 && (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                        <span className={customer.stats.error_rate > 5 ? 'text-red-600 font-medium' : ''}>
                          {customer.stats.errors_today}
                        </span>
                        <span className="text-gray-400 text-sm">
                          ({customer.stats.error_rate.toFixed(1)}%)
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={customer.stats.unknown_rate > 20 ? 'text-yellow-600 font-medium' : ''}>
                        {customer.stats.unknown_questions_today}
                      </span>
                      <span className="text-gray-400 text-sm ml-1">
                        ({customer.stats.unknown_rate.toFixed(1)}%)
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <DollarSign className="h-4 w-4 text-gray-400" />
                        <span>{formatCurrency(customer.stats.spend_month_cents)}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {customer.is_kill_switched ? (
                        <Badge variant="danger">Kill Switch</Badge>
                      ) : customer.is_active ? (
                        <Badge variant="success">Actief</Badge>
                      ) : (
                        <Badge variant="gray">Inactief</Badge>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedCustomer(customer.id)}
                        >
                          <Settings className="h-4 w-4" />
                        </Button>
                        <Button
                          variant={customer.is_kill_switched ? 'primary' : 'outline'}
                          size="sm"
                          onClick={() => killSwitchMutation.mutate({
                            customerId: customer.id,
                            enabled: !customer.is_kill_switched
                          })}
                          className={customer.is_kill_switched ? '' : 'text-red-600 hover:bg-red-50'}
                        >
                          <Power className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* Customer Detail Modal */}
      <Modal
        isOpen={!!selectedCustomer}
        onClose={() => setSelectedCustomer(null)}
        title={customerDetail?.name || 'Klant Details'}
        description="Bekijk en bewerk verborgen admin instellingen"
      >
        {detailLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : customerDetail ? (
          <CustomerDetailContent
            customer={customerDetail}
            onSave={(overrides) => {
              updateOverridesMutation.mutate({
                customerId: customerDetail.id,
                overrides
              })
            }}
            isSaving={updateOverridesMutation.isPending}
          />
        ) : null}
      </Modal>
    </div>
  )
}

interface CustomerDetailContentProps {
  customer: CustomerDetail
  onSave: (overrides: any) => void
  isSaving: boolean
}

function CustomerDetailContent({ customer, onSave, isSaving }: CustomerDetailContentProps) {
  const [overrides, setOverrides] = useState(customer.admin_overrides || {})

  const handleChange = (key: string, value: any) => {
    setOverrides((prev: any) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="space-y-6">
      {/* Basic Info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm text-gray-500">Email</p>
          <p className="font-medium">{customer.email}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Plan</p>
          <p className="font-medium capitalize">{customer.subscription_plan}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Status</p>
          <p className="font-medium">{customer.subscription_status}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Stripe Customer</p>
          <p className="font-medium text-sm">{customer.stripe_customer_id || '-'}</p>
        </div>
      </div>

      <hr />

      {/* Admin Overrides */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-4">
          Verborgen Admin Overrides
        </h4>
        <p className="text-xs text-gray-500 mb-4">
          Deze instellingen zijn alleen zichtbaar voor platform admins, niet voor de klant.
        </p>

        <div className="space-y-4">
          <Input
            label="Force Language"
            value={overrides.force_language || ''}
            onChange={(e) => handleChange('force_language', e.target.value || null)}
            placeholder="nl-NL"
            helperText="Forceer taalinstelling (bijv. nl-NL)"
          />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Force U-vorm</p>
              <p className="text-xs text-gray-500">Forceer formele aanspreking</p>
            </div>
            <Toggle
              enabled={overrides.force_u_form || false}
              onChange={(val) => handleChange('force_u_form', val)}
            />
          </div>

          <Input
            label="Orchestrator Model Override"
            value={overrides.orchestrator_model_override || ''}
            onChange={(e) => handleChange('orchestrator_model_override', e.target.value || null)}
            placeholder="gpt-4o"
            helperText="Override het standaard model (gpt-4o-mini)"
          />

          <Input
            label="RAG Threshold Override"
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={overrides.rag_threshold_override || ''}
            onChange={(e) => handleChange('rag_threshold_override', e.target.value ? parseFloat(e.target.value) : null)}
            placeholder="0.7"
            helperText="Minimum RAG confidence (0-1)"
          />

          <Input
            label="Audio Segment Override (ms)"
            type="number"
            min="500"
            max="5000"
            value={overrides.audio_segment_ms_override || ''}
            onChange={(e) => handleChange('audio_segment_ms_override', e.target.value ? parseInt(e.target.value) : null)}
            placeholder="2500"
            helperText="Audio segment lengte in milliseconden"
          />

          <Input
            label="Max Calls per Minuut"
            type="number"
            min="1"
            max="100"
            value={overrides.max_calls_per_minute || ''}
            onChange={(e) => handleChange('max_calls_per_minute', e.target.value ? parseInt(e.target.value) : null)}
            placeholder="10"
            helperText="Rate limit voor deze klant"
          />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Disable Auto Booking</p>
              <p className="text-xs text-gray-500">Alleen suggesties, geen echte boekingen</p>
            </div>
            <Toggle
              enabled={overrides.disable_auto_booking || false}
              onChange={(val) => handleChange('disable_auto_booking', val)}
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4">
        <Button
          onClick={() => onSave({ admin_overrides: overrides })}
          disabled={isSaving}
        >
          {isSaving ? 'Opslaan...' : 'Overrides Opslaan'}
        </Button>
      </div>
    </div>
  )
}
