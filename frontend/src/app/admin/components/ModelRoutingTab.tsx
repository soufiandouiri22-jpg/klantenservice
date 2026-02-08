'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Cpu, Save, RefreshCw } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { Spinner } from '@/components/ui/Spinner'
import { Select } from '@/components/ui/Select'
import { adminApi } from '@/lib/api'
import { useState, useEffect } from 'react'

export function ModelRoutingTab() {
  const queryClient = useQueryClient()
  
  const { data: configs, isLoading } = useQuery({
    queryKey: ['admin-global-configs'],
    queryFn: adminApi.getGlobalConfigs,
  })

  const [values, setValues] = useState<Record<string, any>>({})

  useEffect(() => {
    if (configs?.model) {
      const initial: Record<string, any> = {}
      configs.model.forEach((c: any) => {
        initial[c.key] = c.value
      })
      setValues(initial)
    }
  }, [configs])

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: any }) =>
      adminApi.updateGlobalConfig(key, { value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success('Instelling opgeslagen')
    },
    onError: () => {
      toast.error('Kon instelling niet opslaan')
    },
  })

  const seedMutation = useMutation({
    mutationFn: adminApi.seedGlobalConfigs,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-global-configs'] })
      toast.success(`${data.created} nieuwe configs aangemaakt`)
    },
  })

  const handleSave = (key: string) => {
    updateMutation.mutate({ key, value: values[key] })
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  const modelConfigs = configs?.model || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Model & Routing</h2>
          <p className="text-sm text-gray-500">
            Configureer welke LLM models worden gebruikt en wanneer.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => seedMutation.mutate()}
          disabled={seedMutation.isPending}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
          Standaard configs laden
        </Button>
      </div>

      {modelConfigs.length === 0 ? (
        <Card>
          <CardBody className="text-center py-12">
            <Cpu className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Geen configuraties</h3>
            <p className="text-gray-500 mb-4">
              Laad de standaard configuraties om te beginnen.
            </p>
            <Button onClick={() => seedMutation.mutate()} disabled={seedMutation.isPending}>
              Configs laden
            </Button>
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Default Model */}
          <Card>
            <CardHeader>
              <CardTitle>Standaard Model</CardTitle>
              <CardDescription>
                Het model dat standaard wordt gebruikt voor de orchestrator.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Select
                  className="max-w-sm"
                  value={values['model_default'] || 'gpt-4o-mini'}
                  onChange={(e) => setValues({ ...values, model_default: e.target.value })}
                >
                  <option value="gpt-4o-mini">GPT-4o Mini (snel, goedkoop)</option>
                  <option value="gpt-4o">GPT-4o (slim, duurder)</option>
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo (legacy)</option>
                </Select>
                <Button
                  onClick={() => handleSave('model_default')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Fallback Model */}
          <Card>
            <CardHeader>
              <CardTitle>Fallback Model</CardTitle>
              <CardDescription>
                Het model dat gebruikt wordt bij fouten/timeouts.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Select
                  className="max-w-xs"
                  value={values['model_fallback'] || 'gpt-3.5-turbo'}
                  onChange={(e) => setValues({ ...values, model_fallback: e.target.value })}
                >
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                </Select>
                <Button
                  onClick={() => handleSave('model_fallback')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Big Model */}
          <Card>
            <CardHeader>
              <CardTitle>Groot Model</CardTitle>
              <CardDescription>
                Het model voor complexe situaties (klachten, onbekende vragen).
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Select
                  className="max-w-xs"
                  value={values['model_big'] || 'gpt-4o'}
                  onChange={(e) => setValues({ ...values, model_big: e.target.value })}
                >
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4-turbo">GPT-4 Turbo</option>
                </Select>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Gebruik bij onbekende vragen</span>
                  <Toggle
                    enabled={values['model_use_big_on_unknown'] || false}
                    onChange={(val) => {
                      setValues({ ...values, model_use_big_on_unknown: val })
                      updateMutation.mutate({ key: 'model_use_big_on_unknown', value: val })
                    }}
                  />
                </div>
                <Button
                  onClick={() => handleSave('model_big')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Rate Limits */}
          <Card>
            <CardHeader>
              <CardTitle>Rate Limits & Budgets</CardTitle>
              <CardDescription>
                Beperk API gebruik om kosten te beheersen.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Input
                  label="Dagelijks token budget"
                  type="number"
                  value={values['model_token_budget_daily'] || 1000000}
                  onChange={(e) => setValues({ ...values, model_token_budget_daily: parseInt(e.target.value) })}
                  helperText="Maximum tokens per dag (platform-breed)"
                />
                <Input
                  label="Rate limit (RPM)"
                  type="number"
                  value={values['model_rate_limit_rpm'] || 500}
                  onChange={(e) => setValues({ ...values, model_rate_limit_rpm: parseInt(e.target.value) })}
                  helperText="Maximum requests per minuut"
                />
                <Button
                  onClick={() => {
                    handleSave('model_token_budget_daily')
                    handleSave('model_rate_limit_rpm')
                  }}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  )
}
