'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  DollarSign,
  Phone,
  TrendingUp,
  Calendar,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  CreditCard,
  Users,
  UserCheck,
  Clock,
} from 'lucide-react'
import {
  format,
  subDays,
  startOfMonth,
  endOfMonth,
  subMonths,
  startOfDay,
  endOfDay,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  isAfter,
  isBefore,
  addMonths,
  startOfWeek,
  endOfWeek,
} from 'date-fns'
import { nl } from 'date-fns/locale'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

type Preset = {
  label: string
  getRange: () => [Date, Date]
}

const PRESETS: Preset[] = [
  { label: 'Vandaag', getRange: () => [startOfDay(new Date()), endOfDay(new Date())] },
  { label: '7 dagen', getRange: () => [startOfDay(subDays(new Date(), 6)), endOfDay(new Date())] },
  { label: '30 dagen', getRange: () => [startOfDay(subDays(new Date(), 29)), endOfDay(new Date())] },
  { label: 'Deze maand', getRange: () => [startOfMonth(new Date()), endOfDay(new Date())] },
  { label: 'Vorige maand', getRange: () => [startOfMonth(subMonths(new Date(), 1)), endOfMonth(subMonths(new Date(), 1))] },
  { label: '3 maanden', getRange: () => [startOfDay(subDays(new Date(), 89)), endOfDay(new Date())] },
]

