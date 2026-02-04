'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { SlidersHorizontal, Save, RefreshCw, AlertTriangle } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'
import { useState, useEffect } from 'react'

export function ThresholdsTab() {
  const queryClient = useQueryClient()
  
  const { data: configs, isLoading } = useQuery({
    queryKey: ['admin-global-configs'],
    queryFn: adminApi.getGlobalConfigs,
  })

  const [values, setValues] = useState<Record<string, any>>({})

  useEffect(() => {
    if (configs?.thresholds) {
      const initial: Record<string, any> = {}
      configs.thresholds.forEach((c: any) => {
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

  const thresholdConfigs = configs?.thresholds || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Confidence Thresholds</h2>
          <p className="text-sm text-gray-500">
            Bepaal wanneer de AI zeker genoeg is om te handelen.
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

      {/* Warning */}
      <Card className="bg-yellow-50 border-yellow-200">
        <CardBody className="py-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-800">
                Let op: deze instellingen beinvloeden de kwaliteit
              </p>
              <p className="text-xs text-yellow-700 mt-1">
                Te lage thresholds = meer fouten. Te hoge thresholds = vaker "ik weet het niet".
                Test wijzigingen grondig voordat je ze in productie zet.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {thresholdConfigs.length === 0 ? (
        <Card>
          <CardBody className="text-center py-12">
            <SlidersHorizontal className="h-12 w-12 text-gray-300 mx-auto mb-4" />
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
          {/* RAG Confidence */}
          <Card>
            <CardHeader>
              <CardTitle>RAG Confidence Threshold</CardTitle>
              <CardDescription>
                Minimum score voor kennisbank resultaten.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <Input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={values['threshold_rag_confidence'] || 0.7}
                    onChange={(e) => setValues({ ...values, threshold_rag_confidence: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>Laag (0.5)</span>
                    <span className="font-medium text-primary-600">
                      {values['threshold_rag_confidence'] || 0.7}
                    </span>
                    <span>Hoog (1.0)</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Lagere waarde = meer resultaten maar minder relevant.
                  Hogere waarde = minder resultaten maar relevanter.
                </p>
                <Button
                  onClick={() => handleSave('threshold_rag_confidence')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Intent Confidence */}
          <Card>
            <CardHeader>
              <CardTitle>Intent Confidence Threshold</CardTitle>
              <CardDescription>
                Minimum zekerheid voor intent detectie.
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <Input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={values['threshold_intent_confidence'] || 0.8}
                    onChange={(e) => setValues({ ...values, threshold_intent_confidence: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>Laag (0.5)</span>
                    <span className="font-medium text-primary-600">
                      {values['threshold_intent_confidence'] || 0.8}
                    </span>
                    <span>Hoog (1.0)</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Bepaalt wanneer de AI zeker genoeg is over wat de klant wil.
                  Bij lage confidence: vraag om verduidelijking.
                </p>
                <Button
                  onClick={() => handleSave('threshold_intent_confidence')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Unknown Sensitivity */}
          <Card>
            <CardHeader>
              <CardTitle>Unknown Sensitivity</CardTitle>
              <CardDescription>
                Hoe snel wordt een vraag als "onbekend" gemarkeerd?
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <div>
                  <Input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={values['threshold_unknown_sensitivity'] || 0.6}
                    onChange={(e) => setValues({ ...values, threshold_unknown_sensitivity: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>Laag (weinig unknowns)</span>
                    <span className="font-medium text-primary-600">
                      {values['threshold_unknown_sensitivity'] || 0.6}
                    </span>
                    <span>Hoog (veel unknowns)</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  Hogere waarde = meer vragen worden gemarkeerd als onbekend
                  en doorgestuurd naar het dashboard.
                </p>
                <Button
                  onClick={() => handleSave('threshold_unknown_sensitivity')}
                  disabled={updateMutation.isPending}
                  className="w-full"
                >
                  <Save className="h-4 w-4 mr-2" />
                  Opslaan
                </Button>
              </div>
            </CardBody>
          </Card>

          {/* Max Turns */}
          <Card>
            <CardHeader>
              <CardTitle>Max Turns zonder Progress</CardTitle>
              <CardDescription>
                Wanneer moet de AI opgeven en doorverbinden?
              </CardDescription>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Input
                  label="Maximum beurten"
                  type="number"
                  min="2"
                  max="20"
                  value={values['threshold_max_turns_no_progress'] || 5}
                  onChange={(e) => setValues({ ...values, threshold_max_turns_no_progress: parseInt(e.target.value) })}
                  helperText="Na zoveel beurten zonder vooruitgang -> handoff"
                />
                <p className="text-xs text-gray-500">
                  Voorkomt eindeloze loops. Aanbevolen: 5-7 beurten.
                  Na dit aantal beurten escaleert de AI naar een mens.
                </p>
                <Button
                  onClick={() => handleSave('threshold_max_turns_no_progress')}
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
