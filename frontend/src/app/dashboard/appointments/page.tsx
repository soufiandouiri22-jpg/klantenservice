'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Calendar, Clock, User, X, Search, Filter, List, CalendarDays } from 'lucide-react'
import toast from 'react-hot-toast'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { PageLoader } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Select'
import { appointmentsApi } from '@/lib/api'
import { formatDateTime, formatDate, getStatusLabel } from '@/lib/utils'

// Mock data for calendar view (when backend is not running)
const MOCK_APPOINTMENTS = [
  {
    id: '1',
    title: 'Knippen - Jan de Vries',
    customer_name: 'Jan de Vries',
    customer_phone: '+31612345678',
    customer_email: 'jan@email.nl',
    starts_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(), // 2 hours from now
    ends_at: new Date(Date.now() + 2.5 * 60 * 60 * 1000).toISOString(),
    duration_minutes: 30,
    status: 'confirmed',
    description: 'Knippen en stylen',
  },
  {
    id: '2',
    title: 'Kleuren - Marie Jansen',
    customer_name: 'Marie Jansen',
    customer_phone: '+31687654321',
    customer_email: 'marie@email.nl',
    starts_at: new Date(Date.now() + 24 * 60 * 60 * 1000 + 10 * 60 * 60 * 1000).toISOString(), // Tomorrow 10:00
    ends_at: new Date(Date.now() + 24 * 60 * 60 * 1000 + 12 * 60 * 60 * 1000).toISOString(),
    duration_minutes: 120,
    status: 'confirmed',
    description: 'Volledige kleuring',
  },
  {
    id: '3',
    title: 'Consult - Peter Bakker',
    customer_name: 'Peter Bakker',
    customer_phone: '+31698765432',
    customer_email: 'peter@email.nl',
    starts_at: new Date(Date.now() + 48 * 60 * 60 * 1000 + 14 * 60 * 60 * 1000).toISOString(), // Day after tomorrow 14:00
    ends_at: new Date(Date.now() + 48 * 60 * 60 * 1000 + 14.5 * 60 * 60 * 1000).toISOString(),
    duration_minutes: 30,
    status: 'confirmed',
    description: 'Adviesgesprek',
  },
]