function MiniCalendar({
  month,
  rangeStart,
  rangeEnd,
  hoverDate,
  onSelect,
  onHover,
  onMonthChange,
  showNav,
}: {
  month: Date
  rangeStart: Date | null
  rangeEnd: Date | null
  hoverDate: Date | null
  onSelect: (d: Date) => void
  onHover: (d: Date | null) => void
  onMonthChange: (d: Date) => void
  showNav: 'left' | 'right' | 'both'
}) {
  const weekStart = startOfWeek(startOfMonth(month), { locale: nl })
  const weekEnd = endOfWeek(endOfMonth(month), { locale: nl })
  const days = eachDayOfInterval({ start: weekStart, end: weekEnd })
  const weekDays = ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo']

  const isInRange = (day: Date) => {
    if (!rangeStart) return false
    const end = rangeEnd || hoverDate
    if (!end) return false
    const [a, b] = isAfter(end, rangeStart) ? [rangeStart, end] : [end, rangeStart]
    return (isAfter(day, a) || isSameDay(day, a)) && (isBefore(day, b) || isSameDay(day, b))
  }

  const isStart = (day: Date) => rangeStart && isSameDay(day, rangeStart)
  const isEnd = (day: Date) => {
    const end = rangeEnd || hoverDate
    return end && isSameDay(day, end)
  }

  return (
    <div className="w-[280px]">
      <div className="flex items-center justify-between mb-3">
        {showNav === 'left' || showNav === 'both' ? (
          <button onClick={() => onMonthChange(subMonths(month, 1))} className="p-1 hover:bg-gray-100 rounded">
            <ChevronLeft className="h-4 w-4 text-gray-600" />
          </button>
        ) : <div className="w-6" />}
        <span className="text-sm font-medium text-gray-900">
          {format(month, 'MMMM yyyy', { locale: nl })}
        </span>
        {showNav === 'right' || showNav === 'both' ? (
          <button onClick={() => onMonthChange(addMonths(month, 1))} className="p-1 hover:bg-gray-100 rounded">
            <ChevronRight className="h-4 w-4 text-gray-600" />
          </button>
        ) : <div className="w-6" />}
      </div>
      <div className="grid grid-cols-7 gap-0">
        {weekDays.map(d => (
          <div key={d} className="text-center text-xs font-medium text-gray-400 py-1">{d}</div>
        ))}
        {days.map((day, i) => {
          const inCurrentMonth = isSameMonth(day, month)
          const inRange = isInRange(day)
          const start = isStart(day)
          const end = isEnd(day)
          const isToday = isSameDay(day, new Date())
          return (
            <button
              key={i}
              onClick={() => inCurrentMonth && onSelect(day)}
              onMouseEnter={() => inCurrentMonth && onHover(day)}
              onMouseLeave={() => onHover(null)}
              disabled={!inCurrentMonth}
              className={`
                h-8 text-xs relative transition-colors
                ${!inCurrentMonth ? 'text-gray-300 cursor-default' : 'cursor-pointer hover:bg-gray-50'}
                ${inRange && inCurrentMonth ? 'bg-primary-50' : ''}
                ${start ? 'bg-primary-500 text-white rounded-l-full hover:bg-primary-600' : ''}
                ${end && !start ? 'bg-primary-500 text-white rounded-r-full hover:bg-primary-600' : ''}
                ${isToday && !start && !end ? 'font-bold text-primary-600' : ''}
                ${!start && !end && inCurrentMonth ? 'text-gray-700' : ''}
              `}
            >
              {format(day, 'd')}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function DateRangePicker({
  startDate,
  endDate,
  onChange,
}: {
  startDate: Date
  endDate: Date
  onChange: (start: Date, end: Date) => void
}) {
  const [open, setOpen] = useState(false)
  const [selecting, setSelecting] = useState<'start' | 'end' | null>(null)
  const [tempStart, setTempStart] = useState<Date | null>(null)
  const [hoverDate, setHoverDate] = useState<Date | null>(null)
  const [leftMonth, setLeftMonth] = useState(startOfMonth(subMonths(new Date(), 1)))
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setSelecting(null)
        setTempStart(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const rightMonth = addMonths(leftMonth, 1)

  const handleSelect = (day: Date) => {
    if (!selecting || selecting === 'start') {
      setTempStart(day)
      setSelecting('end')
    } else {
      const [a, b] = isAfter(day, tempStart!) ? [tempStart!, day] : [day, tempStart!]
      onChange(startOfDay(a), endOfDay(b))
      setOpen(false)
      setSelecting(null)
      setTempStart(null)
    }
  }

  const displayStart = tempStart || startDate
  const displayEnd = selecting === 'end' ? null : endDate

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setOpen(!open); if (!open) setSelecting('start') }}
        className={`
          flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border transition-colors
          ${open ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-300 text-gray-700 hover:border-gray-400'}
        `}
      >
        <Calendar className="h-4 w-4" />
        <span>
          {format(startDate, 'd MMM', { locale: nl })} – {format(endDate, 'd MMM yyyy', { locale: nl })}
        </span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 bg-white rounded-xl shadow-xl border border-gray-200 p-4 z-50">
          <div className="flex gap-4">
            <div className="border-r border-gray-100 pr-4 space-y-1">
              <p className="text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">Snel kiezen</p>
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => {
                    const [s, e] = p.getRange()
                    onChange(s, e)
                    setLeftMonth(startOfMonth(subMonths(e, 1)))
                    setOpen(false)
                    setSelecting(null)
                    setTempStart(null)
                  }}
                  className="block w-full text-left text-sm px-3 py-1.5 rounded-md hover:bg-gray-100 text-gray-700"
                >
                  {p.label}
                </button>
              ))}
            </div>
            <MiniCalendar
              month={leftMonth}
              rangeStart={displayStart}
              rangeEnd={displayEnd}
              hoverDate={hoverDate}
              onSelect={handleSelect}
              onHover={setHoverDate}
              onMonthChange={setLeftMonth}
              showNav="left"
            />
            <MiniCalendar
              month={rightMonth}
              rangeStart={displayStart}
              rangeEnd={displayEnd}
              hoverDate={hoverDate}
              onSelect={handleSelect}
              onHover={setHoverDate}
              onMonthChange={(m) => setLeftMonth(subMonths(m, 1))}
              showNav="right"
            />
          </div>
          {selecting === 'end' && (
            <p className="text-xs text-gray-400 mt-3 text-center">Klik op een einddatum</p>
          )}
        </div>
      )}
    </div>
  )
}

