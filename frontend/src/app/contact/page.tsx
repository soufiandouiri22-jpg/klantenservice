'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Mail, Phone, MapPin, Send, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'

export default function ContactPage() {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    subject: 'Algemene vraag',
    message: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    // Simulate form submission
    await new Promise(resolve => setTimeout(resolve, 1000))

    // TODO: Implement actual form submission
    console.log('Form submitted:', formData)
    
    setIsSubmitting(false)
    setIsSubmitted(true)
    toast.success('Bericht verzonden! We nemen zo snel mogelijk contact met u op.')
  }

  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-12">
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
              Neem contact op
            </h1>
            <p className="mt-4 text-lg text-gray-600">
              Heeft u vragen over onze AI-telefonisten of wilt u een demo inplannen? 
              Wij helpen u graag verder.
            </p>

            <div className="mt-10 space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <Mail className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">E-mail</h3>
                  <p className="text-gray-600">info@klantenservice.ai</p>
                  <p className="text-sm text-gray-500 mt-1">We reageren binnen 24 uur</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <Phone className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Telefoon</h3>
                  <p className="text-gray-600">+31 (0)20 123 4567</p>
                  <p className="text-sm text-gray-500 mt-1">Ma-vr 9:00 - 17:00</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                  <MapPin className="h-6 w-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Adres</h3>
                  <p className="text-gray-600">Amsterdam, Nederland</p>
                  <p className="text-sm text-gray-500 mt-1">Op afspraak</p>
                </div>
              </div>
            </div>

            {/* FAQ hint */}
            <div className="mt-10 p-6 rounded-xl bg-primary-50 border border-primary-100">
              <h3 className="font-semibold text-gray-900">Veelgestelde vragen?</h3>
              <p className="mt-2 text-gray-600 text-sm">
                Bekijk onze FAQ sectie voor antwoorden op de meest gestelde vragen.
              </p>
              <Link 
                href="/#faq" 
                className="mt-3 inline-flex items-center text-sm font-medium text-primary-600 hover:text-primary-700"
              >
                Naar FAQ
                <ArrowLeft className="ml-1 h-4 w-4 rotate-180" />
              </Link>
            </div>
          </div>

          {/* Right side - Form */}
          <div>
            <div className="bg-white rounded-2xl shadow-soft border border-gray-200 p-8">
              {isSubmitted ? (
                <div className="text-center py-12">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 mx-auto">
                    <Check className="h-8 w-8 text-green-600" />
                  </div>
                  <h2 className="mt-6 text-2xl font-display font-bold text-gray-900">
                    Bericht verzonden!
                  </h2>
                  <p className="mt-2 text-gray-600">
                    Bedankt voor uw bericht. We nemen zo snel mogelijk contact met u op.
                  </p>
                  <button
                    onClick={() => {
                      setIsSubmitted(false)
                      setFormData({
                        name: '',
                        email: '',
                        company: '',
                        phone: '',
                        subject: 'Algemene vraag',
                        message: '',
                      })
                    }}
                    className="mt-6 text-primary-600 font-medium hover:text-primary-700"
                  >
                    Nog een bericht sturen
                  </button>
                </div>
              ) : (
                <>
                  <h2 className="text-xl font-display font-bold text-gray-900 mb-6">
                    Stuur ons een bericht
                  </h2>
                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="grid sm:grid-cols-2 gap-5">
                      <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                          Naam *
                        </label>
                        <input
                          type="text"
                          id="name"
                          name="name"
                          required
                          value={formData.name}
                          onChange={handleChange}
                          className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                          placeholder="Uw naam"
                        />
                      </div>
                      <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                          E-mail *
                        </label>
                        <input
                          type="email"
                          id="email"
                          name="email"
                          required
                          value={formData.email}
                          onChange={handleChange}
                          className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                          placeholder="naam@bedrijf.nl"
                        />
                      </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-5">
                      <div>
                        <label htmlFor="company" className="block text-sm font-medium text-gray-700 mb-1">
                          Bedrijfsnaam
                        </label>
                        <input
                          type="text"
                          id="company"
                          name="company"
                          value={formData.company}
                          onChange={handleChange}
                          className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                          placeholder="Uw bedrijf"
                        />
                      </div>
                      <div>
                        <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">
                          Telefoonnummer
                        </label>
                        <input
                          type="tel"
                          id="phone"
                          name="phone"
                          value={formData.phone}
                          onChange={handleChange}
                          className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
                          placeholder="+31 6 12345678"
                        />
                      </div>
                    </div>

                    <div>
                      <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">
                        Onderwerp
                      </label>
                      <select
                        id="subject"
                        name="subject"
                        value={formData.subject}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors bg-white"
                      >
                        <option value="Algemene vraag">Algemene vraag</option>
                        <option value="Demo aanvragen">Demo aanvragen</option>
                        <option value="Prijsinformatie">Prijsinformatie</option>
                        <option value="Technische vraag">Technische vraag</option>
                        <option value="Partnership">Partnership</option>
                        <option value="Anders">Anders</option>
                      </select>
                    </div>

                    <div>
                      <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
                        Bericht *
                      </label>
                      <textarea
                        id="message"
                        name="message"
                        required
                        rows={5}
                        value={formData.message}
                        onChange={handleChange}
                        className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors resize-none"
                        placeholder="Hoe kunnen we u helpen?"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full bg-primary-600 text-white px-6 py-4 rounded-lg font-semibold hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                          Verzenden...
                        </>
                      ) : (
                        <>
                          Verstuur bericht
                          <Send className="h-5 w-5" />
                        </>
                      )}
                    </button>

                    <p className="text-xs text-gray-500 text-center">
                      Door dit formulier te verzenden gaat u akkoord met onze{' '}
                      <Link href="/privacy" className="text-primary-600 hover:underline">
                        privacyverklaring
                      </Link>
                      .
                    </p>
                  </form>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  )
}