export default function AppointmentsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [selectedAppointment, setSelectedAppointment] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')

  const { data: appointmentsData, isLoading } = useQuery({
    queryKey: ['appointments', page, searchQuery, statusFilter],
    queryFn: async () => {
      try {
        return await appointmentsApi.list({
          page,
          page_size: 20,
          search: searchQuery || undefined,
          status: statusFilter || undefined,
        })
      } catch {
        // Return mock data if backend is not available
        return { items: MOCK_APPOINTMENTS, total: MOCK_APPOINTMENTS.length, total_pages: 1, page: 1 }
      }
    },
  })

  const { data: todayAppointments } = useQuery({
    queryKey: ['appointments-today'],
    queryFn: async () => {
      try {
        return await appointmentsApi.getToday()
      } catch {
        // Return today's mock appointments
        const today = new Date().toDateString()
        return MOCK_APPOINTMENTS.filter(apt => new Date(apt.starts_at).toDateString() === today)
      }
    },
  })

  // Get all appointments for calendar view
  const { data: allAppointments } = useQuery({
    queryKey: ['appointments-all'],
    queryFn: async () => {
      try {
        const result = await appointmentsApi.list({ page: 1, page_size: 100 })
        return result.items
      } catch {
        return MOCK_APPOINTMENTS
      }
    },
  })

  // Convert appointments to FullCalendar events
  const calendarEvents = (allAppointments || MOCK_APPOINTMENTS).map((apt: any) => ({
    id: apt.id,
    title: apt.title,
    start: apt.starts_at,
    end: apt.ends_at,
    backgroundColor: apt.status === 'confirmed' ? '#2563eb' : apt.status === 'cancelled' ? '#dc2626' : '#6b7280',
    borderColor: apt.status === 'confirmed' ? '#1d4ed8' : apt.status === 'cancelled' ? '#b91c1c' : '#4b5563',
    extendedProps: apt,
  }))

  const cancelMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      appointmentsApi.cancel(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      queryClient.invalidateQueries({ queryKey: ['appointments-today'] })
      toast.success('Afspraak geannuleerd')
      setSelectedAppointment(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Fout bij annuleren')
    },
  })

  if (isLoading) {
    return (
      <DashboardLayout>
        <PageLoader />
      </DashboardLayout>
    )
  }

  const appointments = appointmentsData?.items || []

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'gray'> = {
      confirmed: 'success',
      held: 'warning',
      cancelled: 'danger',
      completed: 'gray',
      no_show: 'danger',
    }
    return variants[status] || 'gray'
  }

  const handleEventClick = (info: any) => {
    setSelectedAppointment(info.event.extendedProps)
  }

  return (
    <DashboardLayout>
      <Header
        title="Afspraken"
        description="Beheer alle gemaakte afspraken."
        actions={
          <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'list'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <List className="h-4 w-4" />
              Lijst
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'calendar'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <CalendarDays className="h-4 w-4" />
              Kalender
            </button>
          </div>
        }
      />

      <div className="p-4 sm:p-6 space-y-6">
        {/* Calendar View */}
        {viewMode === 'calendar' && (
          <Card>
            <CardBody>
              <FullCalendar
                plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                initialView="timeGridWeek"
                headerToolbar={{
                  left: 'prev,next today',
                  center: 'title',
                  right: 'dayGridMonth,timeGridWeek,timeGridDay',
                }}
                locale="nl"
                buttonText={{
                  today: 'Vandaag',
                  month: 'Maand',
                  week: 'Week',
                  day: 'Dag',
                }}
                events={calendarEvents}
                eventClick={handleEventClick}
                slotMinTime="07:00:00"
                slotMaxTime="21:00:00"
                allDaySlot={false}
                weekends={true}
                nowIndicator={true}
                slotDuration="00:30:00"
                height="auto"
                eventTimeFormat={{
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false,
                }}
                slotLabelFormat={{
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false,
                }}
                dayHeaderFormat={{
                  weekday: 'short',
                  day: 'numeric',
                  month: 'short',
                }}
              />
            </CardBody>
          </Card>
        )}

        {/* List View */}
        {viewMode === 'list' && (
          <>
            {/* Today's Appointments */}
        {todayAppointments && todayAppointments.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary-600" />
                Afspraken vandaag ({todayAppointments.length})
              </CardTitle>
            </CardHeader>
            <CardBody className="p-0">
              <div className="divide-y divide-gray-100">
                {todayAppointments.map((apt: any) => (
                  <div
                    key={apt.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedAppointment(apt)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex flex-col items-center justify-center w-16 h-16 flex-shrink-0 rounded-lg bg-primary-50">
                        <span className="text-2xl font-bold text-primary-600">
                          {new Date(apt.starts_at).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{apt.title}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <User className="h-3 w-3" />
                          <span>{apt.customer_name}</span>
                          <span>•</span>
                          <Clock className="h-3 w-3" />
                          <span>{apt.duration_minutes} min</span>
                        </div>
                      </div>
                    </div>
                    <Badge variant={getStatusBadge(apt.status)}>
                      {getStatusLabel(apt.status)}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        )}

        {/* Search & Filter */}
        <Card>
          <CardBody>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Zoek op naam of titel..."
                  className="input pl-10"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Select
                className="w-full sm:w-48"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">Alle statussen</option>
                <option value="confirmed">Bevestigd</option>
                <option value="cancelled">Geannuleerd</option>
                <option value="completed">Afgerond</option>
                <option value="no_show">Niet verschenen</option>
              </Select>
            </div>
          </CardBody>
        </Card>

        {/* All Appointments */}
        <Card>
          <CardHeader>
            <CardTitle>Alle afspraken ({appointmentsData?.total || 0})</CardTitle>
          </CardHeader>
          <CardBody className="p-0">
            {appointments.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={Calendar}
                  title="Geen afspraken gevonden"
                  description="Er zijn nog geen afspraken gemaakt of uw zoekopdracht leverde geen resultaten op."
                />
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {appointments.map((apt: any) => (
                  <motion.div
                    key={apt.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center justify-between p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedAppointment(apt)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-gray-100">
                        <Calendar className="h-6 w-6 text-gray-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{apt.title}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <User className="h-3 w-3" />
                          <span>{apt.customer_name}</span>
                          <span>•</span>
                          <span>{formatDateTime(apt.starts_at)}</span>
                          <span>•</span>
                          <span>{apt.duration_minutes} min</span>
                        </div>
                      </div>
                    </div>
                    <Badge variant={getStatusBadge(apt.status)}>
                      {getStatusLabel(apt.status)}
                    </Badge>
                  </motion.div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

            {/* Pagination */}
            {appointmentsData && appointmentsData.total_pages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Vorige
                </Button>
                <span className="text-sm text-gray-600">
                  Pagina {page} van {appointmentsData.total_pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === appointmentsData.total_pages}
                  onClick={() => setPage(page + 1)}
                >
                  Volgende
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Appointment Detail Modal */}
      <Modal
        isOpen={!!selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
        title="Afspraakdetails"
        size="lg"
      >
        {selectedAppointment && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Titel</p>
                <p className="font-medium text-gray-900">{selectedAppointment.title}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <Badge variant={getStatusBadge(selectedAppointment.status)}>
                  {getStatusLabel(selectedAppointment.status)}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-gray-500">Klant</p>
                <p className="font-medium text-gray-900">{selectedAppointment.customer_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Telefoon</p>
                <p className="font-medium text-gray-900">{selectedAppointment.customer_phone || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">E-mail</p>
                <p className="font-medium text-gray-900">{selectedAppointment.customer_email || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Duur</p>
                <p className="font-medium text-gray-900">{selectedAppointment.duration_minutes} minuten</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Start</p>
                <p className="font-medium text-gray-900">{formatDateTime(selectedAppointment.starts_at)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Einde</p>
                <p className="font-medium text-gray-900">{formatDateTime(selectedAppointment.ends_at)}</p>
              </div>
            </div>

            {selectedAppointment.description && (
              <div>
                <p className="text-sm text-gray-500 mb-2">Beschrijving</p>
                <div className="p-3 rounded-lg bg-gray-50">
                  <p className="text-sm text-gray-700">{selectedAppointment.description}</p>
                </div>
              </div>
            )}

            {selectedAppointment.status === 'confirmed' && (
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <Button variant="outline" onClick={() => setSelectedAppointment(null)}>
                  Sluiten
                </Button>
                <Button
                  variant="danger"
                  leftIcon={<X className="h-4 w-4" />}
                  onClick={() => {
                    if (confirm('Weet u zeker dat u deze afspraak wilt annuleren?')) {
                      cancelMutation.mutate({ id: selectedAppointment.id })
                    }
                  }}
                  isLoading={cancelMutation.isPending}
                >
                  Annuleren
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>
    </DashboardLayout>
  )
}