export function FinanceTab() {
  const [startDate, setStartDate] = useState(() => startOfDay(new Date()))
  const [endDate, setEndDate] = useState(() => endOfDay(new Date()))
  const [activePreset, setActivePreset] = useState('Vandaag')

  const startStr = format(startDate, 'yyyy-MM-dd')
  const endStr = format(endDate, 'yyyy-MM-dd')

  const { data: costs, isLoading: costsLoading, refetch: refetchCosts } = useQuery({
    queryKey: ['finance-costs', startStr, endStr],
    queryFn: () => adminApi.getCostMetrics(startStr, endStr),
    refetchInterval: 60000,
  })

  const { data: business, isLoading: businessLoading, refetch: refetchBusiness } = useQuery({
    queryKey: ['finance-business'],
    queryFn: () => adminApi.getBusinessMetrics(),
    refetchInterval: 60000,
  })

  const handlePreset = (preset: Preset) => {
    const [s, e] = preset.getRange()
    setStartDate(s)
    setEndDate(e)
    setActivePreset(preset.label)
  }

  const handleCustomRange = (s: Date, e: Date) => {
    setStartDate(s)
    setEndDate(e)
    setActivePreset('')
  }

  const formatCurrency = (cents: number) => `€${(cents / 100).toFixed(2)}`

  const costPerCall = useMemo(() => {
    if (!costs || !costs.twilio_calls_today || costs.twilio_calls_today === 0) return 0
    return (costs.twilio_calls_cost_month_cents + costs.twilio_media_streams_cost_month_cents + (costs.elevenlabs_cost_today_cents || 0)) / costs.twilio_calls_today
  }, [costs])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-gray-900">Finance</h2>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex bg-gray-100 rounded-lg p-0.5 gap-0.5">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => handlePreset(p)}
                className={`
                  px-3 py-1.5 text-sm rounded-md transition-colors
                  ${activePreset === p.label
                    ? 'bg-white text-gray-900 shadow-sm font-medium'
                    : 'text-gray-500 hover:text-gray-700'
                  }
                `}
              >
                {p.label}
              </button>
            ))}
          </div>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={handleCustomRange}
          />
          <Button variant="outline" size="sm" onClick={() => { refetchCosts(); refetchBusiness() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Revenue Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardBody className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-green-100">
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">MRR</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(business?.mrr_cents || 0)}</p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-100">
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">ARR</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(business?.arr_cents || 0)}</p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-purple-100">
                <CreditCard className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Kosten (periode)</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(costs?.total_cost_today_cents || 0)}</p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-amber-100">
                <Phone className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Gem. kosten/call</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(costPerCall)}</p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Detailed Cost Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Selected period */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Calendar className="h-4 w-4 text-gray-400" />
              Kosten — {activePreset || `${format(startDate, 'd MMM', { locale: nl })} – ${format(endDate, 'd MMM yyyy', { locale: nl })}`}
            </CardTitle>
          </CardHeader>
          <CardBody>
            {costsLoading ? (
              <Spinner />
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center py-2">
                  <div className="flex items-center gap-2">
                    <img src="/app-icons/elevenlabs.svg" alt="ElevenLabs" className="h-5 w-5" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    <div>
                      <span className="text-gray-700 font-medium">ElevenLabs</span>
                      <p className="text-xs text-gray-400">{(costs?.elevenlabs_characters_today || 0).toLocaleString()} characters</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.elevenlabs_cost_today_cents || 0)}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <div className="flex items-center gap-2">
                    <Phone className="h-5 w-5 text-red-500" />
                    <div>
                      <span className="text-gray-700 font-medium">Twilio</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_calls_today || 0} calls · {costs?.twilio_minutes_today || 0} min</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.twilio_cost_today_cents || 0)}</span>
                </div>
                <div className="border-t pt-3 flex justify-between items-center">
                  <span className="font-semibold text-gray-900">Totaal</span>
                  <span className="text-xl font-bold text-primary-600">{formatCurrency(costs?.total_cost_today_cents || 0)}</span>
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Calendar month (always current) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Clock className="h-4 w-4 text-gray-400" />
              Kosten — Deze maand ({format(new Date(), 'MMMM yyyy', { locale: nl })})
            </CardTitle>
          </CardHeader>
          <CardBody>
            {costsLoading ? (
              <Spinner />
            ) : (
              <div className="space-y-4">
                <div className="flex justify-between items-center py-2">
                  <div className="flex items-center gap-2">
                    <img src="/app-icons/elevenlabs.svg" alt="ElevenLabs" className="h-5 w-5" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    <div>
                      <span className="text-gray-700 font-medium">ElevenLabs</span>
                      <p className="text-xs text-gray-400">{(costs?.elevenlabs_characters_month || 0).toLocaleString()} characters</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.elevenlabs_cost_month_cents || 0)}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <div className="flex items-center gap-2">
                    <Phone className="h-5 w-5 text-red-500" />
                    <div>
                      <span className="text-gray-700 font-medium">Belkosten</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_calls_month || 0} calls · {costs?.twilio_minutes_month || 0} min</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.twilio_calls_cost_month_cents || 0)}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <div className="flex items-center gap-2">
                    <Phone className="h-5 w-5 text-gray-400" />
                    <div>
                      <span className="text-gray-700 font-medium">Telefoonnummers</span>
                      <p className="text-xs text-gray-400">{costs?.twilio_numbers_count_month || 0} nummers</p>
                    </div>
                  </div>
                  <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs?.twilio_numbers_cost_month_cents || 0)}</span>
                </div>
                {(costs?.twilio_media_streams_cost_month_cents || 0) > 0 && (
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-700 font-medium">Media Streams</span>
                    <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs.twilio_media_streams_cost_month_cents)}</span>
                  </div>
                )}
                {(costs?.twilio_recordings_cost_month_cents || 0) > 0 && (
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-700 font-medium">Opnames</span>
                    <span className="text-lg font-semibold text-gray-900">{formatCurrency(costs.twilio_recordings_cost_month_cents)}</span>
                  </div>
                )}
                <div className="border-t pt-3 flex justify-between items-center">
                  <span className="font-semibold text-gray-900">Totaal</span>
                  <span className="text-xl font-bold text-primary-600">{formatCurrency(costs?.total_cost_month_cents || 0)}</span>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Customer + Revenue breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-gray-500" />
            Klanten & Omzet per Plan
          </CardTitle>
        </CardHeader>
        <CardBody>
          {businessLoading ? (
            <Spinner />
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-green-50 rounded-lg p-4 text-center">
                  <UserCheck className="h-5 w-5 text-green-600 mx-auto mb-1" />
                  <p className="text-2xl font-bold text-green-700">{business?.active_customers || 0}</p>
                  <p className="text-xs text-green-600">Actief</p>
                </div>
                <div className="bg-amber-50 rounded-lg p-4 text-center">
                  <Clock className="h-5 w-5 text-amber-600 mx-auto mb-1" />
                  <p className="text-2xl font-bold text-amber-700">{business?.trialing_customers || 0}</p>
                  <p className="text-xs text-amber-600">Proefperiode</p>
                </div>
                <div className="bg-blue-50 rounded-lg p-4 text-center">
                  <CreditCard className="h-5 w-5 text-blue-600 mx-auto mb-1" />
                  <p className="text-2xl font-bold text-blue-700">{business?.trial_to_paid_rate?.toFixed(1) || 0}%</p>
                  <p className="text-xs text-blue-600">Conversie</p>
                </div>
                <div className="bg-red-50 rounded-lg p-4 text-center">
                  <TrendingUp className="h-5 w-5 text-red-500 mx-auto mb-1" />
                  <p className="text-2xl font-bold text-red-600">{business?.churned_this_month || 0}</p>
                  <p className="text-xs text-red-500">Churn deze maand</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { plan: 'Starter', price: '€149/mo', yearly: '€1.490/jr', count: business?.starter_customers || 0, color: 'blue' },
                  { plan: 'Business', price: '€299/mo', yearly: '€2.990/jr', count: business?.business_customers || 0, color: 'purple' },
                  { plan: 'Enterprise', price: 'Op aanvraag', yearly: '', count: business?.enterprise_customers || 0, color: 'amber' },
                ].map(({ plan, price, yearly, count, color }) => (
                  <div key={plan} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-sm font-medium text-gray-700">{plan}</span>
                        <p className="text-xs text-gray-400">{price}{yearly ? ` · ${yearly}` : ''}</p>
                      </div>
                      <span className="text-xl font-bold text-gray-900">{count}</span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full bg-${color}-500`}
                        style={{ width: `${business?.active_customers ? (count / business.active_customers * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
