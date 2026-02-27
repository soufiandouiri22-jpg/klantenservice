'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Lock, 
  FileText,
  Plus,
  Pencil,
  Trash2,
  Eye,
  Save,
  X,
  ChevronDown,
  ChevronRight,
  Sparkles,
  RefreshCw,
  Info,
  Bot
} from 'lucide-react'
import toast from 'react-hot-toast'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { Select } from '@/components/ui/Select'
import { adminApi } from '@/lib/api'

interface SystemPrompt {
  id: string
  key: string
  name: string
  description: string | null
  category: string
  content: string
  is_active: boolean
  display_order: number
  created_at: string
  updated_at: string
  updated_by_name: string | null
}

interface Category {
  key: string
  name: string
  icon: string
}

const categoryIcons: Record<string, any> = {
  privacy: Lock,
  compliance: FileText,
  custom: FileText,
}

const categoryColors: Record<string, string> = {
  privacy: 'bg-purple-100 text-purple-700 border-purple-200',
  compliance: 'bg-blue-100 text-blue-700 border-blue-200',
  custom: 'bg-gray-100 text-gray-700 border-gray-200',
}

export function PoliciesTab() {
  const queryClient = useQueryClient()
  
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false)
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set())
  
  const [newPrompt, setNewPrompt] = useState({
    key: '',
    name: '',
    description: '',
    category: 'custom',
    content: '',
    is_active: true,
    display_order: 0,
  })

  const { data: promptsData, isLoading: promptsLoading } = useQuery({
    queryKey: ['admin-prompts'],
    queryFn: () => adminApi.getPrompts(),
  })

  const { data: categories } = useQuery({
    queryKey: ['admin-categories'],
    queryFn: adminApi.getCategories,
  })

  const { data: previewData } = useQuery({
    queryKey: ['admin-prompt-preview'],
    queryFn: adminApi.previewPrompt,
    enabled: isPreviewModalOpen,
  })

  const createMutation = useMutation({
    mutationFn: adminApi.createPrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Beleidsregel aangemaakt')
      setIsCreateModalOpen(false)
      setNewPrompt({
        key: '',
        name: '',
        description: '',
        category: 'custom',
        content: '',
        is_active: true,
        display_order: 0,
      })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon beleidsregel niet aanmaken')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminApi.updatePrompt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Beleidsregel bijgewerkt')
      setEditingPrompt(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon beleidsregel niet bijwerken')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: adminApi.deletePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Beleidsregel verwijderd')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon beleidsregel niet verwijderen')
    },
  })

  const seedMutation = useMutation({
    mutationFn: adminApi.seedPrompts,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      if (data.total > 0) {
        toast.success(`${data.total} standaard beleidsregels aangemaakt`)
      } else {
        toast.success('Alle standaard beleidsregels bestaan al')
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon standaard beleidsregels niet aanmaken')
    },
  })

  const togglePromptExpand = (id: string) => {
    const newExpanded = new Set(expandedPrompts)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedPrompts(newExpanded)
  }

  const handleToggleActive = (prompt: SystemPrompt) => {
    updateMutation.mutate({
      id: prompt.id,
      data: { is_active: !prompt.is_active },
    })
  }

  if (promptsLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    )
  }

  const prompts: SystemPrompt[] = promptsData?.prompts || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Aanvullend Bedrijfsbeleid</h2>
          <p className="text-sm text-gray-500">
            Optionele beleidsregels die worden meegegeven aan alle AI-medewerkers.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsPreviewModalOpen(true)}
          >
            <Eye className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">Preview</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
          >
            <RefreshCw className={`h-4 w-4 sm:mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Standaard laden</span>
          </Button>
          <Button size="sm" onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">Nieuwe beleidsregel</span>
          </Button>
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardBody className="p-4">
          <div className="flex gap-3">
            <Bot className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">AI-instructies beheren</p>
              <p className="text-blue-700">
                Beheer alle AI-instructies: persoonlijkheid, toon, spreekstijl, gespreksverloop, 
                veiligheid en taalregels. Voeg daarnaast aanvullend bedrijfsbeleid toe, zoals 
                privacy- of compliance-regels.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Empty State */}
      {prompts.length === 0 && (
        <Card>
          <CardBody className="text-center py-12">
            <Sparkles className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Geen aanvullende beleidsregels</h3>
            <p className="text-gray-500 mb-6">
              De AI werkt al met automatische instructies. Voeg hier optioneel extra beleidsregels toe.
            </p>
            <div className="flex justify-center gap-3">
              <Button
                variant="outline"
                onClick={() => seedMutation.mutate()}
                disabled={seedMutation.isPending}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
                Standaard beleidsregels laden
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Prompts List */}
      <div className="space-y-3">
        {prompts.map((prompt) => {
          const CategoryIcon = categoryIcons[prompt.category] || FileText
          
          return (
            <motion.div
              key={prompt.id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card className={!prompt.is_active ? 'opacity-60' : ''}>
                <CardBody className="p-4">
                  {editingPrompt?.id === prompt.id ? (
                    // Edit Mode
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <Input
                          label="Key"
                          value={editingPrompt.key}
                          onChange={(e) => setEditingPrompt({ ...editingPrompt, key: e.target.value })}
                        />
                        <Input
                          label="Naam"
                          value={editingPrompt.name}
                          onChange={(e) => setEditingPrompt({ ...editingPrompt, name: e.target.value })}
                        />
                      </div>
                      <Input
                        label="Beschrijving"
                        value={editingPrompt.description || ''}
                        onChange={(e) => setEditingPrompt({ ...editingPrompt, description: e.target.value })}
                      />
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Content
                        </label>
                        <textarea
                          value={editingPrompt.content}
                          onChange={(e) => setEditingPrompt({ ...editingPrompt, content: e.target.value })}
                          rows={6}
                          className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm font-mono focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                        />
                      </div>
                      <div className="flex justify-end gap-3">
                        <Button variant="outline" onClick={() => setEditingPrompt(null)}>
                          <X className="h-4 w-4 mr-2" />
                          Annuleren
                        </Button>
                        <Button
                          onClick={() => updateMutation.mutate({
                            id: editingPrompt.id,
                            data: {
                              key: editingPrompt.key,
                              name: editingPrompt.name,
                              description: editingPrompt.description,
                              content: editingPrompt.content,
                            }
                          })}
                          disabled={updateMutation.isPending}
                        >
                          <Save className="h-4 w-4 mr-2" />
                          Opslaan
                        </Button>
                      </div>
                    </div>
                  ) : (
                    // View Mode
                    <div>
                      <div className="flex items-start gap-3">
                        <div 
                          className="flex items-start gap-3 cursor-pointer flex-1 min-w-0"
                          onClick={() => togglePromptExpand(prompt.id)}
                        >
                          <div className="flex-shrink-0 mt-0.5">
                            {expandedPrompts.has(prompt.id) ? (
                              <ChevronDown className="h-5 w-5 text-gray-400" />
                            ) : (
                              <ChevronRight className="h-5 w-5 text-gray-400" />
                            )}
                          </div>
                          <div className={`flex-shrink-0 p-1.5 rounded ${categoryColors[prompt.category] || categoryColors.custom}`}>
                            <CategoryIcon className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <h3 className="font-medium text-gray-900">{prompt.name}</h3>
                            {prompt.description && (
                              <p className="text-sm text-gray-500 break-words">{prompt.description}</p>
                            )}
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                          <Toggle
                            enabled={prompt.is_active}
                            onChange={() => handleToggleActive(prompt)}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingPrompt(prompt)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => {
                              if (confirm(`Weet je zeker dat je "${prompt.name}" wilt verwijderen?`)) {
                                deleteMutation.mutate(prompt.id)
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      <AnimatePresence>
                        {expandedPrompts.has(prompt.id) && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-4 ml-14 p-4 bg-gray-50 rounded-lg">
                              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                                {prompt.content}
                              </pre>
                            </div>
                            {prompt.updated_by_name && (
                              <p className="mt-3 ml-14 text-xs text-gray-400">
                                Laatst bewerkt door {prompt.updated_by_name} op{' '}
                                {new Date(prompt.updated_at).toLocaleDateString('nl-NL', {
                                  day: 'numeric',
                                  month: 'long',
                                  year: 'numeric',
                                })}
                              </p>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}
                </CardBody>
              </Card>
            </motion.div>
          )
        })}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nieuwe beleidsregel"
        description="Voeg een aanvullende beleidsregel toe voor alle AI-medewerkers."
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Key"
              value={newPrompt.key}
              onChange={(e) => setNewPrompt({ ...newPrompt, key: e.target.value })}
              placeholder="custom_policy"
            />
            <Input
              label="Naam"
              value={newPrompt.name}
              onChange={(e) => setNewPrompt({ ...newPrompt, name: e.target.value })}
              placeholder="Bedrijfsbeleid"
            />
          </div>
          
          <Select
            label="Categorie"
            className="max-w-xs"
            value={newPrompt.category}
            onChange={(e) => setNewPrompt({ ...newPrompt, category: e.target.value })}
          >
            {categories?.map((cat: Category) => (
              <option key={cat.key} value={cat.key}>
                {cat.icon} {cat.name}
              </option>
            ))}
          </Select>

          <Input
            label="Beschrijving"
            value={newPrompt.description}
            onChange={(e) => setNewPrompt({ ...newPrompt, description: e.target.value })}
            placeholder="Korte beschrijving"
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
            <textarea
              value={newPrompt.content}
              onChange={(e) => setNewPrompt({ ...newPrompt, content: e.target.value })}
              rows={6}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm font-mono focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              placeholder="- Regel 1&#10;- Regel 2"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Annuleren
            </Button>
            <Button
              onClick={() => createMutation.mutate(newPrompt)}
              disabled={createMutation.isPending || !newPrompt.key || !newPrompt.name || !newPrompt.content}
            >
              {createMutation.isPending ? 'Aanmaken...' : 'Aanmaken'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Preview Modal */}
      <Modal
        isOpen={isPreviewModalOpen}
        onClose={() => setIsPreviewModalOpen(false)}
        title="Preview aanvullend bedrijfsbeleid"
        description={`${previewData?.active_prompts || 0} actieve beleidsregels worden meegegeven aan de AI`}
      >
        <div className="space-y-4">
          <div className="flex gap-3 p-3 bg-blue-50 rounded-lg">
            <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
            <p className="text-xs text-blue-700">
              Dit is een preview van alle actieve instructies, inclusief persoonlijkheid, toon, 
              gespreksverloop, veiligheidsregels en aanvullend bedrijfsbeleid.
            </p>
          </div>
          <div className="max-h-[50vh] overflow-y-auto">
            <pre className="p-4 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap font-mono">
              {previewData?.combined_prompt || 'Geen actieve beleidsregels'}
            </pre>
          </div>
        </div>
        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={() => setIsPreviewModalOpen(false)}>
            Sluiten
          </Button>
        </div>
      </Modal>
    </div>
  )
}
