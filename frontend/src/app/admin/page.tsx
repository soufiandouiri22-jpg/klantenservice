'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Settings2, 
  MessageSquare, 
  Shield, 
  Lock, 
  Star, 
  AlertTriangle, 
  FileText,
  Plus,
  Pencil,
  Trash2,
  Eye,
  EyeOff,
  Save,
  X,
  ChevronDown,
  ChevronRight,
  Sparkles,
  RefreshCw
} from 'lucide-react'
import toast from 'react-hot-toast'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { Badge } from '@/components/ui/Badge'
import { PageLoader } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { adminApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'

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
  communication: MessageSquare,
  safety: Shield,
  privacy: Lock,
  quality: Star,
  edge_cases: AlertTriangle,
  general: FileText,
}

const categoryColors: Record<string, string> = {
  communication: 'bg-blue-100 text-blue-700 border-blue-200',
  safety: 'bg-red-100 text-red-700 border-red-200',
  privacy: 'bg-purple-100 text-purple-700 border-purple-200',
  quality: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  edge_cases: 'bg-orange-100 text-orange-700 border-orange-200',
  general: 'bg-gray-100 text-gray-700 border-gray-200',
}

export default function AdminPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false)
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set())
  
  const [newPrompt, setNewPrompt] = useState({
    key: '',
    name: '',
    description: '',
    category: 'general',
    content: '',
    is_active: true,
    display_order: 0,
  })

  // Check if user is superadmin
  useEffect(() => {
    if (user && !user.is_superadmin) {
      toast.error('Je hebt geen toegang tot deze pagina')
      router.push('/dashboard')
    }
  }, [user, router])

  const { data: promptsData, isLoading: promptsLoading, error: promptsError } = useQuery({
    queryKey: ['admin-prompts', selectedCategory],
    queryFn: () => adminApi.getPrompts(selectedCategory || undefined),
    enabled: !!user?.is_superadmin,
  })

  const { data: categories } = useQuery({
    queryKey: ['admin-categories'],
    queryFn: adminApi.getCategories,
    enabled: !!user?.is_superadmin,
  })

  const { data: previewData } = useQuery({
    queryKey: ['admin-prompt-preview'],
    queryFn: adminApi.previewPrompt,
    enabled: isPreviewModalOpen && !!user?.is_superadmin,
  })

  const createMutation = useMutation({
    mutationFn: adminApi.createPrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Prompt aangemaakt')
      setIsCreateModalOpen(false)
      setNewPrompt({
        key: '',
        name: '',
        description: '',
        category: 'general',
        content: '',
        is_active: true,
        display_order: 0,
      })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon prompt niet aanmaken')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminApi.updatePrompt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Prompt bijgewerkt')
      setEditingPrompt(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon prompt niet bijwerken')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: adminApi.deletePrompt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      toast.success('Prompt verwijderd')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon prompt niet verwijderen')
    },
  })

  const seedMutation = useMutation({
    mutationFn: adminApi.seedPrompts,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin-prompts'] })
      queryClient.invalidateQueries({ queryKey: ['admin-prompt-preview'] })
      if (data.total > 0) {
        toast.success(`${data.total} standaard prompts aangemaakt`)
      } else {
        toast.success('Alle standaard prompts bestaan al')
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Kon standaard prompts niet aanmaken')
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

  if (!user?.is_superadmin) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <Shield className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900">Geen toegang</h2>
            <p className="text-gray-500 mt-2">Je hebt geen rechten om deze pagina te bekijken.</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  if (promptsLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const prompts: SystemPrompt[] = promptsData?.prompts || []

  // Group prompts by category
  const promptsByCategory = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.category]) {
      acc[prompt.category] = []
    }
    acc[prompt.category].push(prompt)
    return acc
  }, {} as Record<string, SystemPrompt[]>)

  return (
    <DashboardLayout>
      <Header 
        title="Admin - System Prompts" 
        description="Beheer de basisinstructies die voor alle AI-medewerkers gelden."
      />

      <div className="p-6">
        {/* Actions Bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            {/* Category Filter */}
            <select
              value={selectedCategory || ''}
              onChange={(e) => setSelectedCategory(e.target.value || null)}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
            >
              <option value="">Alle categorieën</option>
              {categories?.map((cat: Category) => (
                <option key={cat.key} value={cat.key}>
                  {cat.icon} {cat.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={() => setIsPreviewModalOpen(true)}
            >
              <Eye className="h-4 w-4 mr-2" />
              Preview volledige prompt
            </Button>
            <Button
              variant="outline"
              onClick={() => seedMutation.mutate()}
              disabled={seedMutation.isPending}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
              Standaard prompts laden
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Nieuwe prompt
            </Button>
          </div>
        </div>

        {/* Empty State */}
        {prompts.length === 0 && (
          <Card>
            <CardBody className="text-center py-12">
              <Sparkles className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Geen system prompts</h3>
              <p className="text-gray-500 mb-6">
                Voeg standaard prompts toe om je AI-medewerkers te verbeteren.
              </p>
              <div className="flex justify-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => seedMutation.mutate()}
                  disabled={seedMutation.isPending}
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
                  Standaard prompts laden
                </Button>
                <Button onClick={() => setIsCreateModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Handmatig toevoegen
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Prompts List */}
        {Object.entries(promptsByCategory).map(([category, categoryPrompts]) => {
          const CategoryIcon = categoryIcons[category] || FileText
          const categoryInfo = categories?.find((c: Category) => c.key === category)
          
          return (
            <div key={category} className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2 rounded-lg ${categoryColors[category] || categoryColors.general}`}>
                  <CategoryIcon className="h-5 w-5" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {categoryInfo?.name || category}
                </h2>
                <Badge variant="gray">{categoryPrompts.length}</Badge>
              </div>

              <div className="space-y-3">
                {categoryPrompts.map((prompt) => (
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
                                placeholder="language_rules"
                              />
                              <Input
                                label="Naam"
                                value={editingPrompt.name}
                                onChange={(e) => setEditingPrompt({ ...editingPrompt, name: e.target.value })}
                                placeholder="Taal & Spraak"
                              />
                            </div>
                            <Input
                              label="Beschrijving"
                              value={editingPrompt.description || ''}
                              onChange={(e) => setEditingPrompt({ ...editingPrompt, description: e.target.value })}
                              placeholder="Korte beschrijving voor admins"
                            />
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">
                                Content
                              </label>
                              <textarea
                                value={editingPrompt.content}
                                onChange={(e) => setEditingPrompt({ ...editingPrompt, content: e.target.value })}
                                rows={8}
                                className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm font-mono focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                                placeholder="- Regel 1&#10;- Regel 2"
                              />
                            </div>
                            <div className="flex justify-end gap-3">
                              <Button
                                variant="outline"
                                onClick={() => setEditingPrompt(null)}
                              >
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
                            <div className="flex items-start justify-between">
                              <div 
                                className="flex items-center gap-3 cursor-pointer flex-1"
                                onClick={() => togglePromptExpand(prompt.id)}
                              >
                                {expandedPrompts.has(prompt.id) ? (
                                  <ChevronDown className="h-5 w-5 text-gray-400" />
                                ) : (
                                  <ChevronRight className="h-5 w-5 text-gray-400" />
                                )}
                                <div>
                                  <h3 className="font-medium text-gray-900">{prompt.name}</h3>
                                  <p className="text-sm text-gray-500">
                                    <code className="bg-gray-100 px-1 rounded">{prompt.key}</code>
                                    {prompt.description && ` · ${prompt.description}`}
                                  </p>
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-3">
                                <Toggle
                                  enabled={prompt.is_active}
                                  onChange={() => handleToggleActive(prompt)}
                                  size="sm"
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
                                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                                    <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                                      {prompt.content}
                                    </pre>
                                  </div>
                                  {prompt.updated_by_name && (
                                    <p className="mt-3 text-xs text-gray-400">
                                      Laatst bewerkt door {prompt.updated_by_name} op{' '}
                                      {new Date(prompt.updated_at).toLocaleDateString('nl-NL', {
                                        day: 'numeric',
                                        month: 'long',
                                        year: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit',
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
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nieuwe System Prompt"
        description="Voeg een nieuwe basisinstructie toe voor alle AI-medewerkers."
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Key"
              value={newPrompt.key}
              onChange={(e) => setNewPrompt({ ...newPrompt, key: e.target.value })}
              placeholder="language_rules"
              helperText="Unieke identifier (snake_case)"
            />
            <Input
              label="Naam"
              value={newPrompt.name}
              onChange={(e) => setNewPrompt({ ...newPrompt, name: e.target.value })}
              placeholder="Taal & Spraak"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Categorie</label>
            <select
              value={newPrompt.category}
              onChange={(e) => setNewPrompt({ ...newPrompt, category: e.target.value })}
              className="w-full rounded-lg border border-gray-200 px-4 py-2.5 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
            >
              {categories?.map((cat: Category) => (
                <option key={cat.key} value={cat.key}>
                  {cat.icon} {cat.name}
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Beschrijving"
            value={newPrompt.description}
            onChange={(e) => setNewPrompt({ ...newPrompt, description: e.target.value })}
            placeholder="Korte beschrijving voor admins"
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
            <textarea
              value={newPrompt.content}
              onChange={(e) => setNewPrompt({ ...newPrompt, content: e.target.value })}
              rows={8}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm font-mono focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              placeholder="- Spreek altijd Nederlands&#10;- Gebruik duidelijke, korte zinnen"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setIsCreateModalOpen(false)}
            >
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
        title="Preview Volledige System Prompt"
        description={`${previewData?.active_prompts || 0} actieve prompts · Categorieën: ${previewData?.categories?.join(', ') || '-'}`}
      >
        <div className="max-h-[60vh] overflow-y-auto">
          <pre className="p-4 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap font-mono">
            {previewData?.combined_prompt || 'Geen actieve prompts'}
          </pre>
        </div>
        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={() => setIsPreviewModalOpen(false)}>
            Sluiten
          </Button>
        </div>
      </Modal>
    </DashboardLayout>
  )
}
