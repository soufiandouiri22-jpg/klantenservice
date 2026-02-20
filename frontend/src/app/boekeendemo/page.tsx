'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Calendar, Clock, Video, CheckCircle2, Users, Headphones } from 'lucide-react'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'

export default function BookDemoPage() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedTime, setSelectedTime] = useState<string | null>(null)

  // Fake dates for the next 2 weeks (skip weekends)
  const today = new Date()
  const dates: Date[] = []
  let daysAdded = 0
  let currentDate = new Date(today)
  
  while (dates.length < 7) {
    currentDate = new Date(today)
    currentDate.setDate(today.getDate() + daysAdded + 1)
    // Skip weekends (0 = Sunday, 6 = Saturday)
    if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
      dates.push(new Date(currentDate))
    }
    daysAdded++
  }

  const times = ['09:00', '10:00', '11:00', '14:00', '15:00', '16:00']

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'short' })
  }

  const formatDateKey = (date: Date) => {
    return date.toISOString().split('T')[0]
  }

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 sm:pt-24 md:pt-28 pb-12">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-8"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Terug naar home
        </Link>

        <div className="grid lg:grid-cols-2 gap-12">
          {/* Left side - Info */}
          <div>
            <h1 className="text-4xl font-display font-bold text-gray-900">
              Plan een demo
            </h1>
            <p className="mt-4 text-lg text-gray-600">
              Ontdek hoe klantenservice.ai uw bedrijf kan helpen met een persoonlijke demo van 30 minuten.
            </p>

            <div className="mt-10 space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <Video className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Video call</h3>
                  <p className="text-gray-600">Via Google Meet of Zoom, naar uw voorkeur</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <Clock className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">30 minuten</h3>
                  <p className="text-gray-600">Korte, efficiënte introductie op maat</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <Users className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Persoonlijk</h3>
                  <p className="text-gray-600">Met een product specialist die uw vragen beantwoordt</p>
                </div>
              </div>
            </div>

            {/* What to expect */}
            <div className="mt-10 p-6 rounded-xl bg-gray-50 border border-gray-100">
              <h3 className="font-semibold text-gray-900 mb-4">Wat kunt u verwachten?</h3>
              <ul className="space-y-3">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600">Live demonstratie van de AI-telefonist</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600">Bespreken van uw specifieke use case</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600">Integratie mogelijkheden met uw systemen</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600">Prijsindicatie op maat</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Right side - Calendar (Fake Calendly) */}
          <div>
            <div className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden">
              {/* Calendar Header */}
              <div className="bg-primary-600 text-white p-4 sm:p-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/20">
                    <Headphones className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="font-semibold">klantenservice.ai</p>
                    <p className="text-sm text-primary-200">Product Demo</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 mt-4 text-sm text-primary-100">
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    30 min
                  </span>
                  <span className="flex items-center gap-1">
                    <Video className="h-4 w-4" />
                    Google Meet
                  </span>
                </div>
              </div>

              {/* Calendar Body */}
              <div className="p-4 sm:p-6">
                <h3 className="font-semibold text-gray-900 mb-4">Selecteer een datum</h3>
                
                {/* Date selector */}
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 mb-6">
                  {dates.map((date) => {
                    const dateKey = formatDateKey(date)
                    const isSelected = selectedDate === dateKey
                    return (
                      <button
                        key={dateKey}
                        onClick={() => {
                          setSelectedDate(dateKey)
                          setSelectedTime(null)
                        }}
                        className={`p-3 rounded-lg text-center transition-all ${
                          isSelected
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-50 hover:bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p className={`text-xs ${isSelected ? 'text-primary-200' : 'text-gray-500'}`}>
                          {date.toLocaleDateString('nl-NL', { weekday: 'short' })}
                        </p>
                        <p className="text-lg font-semibold">{date.getDate()}</p>
                      </button>
                    )
                  })}
                </div>

                {/* Time selector */}
                {selectedDate && (
                  <div className="animate-fadeIn">
                    <h3 className="font-semibold text-gray-900 mb-4">Selecteer een tijd</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {times.map((time) => {
                        const isSelected = selectedTime === time
                        return (
                          <button
                            key={time}
                            onClick={() => setSelectedTime(time)}
                            className={`p-3 rounded-lg text-center font-medium transition-all ${
                              isSelected
                                ? 'bg-primary-600 text-white'
                                : 'bg-gray-50 hover:bg-gray-100 text-gray-900'
                            }`}
                          >
                            {time}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Confirm button */}
                {selectedDate && selectedTime && (
                  <div className="mt-6 animate-fadeIn">
                    <div className="p-4 rounded-lg bg-primary-50 border border-primary-100 mb-4">
                      <p className="text-sm text-primary-700">
                        <strong>Geselecteerd:</strong>{' '}
                        {new Date(selectedDate).toLocaleDateString('nl-NL', { 
                          weekday: 'long', 
                          day: 'numeric', 
                          month: 'long' 
                        })} om {selectedTime}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        // TODO: Integrate with real Calendly
                        alert('Calendly integratie komt binnenkort! Neem contact op via info@klantenservice.ai')
                      }}
                      className="w-full bg-primary-600 text-white px-6 py-4 rounded-lg font-semibold hover:bg-primary-700 transition-colors flex items-center justify-center gap-2"
                    >
                      <Calendar className="h-5 w-5" />
                      Bevestig afspraak
                    </button>
                    <p className="text-xs text-gray-500 text-center mt-3">
                      U ontvangt een bevestiging per e-mail
                    </p>
                  </div>
                )}

                {/* Powered by badge */}
                <div className="mt-6 pt-4 border-t border-gray-100 text-center">
                  <p className="text-xs text-gray-400">
                    Powered by Calendly
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  )
}
