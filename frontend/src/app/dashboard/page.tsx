'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Phone,
  Calendar,
  AlertCircle,
  Headphones,
  Rocket,
  CheckCircle2,
  Circle,
  ChevronRight,
  X,
  CreditCard,
  ArrowRight,
} from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { PageLoader } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { dashboardApi, aiWorkersApi, phoneNumbersApi, websitesApi, companyApi, paymentsApi } from '@/lib/api'
import { formatRelativeTime, formatDuration, getStatusColor, getStatusLabel } from '@/lib/utils'
import Link from 'next/link'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

export default function DashboardPage() {
  const [hideOnboarding, setHideOnboarding] = useState(false)
  
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: dashboardApi.getStats,
  })

  const { data: recentCalls, isLoading: callsLoading } = useQuery({
    queryKey: ['recent-calls'],
    queryFn: () => dashboardApi.getRecentCalls(5),
  })

  const { data: upcomingAppointments, isLoading: appointmentsLoading } = useQuery({
    queryKey: ['upcoming-appointments'],
    queryFn: () => dashboardApi.getUpcomingAppointments(5),
  })

  const { data: actionItems, isLoading: actionsLoading } = useQuery({
    queryKey: ['action-items'],
    queryFn: () => dashboardApi.getActionItems(5),
  })

  const { data: workersStatus, isLoading: workersLoading } = useQuery({
    queryKey: ['workers-status'],
    queryFn: dashboardApi.getAIWorkersStatus,
  })

  // Onboarding status queries
  const { data: aiWorkers } = useQuery({
    queryKey: ['ai-workers'],
    queryFn: aiWorkersApi.list,
  })

  const { data: phoneNumbers } = useQuery({
    queryKey: ['phone-numbers'],
    queryFn: phoneNumbersApi.list,
  })

  const { data: websites } = useQuery({
    queryKey: ['websites'],
    queryFn: websitesApi.list,
  })

  // Check subscription status
  const { data: subscription, isLoading: subscriptionLoading } = useQuery({
    queryKey: ['subscription'],
    queryFn: companyApi.getSubscription,
  })

  // Call minutes usage
  const { data: usage } = useQuery({
    queryKey: ['usage'],
    queryFn: paymentsApi.getUsage,
  })

  // Calculate onboarding progress
  const hasAIWorker = (aiWorkers?.length || 0) > 0
  const hasPhoneNumber = (phoneNumbers?.length || 0) > 0
  const phoneLinkedToAI = phoneNumbers?.some((p: any) => p.ai_worker_id) || false
  const hasKnowledge = (websites?.length || 0) > 0
  
  const completedSteps = [hasAIWorker, hasKnowledge, hasPhoneNumber && phoneLinkedToAI].filter(Boolean).length
  const totalSteps = 3
  const progressPercent = Math.round((completedSteps / totalSteps) * 100)
  const showOnboarding = !hideOnboarding && completedSteps < totalSteps

  // Check if user needs to activate subscription
  // Show banner for: pending, canceled, past_due - regardless of whether they have a stripe_customer_id
  const needsSubscription = subscription?.status === 'pending' || 
    subscription?.status === 'canceled' ||
    subscription?.status === 'past_due' ||
    (subscription?.status !== 'trialing' && subscription?.status !== 'active' && !subscription?.has_stripe)

  const isLoading = statsLoading || callsLoading || appointmentsLoading || actionsLoading || workersLoading || subscriptionLoading

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const statCards = [
    {
      label: 'Actieve AI-medewerkers',
      value: `${stats?.active_ai_workers || 0}/${stats?.total_ai_workers || 0}`,
      icon: Headphones,
      color: 'text-primary-600 bg-primary-100',
    },
    {
      label: 'Gesprekken vandaag',
      value: stats?.calls_today || 0,
      icon: Phone,
      color: 'text-green-600 bg-green-100',
    },
    {
      label: 'Afspraken vandaag',
      value: stats?.appointments_today || 0,
      icon: Calendar,
      color: 'text-amber-600 bg-amber-100',
    },
    {
      label: 'Openstaande acties',
      value: stats?.unresolved_notes || 0,
      icon: AlertCircle,
      color: 'text-red-600 bg-red-100',
    },
  ]

  // Sentiment calculations: neutral counts as positive
  const positiveCount = (stats?.sentiment_positive || 0) + (stats?.sentiment_neutral || 0)
  const negativeCount = (stats?.sentiment_negative || 0)
  const sentimentTotal = positiveCount + negativeCount
  const satisfactionPct = sentimentTotal > 0
    ? Math.round((positiveCount / sentimentTotal) * 100)
    : null

  // Answered %
  const answeredPct = (stats?.calls_this_month || 0) > 0
    ? Math.round(((stats!.calls_answered_month) / stats!.calls_this_month) * 100)
    : 100

  // Average duration formatted
  const avgDurMin = Math.floor((stats?.avg_duration_seconds || 0) / 60)
  const avgDurSec = (stats?.avg_duration_seconds || 0) % 60

  return (
    <DashboardLayout>
      <Header
        title="Overzicht"
        description="Welkom terug! Hier is een overzicht van uw klantenservice."
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="p-4 sm:p-6 space-y-6"
      >
        {/* Subscription Activation Banner */}
        {needsSubscription && (
          <motion.div variants={item}>
            <Card className={`border-${subscription?.status === 'canceled' || subscription?.status === 'past_due' ? 'red-300 bg-gradient-to-r from-red-50 to-orange-50' : 'amber-300 bg-gradient-to-r from-amber-50 to-orange-50'}`}>
              <CardBody className="p-6">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full ${subscription?.status === 'canceled' || subscription?.status === 'past_due' ? 'bg-red-100' : 'bg-amber-100'}`}>
                      <CreditCard className={`h-6 w-6 ${subscription?.status === 'canceled' || subscription?.status === 'past_due' ? 'text-red-600' : 'text-amber-600'}`} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {subscription?.status === 'canceled'
                          ? 'Uw abonnement is beëindigd'
                          : subscription?.status === 'past_due'
                          ? 'Betaling mislukt'
                          : 'Activeer uw abonnement'}
                      </h3>
                      <p className="text-sm text-gray-600 mt-1">
                        {subscription?.status === 'canceled'
                          ? 'Uw abonnement is opgezegd. Neem een nieuw abonnement om uw AI-medewerkers weer te activeren.'
                          : subscription?.status === 'past_due'
                          ? 'Uw laatste betaling is mislukt. Werk uw betaalgegevens bij om uw dienst te behouden.'
                          : 'Start vandaag nog met uw 14-dagen gratis proefperiode. Na de proefperiode wordt uw abonnement automatisch geactiveerd.'}
                      </p>
                    </div>
                  </div>
                  <Link href="/dashboard/settings?tab=subscription" className="w-full sm:w-auto">
                    <Button size="lg" className="whitespace-nowrap w-full sm:w-auto">
                      {subscription?.status === 'canceled' ? 'Opnieuw abonneren' : subscription?.status === 'past_due' ? 'Betaling bijwerken' : 'Abonnement kiezen'}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              </CardBody>
            </Card>
          </motion.div>
        )}

        {/* Onboarding Checklist */}
        {showOnboarding && (
          <motion.div variants={item}>
            <Card className="border-primary-200 bg-gradient-to-r from-primary-50 to-white">
              <CardBody className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100">
                      <Rocket className="h-5 w-5 text-primary-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">Start uw AI-klantenservice</h3>
                      <p className="text-sm text-gray-500">Voltooi deze stappen om live te gaan</p>
                    </div>
                  </div>
                  <button
                    onClick={() => setHideOnboarding(true)}
                    className="text-gray-400 hover:text-gray-600 p-1"
                    title="Verbergen"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <div className="space-y-3 mb-4">
                  {/* Step 1: AI Worker */}
                  <Link
                    href="/dashboard/ai-workers"
                    className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                      hasAIWorker 
                        ? 'bg-green-50 border-green-200' 
                        : 'bg-white border-gray-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {hasAIWorker ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Circle className="h-5 w-5 text-gray-300" />
                      )}
                      <div>
                        <p className={`font-medium ${hasAIWorker ? 'text-green-700' : 'text-gray-900'}`}>
                          AI-medewerker aanmaken
                        </p>
                        <p className="text-xs text-gray-500">Configureer naam, stem en gedrag</p>
                      </div>
                    </div>
                    {!hasAIWorker && <ChevronRight className="h-5 w-5 text-gray-400" />}
                  </Link>

                  {/* Step 2: Phone Number */}
                  <Link
                    href="/dashboard/phone"
                    className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                      hasPhoneNumber && phoneLinkedToAI
                        ? 'bg-green-50 border-green-200' 
                        : 'bg-white border-gray-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {hasPhoneNumber && phoneLinkedToAI ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Circle className="h-5 w-5 text-gray-300" />
                      )}
                      <div>
                        <p className={`font-medium ${hasPhoneNumber && phoneLinkedToAI ? 'text-green-700' : 'text-gray-900'}`}>
                          Telefoonnummer koppelen
                        </p>
                        <p className="text-xs text-gray-500">
                          {hasPhoneNumber && !phoneLinkedToAI 
                            ? 'Koppel uw nummer aan een AI-medewerker' 
                            : 'Vraag een nummer aan en koppel aan AI'}
                        </p>
                      </div>
                    </div>
                    {!(hasPhoneNumber && phoneLinkedToAI) && <ChevronRight className="h-5 w-5 text-gray-400" />}
                  </Link>

                  {/* Step 3: Knowledge */}
                  <Link
                    href="/dashboard/knowledge"
                    className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                      hasKnowledge 
                        ? 'bg-green-50 border-green-200' 
                        : 'bg-white border-gray-200 hover:border-primary-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {hasKnowledge ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <Circle className="h-5 w-5 text-gray-300" />
                      )}
                      <div>
                        <p className={`font-medium ${hasKnowledge ? 'text-green-700' : 'text-gray-900'}`}>
                          Kennisbank vullen
                        </p>
                        <p className="text-xs text-gray-500">Voeg uw website toe of upload documenten</p>
                      </div>
                    </div>
                    {!hasKnowledge && <ChevronRight className="h-5 w-5 text-gray-400" />}
                  </Link>
                </div>

                {/* Progress Bar */}
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary-500 rounded-full transition-all duration-500"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-600">{progressPercent}%</span>
                </div>
              </CardBody>
            </Card>
          </motion.div>
        )}

        {/* Stats Grid — Today */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((stat) => (
            <motion.div key={stat.label} variants={item}>
              <Card className="hover:shadow-soft-lg transition-shadow">
                <CardBody className="flex items-center gap-3 p-4">
                  <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${stat.color}`}>
                    <stat.icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-gray-500 truncate">{stat.label}</p>
                    <p className="text-xl font-bold text-gray-900">{stat.value}</p>
                  </div>
                </CardBody>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Monthly Overview — Two rich cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Prestaties deze maand */}
          <motion.div variants={item}>
            <Card className="h-full">
              <CardHeader>
                <CardTitle>Prestaties deze maand</CardTitle>
              </CardHeader>
              <CardBody className="space-y-5">
                <div>
                  <div className="flex items-baseline gap-1.5 mb-1">
                    <span className="text-4xl font-bold text-gray-900">
                      {stats?.calls_this_month || 0}
                    </span>
                    <span className="text-gray-500">gesprekken</span>
                  </div>
                  <p className="text-sm text-gray-400">deze maand</p>
                </div>

                <div className="border-t pt-4 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Beantwoord</span>
                    <span className="font-medium text-gray-900">
                      {answeredPct}%
                      <span className="text-gray-400 font-normal ml-1">({stats?.calls_missed_month || 0} gemist)</span>
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Gem. gespreksduur</span>
                    <span className="font-medium text-gray-900">
                      {avgDurMin > 0 ? `${avgDurMin}m ${avgDurSec}s` : `${avgDurSec}s`}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">AI-afspraken</span>
                    <span className="font-medium text-gray-900">{stats?.appointments_made_by_ai_month || 0}</span>
                  </div>
                </div>

                {/* Sentiment */}
                {sentimentTotal > 0 ? (
                  <div className="border-t pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium text-gray-700">Klanttevredenheid</span>
                      <span className={`text-lg font-bold ${
                        satisfactionPct! >= 80 ? 'text-green-600' :
                        satisfactionPct! >= 50 ? 'text-amber-600' :
                        'text-red-600'
                      }`}>
                        {satisfactionPct}% tevreden
                      </span>
                    </div>
                    <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden flex">
                      <div
                        className="h-full bg-green-500 transition-all"
                        style={{ width: `${(positiveCount / sentimentTotal) * 100}%` }}
                      />
                      <div
                        className="h-full bg-red-400 transition-all"
                        style={{ width: `${(negativeCount / sentimentTotal) * 100}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-gray-500 mt-2">
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                        Positief ({positiveCount})
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-full bg-red-400" />
                        Negatief ({negativeCount})
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="border-t pt-4">
                    <p className="text-sm text-gray-400 text-center">
                      Klanttevredenheid wordt bijgehouden na nieuwe gesprekken
                    </p>
                  </div>
                )}
              </CardBody>
            </Card>
          </motion.div>

          {/* Right: Belminuten */}
          <motion.div variants={item}>
            <Card className="h-full">
              <CardHeader>
                <CardTitle>Belminuten</CardTitle>
              </CardHeader>
              <CardBody>
                {!usage ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    Geen verbruiksdata beschikbaar
                  </p>
                ) : (
                  <div className="space-y-5">
                    <div>
                      <div className="flex items-end justify-between mb-3">
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-4xl font-bold text-gray-900">
                            {Math.round(usage.minutes_used)}
                          </span>
                          <span className="text-gray-500">
                            {usage.is_unlimited ? 'minuten gebruikt' : `/ ${usage.minutes_limit} min`}
                          </span>
                        </div>
                        {!usage.is_unlimited && (
                          <span className={`text-sm font-semibold ${
                            usage.percentage >= 90 ? 'text-red-600' : usage.percentage >= 75 ? 'text-amber-600' : 'text-primary-600'
                          }`}>
                            {usage.percentage}%
                          </span>
                        )}
                      </div>
                      {!usage.is_unlimited && (
                        <div className="w-full bg-gray-100 rounded-full h-3">
                          <div
                            className={`h-3 rounded-full transition-all ${
                              usage.percentage >= 90 ? 'bg-red-500' : usage.percentage >= 75 ? 'bg-amber-500' : 'bg-primary-500'
                            }`}
                            style={{ width: `${Math.min(usage.percentage, 100)}%` }}
                          />
                        </div>
                      )}
                      {!usage.is_unlimited && usage.percentage >= 100 && (
                        <p className="text-sm text-red-600 mt-2">
                          U heeft uw limiet bereikt. Extra minuten worden gefactureerd a €0,25 per minuut.
                        </p>
                      )}
                      {!usage.is_unlimited && usage.percentage >= 80 && usage.percentage < 100 && (
                        <p className="text-sm text-amber-600 mt-2">
                          U nadert uw limiet. Na het bereiken worden extra minuten gefactureerd a €0,25 per minuut.
                        </p>
                      )}
                    </div>

                    <div className="border-t pt-4 space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Abonnement</span>
                        <span className="font-medium text-gray-900">
                          {usage.plan === 'starter' ? 'Starter' : usage.plan === 'business' ? 'Business' : 'Enterprise'}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Gesprekken deze maand</span>
                        <span className="font-medium text-gray-900">{stats?.calls_this_month || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Gem. per gesprek</span>
                        <span className="font-medium text-gray-900">
                          {(stats?.calls_this_month || 0) > 0
                            ? `${Math.round(usage.minutes_used / stats!.calls_this_month * 10) / 10} min`
                            : '–'}
                        </span>
                      </div>
                      {!usage.is_unlimited && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500">Resterend</span>
                          <span className="font-medium text-gray-900">
                            {Math.max(0, usage.minutes_limit - Math.round(usage.minutes_used))} min
                          </span>
                        </div>
                      )}
                      {usage.overage_minutes > 0 && (
                        <div className="flex justify-between text-sm">
                          <span className="text-red-600">Extra minuten</span>
                          <span className="font-medium text-red-600">
                            {usage.overage_minutes} min (€{usage.overage_cost?.toFixed(2)})
                          </span>
                        </div>
                      )}
                    </div>

                    <Link
                      href="/dashboard/settings?tab=subscription"
                      className="block text-center text-sm text-primary-600 hover:text-primary-700 pt-2 border-t"
                    >
                      Abonnement beheren
                    </Link>
                  </div>
                )}
              </CardBody>
            </Card>
          </motion.div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* AI Workers Status */}
          <motion.div variants={item}>
            <Card className="h-full">
              <CardHeader className="flex items-center justify-between">
                <CardTitle>AI-medewerkers</CardTitle>
                <Link href="/dashboard/ai-workers" className="text-sm text-primary-600 hover:text-primary-700">
                  Beheren
                </Link>
              </CardHeader>
              <CardBody className="space-y-3">
                {workersStatus?.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    Geen AI-medewerkers geconfigureerd
                  </p>
                ) : (
                  workersStatus?.map((worker: any) => (
                    <div
                      key={worker.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100">
                          <Headphones className="h-5 w-5 text-primary-600" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{worker.name}</p>
                          <p className="text-xs text-gray-500">{worker.role_title}</p>
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
                  ))
                )}
              </CardBody>
            </Card>
          </motion.div>

          {/* Recent Calls */}
          <motion.div variants={item}>
            <Card className="h-full">
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Recente gesprekken</CardTitle>
                <Link href="/dashboard/calls" className="text-sm text-primary-600 hover:text-primary-700">
                  Alles bekijken
                </Link>
              </CardHeader>
              <CardBody className="space-y-3">
                {recentCalls?.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    Nog geen gesprekken
                  </p>
                ) : (
                  recentCalls?.map((call: any) => (
                    <div
                      key={call.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`flex h-10 w-10 items-center justify-center rounded-full ${getStatusColor(call.status)}`}>
                          <Phone className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {call.customer_name || call.caller_number}
                          </p>
                          <p className="text-xs text-gray-500">
                            {formatRelativeTime(call.started_at)} • {formatDuration(call.duration_seconds)}
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant={
                          call.status === 'completed' ? 'success' :
                          call.status === 'missed' ? 'danger' : 'gray'
                        }
                      >
                        {getStatusLabel(call.status)}
                      </Badge>
                    </div>
                  ))
                )}
              </CardBody>
            </Card>
          </motion.div>

          {/* Upcoming Appointments */}
          <motion.div variants={item}>
            <Card className="h-full">
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Komende afspraken</CardTitle>
                <Link href="/dashboard/appointments" className="text-sm text-primary-600 hover:text-primary-700">
                  Alles bekijken
                </Link>
              </CardHeader>
              <CardBody className="space-y-3">
                {upcomingAppointments?.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">
                    Geen komende afspraken
                  </p>
                ) : (
                  upcomingAppointments?.map((apt: any) => (
                    <div
                      key={apt.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-gray-50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
                          <Calendar className="h-5 w-5 text-amber-600" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{apt.title}</p>
                          <p className="text-xs text-gray-500">
                            {apt.customer_name} • {apt.duration_minutes} min
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-gray-900">
                          {new Date(apt.starts_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })}
                        </p>
                        <p className="text-xs text-gray-500">
                          {new Date(apt.starts_at).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </CardBody>
            </Card>
          </motion.div>
        </div>

        {/* Action Items */}
        {actionItems && actionItems.length > 0 && (
          <motion.div variants={item}>
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-500" />
                  Actie vereist
                </CardTitle>
                <Link href="/dashboard/notes?action_required=true" className="text-sm text-primary-600 hover:text-primary-700">
                  Alles bekijken
                </Link>
              </CardHeader>
              <CardBody>
                <div className="divide-y divide-gray-100">
                  {actionItems.map((note: any) => (
                    <div key={note.id} className="py-4 first:pt-0 last:pb-0">
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium text-gray-900">{note.title}</p>
                          <p className="mt-1 text-sm text-gray-500">{note.action_description}</p>
                          <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
                            {note.customer_name && <span>{note.customer_name}</span>}
                            {note.customer_phone && <span>• {note.customer_phone}</span>}
                            <span>• {formatRelativeTime(note.created_at)}</span>
                          </div>
                        </div>
                        <Badge
                          variant={
                            note.priority === 'urgent' ? 'danger' :
                            note.priority === 'high' ? 'warning' : 'gray'
                          }
                        >
                          {note.priority}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          </motion.div>
        )}
      </motion.div>
    </DashboardLayout>
  )
}
