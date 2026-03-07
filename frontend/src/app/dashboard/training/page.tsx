'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, GraduationCap, MessageSquare, Lightbulb, Trash2, Edit2, Check, X, FileText, Info } from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { trainingApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export default function TrainingPage() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const canEdit = user?.role !== 'viewer'
  const [isAddAnswerModalOpen, setIsAddAnswerModalOpen] = useState(false)
  const [editingAnswer, setEditingAnswer] = useState<any>(null)
  const [newQuestion, setNewQuestion] = useState('')
  const [newAnswer, setNewAnswer] = useState('')
  const [newCategory, setNewCategory] = useState('')

  const { data: instructionsData } = useQuery({
    queryKey: ['training-instructions'],
    queryFn: trainingApi.getInstructions,
  })
  const [instructionsValue, setInstructionsValue] = useState<string | null>(null)
  const instructionsText = instructionsValue ?? instructionsData?.custom_instructions ?? ''

  const updateInstructionsMutation = useMutation({
    mutationFn: trainingApi.updateInstructions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-instructions'] })
      toast.success('Instructies opgeslagen')
    },
    onError: () => {
      toast.error('Kon instructies niet opslaan')
    },
  })

  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ['training-rules'],
    queryFn: trainingApi.getRules,
  })

  const { data: answers, isLoading: answersLoading } = useQuery({
    queryKey: ['example-answers'],
    queryFn: () => trainingApi.getAnswers(),
  })

  const { data: detectedQuestions } = useQuery({
    queryKey: ['detected-questions'],
    queryFn: trainingApi.getDetectedQuestions,
  })

  const { data: categories } = useQuery({
    queryKey: ['answer-categories'],
    queryFn: trainingApi.getCategories,
  })

  const updateRuleMutation = useMutation({
    mutationFn: ({ id, isEnabled }: { id: string; isEnabled: boolean }) =>
      trainingApi.updateRule(id, isEnabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['training-rules'] })
      toast.success('Regel bijgewerkt')
    },
  })

  const createAnswerMutation = useMutation({
    mutationFn: trainingApi.createAnswer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['example-answers'] })
      toast.success('Voorbeeldantwoord toegevoegd')
      setIsAddAnswerModalOpen(false)
      resetForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij toevoegen')
    },
  })

  const updateAnswerMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      trainingApi.updateAnswer(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['example-answers'] })
      toast.success('Voorbeeldantwoord bijgewerkt')
      setEditingAnswer(null)
    },
  })

  const deleteAnswerMutation = useMutation({
    mutationFn: trainingApi.deleteAnswer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['example-answers'] })
      toast.success('Voorbeeldantwoord verwijderd')
    },
  })

  const dismissQuestionMutation = useMutation({
    mutationFn: trainingApi.dismissDetectedQuestion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['detected-questions'] })
      toast.success('Vraag genegeerd')
    },
    onError: () => {
      toast.error('Fout bij negeren van vraag')
    },
  })

  const resetForm = () => {
    setNewQuestion('')
    setNewAnswer('')
    setNewCategory('')
  }

  const handleAddAnswer = () => {
    if (!newQuestion.trim() || !newAnswer.trim()) {
      toast.error('Vul zowel vraag als antwoord in')
      return
    }
    createAnswerMutation.mutate({
      question: newQuestion,
      answer: newAnswer,
      category: newCategory || undefined,
    })
  }

  const isLoading = rulesLoading || answersLoading

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  // Group answers by category
  const answersByCategory = answers?.reduce((acc: any, answer: any) => {
    const category = answer.category || 'Algemeen'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(answer)
    return acc
  }, {})

  return (
    <DashboardLayout>
      <Header
        title="Training"
        description="Configureer het gedrag en de kennis van uw AI-medewerkers."
        hideSearch
        actions={
          canEdit ? (
            <Button
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={() => setIsAddAnswerModalOpen(true)}
            >
              Vraag toevoegen
            </Button>
          ) : undefined
        }
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Custom Instructions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary-600" />
              Instructies voor uw AI
              <div className="relative group">
                <Info className="h-4 w-4 text-gray-400 cursor-help" />
                <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none">
                  Uw AI weet al hoe het moet doorvragen — bij gezondheidsklachten vraagt het naar de duur en ernst, bij voertuigproblemen naar het kenteken en merk, enzovoort. Dit veld is voor regels die alleen voor uw bedrijf gelden, zoals interne afspraken, uitzonderingen of doorverwijzingen.
                  <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-900" />
                </div>
              </div>
            </CardTitle>
          </CardHeader>
          <CardBody>
            <textarea
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none transition-colors"
              rows={5}
              placeholder={'Bijv. "Wij leveren alleen aan bedrijven, niet aan particulieren."\nof "Kinderen onder 4 jaar altijd dezelfde dag inplannen."'}
              value={instructionsText}
              onChange={(e) => setInstructionsValue(e.target.value)}
              onBlur={() => {
                if (canEdit && instructionsText !== (instructionsData?.custom_instructions ?? '')) {
                  updateInstructionsMutation.mutate(instructionsText)
                }
              }}
              disabled={!canEdit}
            />
            <p className="mt-2 text-xs text-gray-400">
              Laat dit veld leeg als de standaard flow al voldoende is. Wijzigingen worden automatisch opgeslagen.
            </p>
          </CardBody>
        </Card>

        {/* Behavior Rules */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-primary-600" />
              Gedragsregels
            </CardTitle>
          </CardHeader>
          <CardBody className="space-y-4">
            {rules?.map((rule: any) => (
              <div key={rule.id} className="flex items-start justify-between py-3 border-b border-gray-100 last:border-0">
                <Toggle
                  enabled={rule.is_enabled}
                  onChange={canEdit ? (enabled) => updateRuleMutation.mutate({ id: rule.id, isEnabled: enabled }) : () => {}}
                  label={rule.rule_name}
                  description={rule.rule_description}
                />
              </div>
            ))}
          </CardBody>
        </Card>

        {/* Detected Questions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-amber-500" />
              Gedetecteerde vragen
              {detectedQuestions && detectedQuestions.length > 0 && (
                <Badge variant="warning">{detectedQuestions.length} nieuw</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardBody>
            {!detectedQuestions || detectedQuestions.length === 0 ? (
              <EmptyState
                icon={Lightbulb}
                title="Nog geen vragen gedetecteerd"
                description="Zodra bellers vragen stellen die de AI niet kan beantwoorden, verschijnen ze hier automatisch. U kunt dan eenvoudig een antwoord toevoegen."
              />
            ) : (
              <>
                <p className="text-sm text-gray-500 mb-4">
                  Deze vragen zijn vaak gesteld door bellers. Voeg een antwoord toe zodat de AI deze vragen kan beantwoorden.
                </p>
                <div className="space-y-3">
                  {detectedQuestions.map((q: any) => (
                    <div key={q.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg bg-amber-50 border border-amber-100">
                      <div>
                        <p className="font-medium text-gray-900">{q.question}</p>
                        <p className="text-sm text-gray-500">{q.occurrences}x gevraagd</p>
                      </div>
                      {canEdit && (
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => dismissQuestionMutation.mutate(q.id)}
                            disabled={dismissQuestionMutation.isPending}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => {
                              setNewQuestion(q.question)
                              setIsAddAnswerModalOpen(true)
                            }}
                          >
                            Antwoord toevoegen
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardBody>
        </Card>

        {/* Example Answers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary-600" />
              Voorbeeldantwoorden
            </CardTitle>
          </CardHeader>
          <CardBody>
            {!answers || answers.length === 0 ? (
              <EmptyState
                icon={MessageSquare}
                title="Geen voorbeeldantwoorden"
                description="Voeg vraag-antwoord paren toe zodat de AI weet hoe te reageren op specifieke vragen."
                action={
                  canEdit ? (
                    <Button
                      leftIcon={<Plus className="h-4 w-4" />}
                      onClick={() => setIsAddAnswerModalOpen(true)}
                    >
                      Eerste vraag toevoegen
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="space-y-6">
                {Object.entries(answersByCategory || {}).map(([category, categoryAnswers]: [string, any]) => (
                  <div key={category}>
                    <h4 className="text-sm font-medium text-gray-500 mb-3">{category}</h4>
                    <div className="space-y-3">
                      {categoryAnswers.map((answer: any) => (
                        <motion.div
                          key={answer.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          className="p-4 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="font-medium text-gray-900">{answer.question}</p>
                              <p className="mt-2 text-sm text-gray-600">{answer.answer}</p>
                              {answer.detected_count > 0 && (
                                <p className="mt-2 text-xs text-gray-400">
                                  {answer.detected_count}x gebruikt
                                </p>
                              )}
                            </div>
                            {canEdit && (
                              <div className="flex items-center gap-1 ml-4">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingAnswer(answer)}
                                >
                                  <Edit2 className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    if (confirm('Weet u zeker dat u dit antwoord wilt verwijderen?')) {
                                      deleteAnswerMutation.mutate(answer.id)
                                    }
                                  }}
                                >
                                  <Trash2 className="h-4 w-4 text-red-500" />
                                </Button>
                              </div>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Add Answer Modal */}
      <Modal
        isOpen={isAddAnswerModalOpen}
        onClose={() => {
          setIsAddAnswerModalOpen(false)
          resetForm()
        }}
        title="Vraag toevoegen"
        description="Voeg een vraag-antwoord paar toe aan de kennisbank."
        size="lg"
      >
        <div className="space-y-4">
          <Input
            label="Vraag"
            placeholder="Wat zijn jullie openingstijden?"
            value={newQuestion}
            onChange={(e) => setNewQuestion(e.target.value)}
          />
          <div>
            <label className="label">Antwoord</label>
            <textarea
              className="input min-h-[120px] resize-none"
              placeholder="Wij zijn geopend van maandag tot en met vrijdag van 9:00 tot 17:00 uur."
              value={newAnswer}
              onChange={(e) => setNewAnswer(e.target.value)}
            />
          </div>
          <Input
            label="Categorie (optioneel)"
            placeholder="bijv. Openingstijden, Prijzen"
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
          />
          <div className="flex gap-3 pt-4">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => {
                setIsAddAnswerModalOpen(false)
                resetForm()
              }}
            >
              Annuleren
            </Button>
            <Button
              className="flex-1"
              onClick={handleAddAnswer}
              isLoading={createAnswerMutation.isPending}
            >
              Toevoegen
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Answer Modal */}
      <Modal
        isOpen={!!editingAnswer}
        onClose={() => setEditingAnswer(null)}
        title="Vraag bewerken"
        size="lg"
      >
        {editingAnswer && (
          <div className="space-y-4">
            <Input
              label="Vraag"
              value={editingAnswer.question}
              onChange={(e) => setEditingAnswer({ ...editingAnswer, question: e.target.value })}
            />
            <div>
              <label className="label">Antwoord</label>
              <textarea
                className="input min-h-[120px] resize-none"
                value={editingAnswer.answer}
                onChange={(e) => setEditingAnswer({ ...editingAnswer, answer: e.target.value })}
              />
            </div>
            <Input
              label="Categorie"
              value={editingAnswer.category || ''}
              onChange={(e) => setEditingAnswer({ ...editingAnswer, category: e.target.value })}
            />
            <div className="flex gap-3 pt-4">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setEditingAnswer(null)}
              >
                Annuleren
              </Button>
              <Button
                className="flex-1"
                onClick={() => {
                  updateAnswerMutation.mutate({
                    id: editingAnswer.id,
                    data: {
                      question: editingAnswer.question,
                      answer: editingAnswer.answer,
                      category: editingAnswer.category,
                    },
                  })
                }}
                isLoading={updateAnswerMutation.isPending}
              >
                Opslaan
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
