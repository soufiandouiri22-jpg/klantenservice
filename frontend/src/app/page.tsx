'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { ArrowRight, Check, Headphones, Calendar, Globe, MessageSquare, Shield, Zap, Plus, Minus, Phone, Mail, Play, UserPlus, Settings, PhoneCall, Link2, Menu, X } from 'lucide-react'
import Image from 'next/image'

const features = [
  {
    icon: Headphones,
    title: 'AI-Telefonisten',
    description: 'Intelligente medewerkers die 24/7 uw telefoon beantwoorden met vloeiend Nederlands.',
  },
  {
    icon: Calendar,
    title: 'Agenda Integratie',
    description: 'Automatisch afspraken inplannen in Google Calendar, Outlook of CalDAV.',
  },
  {
    icon: Globe,
    title: 'Website Kennis',
    description: 'De AI leert automatisch van uw website en beantwoordt vragen accuraat.',
  },
  {
    icon: MessageSquare,
    title: 'Interne Notities',
    description: 'Belangrijke berichten en terugbelverzoeken worden netjes genoteerd.',
  },
  {
    icon: Shield,
    title: 'AVG Compliant',
    description: 'Volledig GDPR-compliant met EU hosting en configureerbare dataretentie.',
  },
  {
    icon: Zap,
    title: 'Direct Operationeel',
    description: 'Binnen enkele minuten opgezet en klaar om gesprekken aan te nemen.',
  },
]

const plans = [
  {
    name: 'Starter',
    price: '59',
    workers: 1,
    description: 'Perfect voor kleine ondernemers',
    features: ['1 AI-medewerker', 'Onbeperkte gesprekken', 'Agenda integratie', 'Website kennis', '30 dagen logs'],
  },
  {
    name: 'Business',
    price: '99',
    workers: 5,
    popular: true,
    description: 'Ideaal voor groeiende bedrijven',
    features: ['5 AI-medewerkers', 'Alles van Starter', 'Prioriteit support', '90 dagen logs', 'API toegang'],
  },
  {
    name: 'Enterprise',
    price: 'Op aanvraag',
    workers: 7,
    description: 'Voor grote organisaties',
    features: ['7+ AI-medewerkers', 'Alles van Business', 'Dedicated support', 'Onbeperkte logs', 'Custom integraties'],
  },
]

const howItWorks = [
  {
    step: '1',
    icon: UserPlus,
    title: 'Account aanmaken',
    description: 'Registreer met uw bedrijfsgegevens. Probeer het gratis, direct aan de slag.',
    time: '2 min',
  },
  {
    step: '2',
    icon: Settings,
    title: 'AI configureren',
    description: 'Koppel uw website en stel gedragsregels in. De AI leert automatisch alles.',
    time: '5 min',
  },
  {
    step: '3',
    icon: PhoneCall,
    title: 'Doorschakelen',
    description: 'Schakel uw telefoonnummer door naar uw nieuwe AI-medewerker. Klaar!',
    time: '1 min',
  },
]

const integrations = [
  { name: 'Google Calendar', logo: '/integrations/google-calendar.svg' },
  { name: 'Microsoft Outlook', logo: '/integrations/outlook.svg' },
  { name: 'Apple Calendar', logo: '/integrations/apple-calendar.svg' },
  { name: 'Google Meet', logo: '/integrations/google-meet.svg' },
  { name: 'Zoom', logo: '/integrations/zoom.svg' },
  { name: 'Microsoft Teams', logo: '/integrations/teams.svg' },
  // TODO: Toevoegen zodra geïntegreerd:
  // { name: 'Shopify', logo: '/integrations/shopify.svg' },
  // { name: 'RDW', logo: '/integrations/rdw.svg' },
  // { name: 'WhatsApp', logo: '/integrations/whatsapp.svg' },
  // { name: 'Mollie', logo: '/integrations/mollie.svg' },
  // { name: 'Slack', logo: '/integrations/slack.svg' },
  // { name: 'Knipklok', logo: '/integrations/knipklok.svg' },
]

const testimonials = [
  {
    company: 'DentaCare',
    logo: '/company-logos/dentacare.png',
    logoType: 'image',
    gradient: 'from-blue-500 to-blue-600',
    stat: '+340 uur/maand',
    statColor: 'bg-green-100 text-green-700',
    challenge: 'Receptie overbelast met telefoontjes',
    quote: 'Nu handelt de AI 80% van de afspraken af. Onze receptie kan zich eindelijk focussen op patiënten in de praktijk.',
    author: 'Dr. van der Berg',
    location: 'Amsterdam',
  },
  {
    company: 'Van Dijk Makelaars',
    logo: '/company-logos/vandijk.png',
    logoType: 'image',
    gradient: 'from-amber-500 to-orange-500',
    stat: '+45% leads',
    statColor: 'bg-primary-100 text-primary-700',
    challenge: 'Gemiste leads buiten kantooruren',
    quote: 'Dankzij de AI-telefonist missen we geen enkele lead meer. Onze omzet is met 30% gestegen.',
    author: 'Jeroen K.',
    location: 'Utrecht',
  },
  {
    company: 'AutoPro Service',
    logo: '/company-logos/autopro.png',
    logoType: 'image',
    gradient: 'from-red-500 to-rose-600',
    stat: '24/7 actief',
    statColor: 'bg-purple-100 text-purple-700',
    challenge: 'Monteurs gestoord door telefoon',
    quote: 'Onze monteurs kunnen nu ongestoord werken. De AI plant APK\'s in en beantwoordt prijsvragen.',
    author: 'Patrick S.',
    location: 'Breda',
  },
  {
    company: 'Brasserie Blauw',
    logo: '/company-logos/brasserie.jpg',
    logoType: 'image',
    gradient: 'from-indigo-500 to-purple-600',
    stat: '+200 reserv.',
    statColor: 'bg-green-100 text-green-700',
    challenge: 'Telefoon stoort tijdens service',
    quote: 'Nu neemt de AI alle reserveringen aan en vraagt zelfs naar allergieën. Gasten en personeel zijn blij!',
    author: 'Lisa M.',
    location: 'Rotterdam',
  },
  {
    company: 'TechFlow Solutions',
    logo: '/company-logos/techflow.png',
    logoType: 'image',
    gradient: 'from-emerald-500 to-teal-600',
    stat: '-60% wachttijd',
    statColor: 'bg-blue-100 text-blue-700',
    challenge: 'Support tickets stapelden op',
    quote: 'De AI lost 60% van de vragen direct op. Ons supportteam kan nu focussen op complexe issues.',
    author: 'Mark R.',
    location: 'Den Haag',
  },
]

const faqs = [
  {
    question: 'Hoe snel kan ik starten?',
    answer: 'U kunt binnen enkele minuten starten. Na registratie configureert u uw AI-medewerker en koppelt u uw telefoonnummer. Dezelfde dag nog operationeel.',
  },
  {
    question: 'Spreekt de AI echt vloeiend Nederlands?',
    answer: 'Ja, onze AI is specifiek getraind voor de Nederlandse markt en spreekt vloeiend Nederlands met natuurlijke intonatie en uitdrukkingen.',
  },
  {
    question: 'Kan ik de AI trainen met mijn eigen informatie?',
    answer: 'Absoluut! U kunt uw website koppelen, FAQ\'s toevoegen, en gedragsregels instellen. De AI leert automatisch van uw bedrijfsinformatie.',
  },
  {
    question: 'Wat gebeurt er als de AI een vraag niet kan beantwoorden?',
    answer: 'De AI maakt een interne notitie met de vraag en vraagt om een terugbelnummer. U ontvangt direct een notificatie zodat u de klant kunt terugbellen.',
  },
  {
    question: 'Hoe zit het met privacy en AVG?',
    answer: 'Wij zijn volledig AVG/GDPR compliant. Alle data wordt in de EU gehost, en u heeft volledige controle over dataretentie en verwijdering.',
  },
  {
    question: 'Kan ik upgraden of downgraden?',
    answer: 'Ja, u kunt op elk moment uw abonnement aanpassen. Wijzigingen gaan direct in en worden pro-rata verrekend.',
  },
]

// Grid background component
function GridBackground() {
  return (
    <div className="absolute inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#d1d5db_1px,transparent_1px),linear-gradient(to_bottom,#d1d5db_1px,transparent_1px)] bg-[size:4rem_4rem]" />
    </div>
  )
}

// FAQ Item component
function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-6 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium text-gray-900">{question}</span>
        {isOpen ? (
          <Minus className="h-5 w-5 text-gray-400 flex-shrink-0" />
        ) : (
          <Plus className="h-5 w-5 text-gray-400 flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-6 pb-6">
          <p className="text-gray-600">{answer}</p>
        </div>
      )}
    </div>
  )
}

// Animated card component with intersection observer
function AnimatedCard({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const [isVisible, setIsVisible] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.2 }
    )

    if (cardRef.current) {
      observer.observe(cardRef.current)
    }

    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={cardRef}
      className={`transition-all duration-700 ease-out ${
        isVisible 
          ? 'opacity-100 translate-y-0' 
          : 'opacity-0 translate-y-8'
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

// Testimonial Card component
function TestimonialCard({ t }: { t: typeof testimonials[0] }) {
  return (
    <div className="flex-shrink-0 w-[300px] md:w-[400px] bg-white rounded-2xl border border-gray-200 p-5 md:p-6 hover:shadow-xl transition-all snap-center">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl ${t.logoType === 'emoji' ? `bg-gradient-to-br ${t.gradient}` : 'bg-white border border-gray-100'} flex items-center justify-center overflow-hidden`}>
            {t.logoType === 'image' ? (
              <Image src={t.logo} alt={t.company} width={48} height={48} className="w-full h-full object-contain p-1" />
            ) : (
              <span className="text-2xl">{t.logo}</span>
            )}
          </div>
          <span className="font-bold text-gray-900 text-lg">{t.company}</span>
        </div>
        <span className={`${t.statColor} text-xs font-semibold px-3 py-1.5 rounded-full flex items-center gap-1`}>
          <ArrowRight className="w-3 h-3 rotate-[-45deg]" />
          {t.stat}
        </span>
      </div>
      <div className="bg-gray-50 rounded-xl p-4 mb-4">
        <p className="text-sm text-gray-500 mb-1">Uitdaging:</p>
        <p className="text-gray-900 font-medium">"{t.challenge}"</p>
      </div>
      <div className="border-l-2 border-primary-500 pl-4">
        <p className="text-gray-700 leading-relaxed">
          "{t.quote}"
        </p>
        <p className="mt-3 text-sm text-gray-500">— {t.author}, {t.location}</p>
      </div>
    </div>
  )
}

// Testimonial Slider component with auto-scroll
function TestimonialSlider() {
  return (
    <div className="relative w-full overflow-hidden">
      {/* Fade edges */}
      <div className="absolute left-0 top-0 bottom-0 w-8 md:w-32 bg-gradient-to-r from-white to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-8 md:w-32 bg-gradient-to-l from-white to-transparent z-10 pointer-events-none" />
      
      {/* Auto-scroll on both, faster on mobile, swipeable */}
      <div 
        className="flex gap-4 md:gap-6 animate-scroll-mobile md:animate-scroll hover:[animation-play-state:paused] active:[animation-play-state:paused] touch-pan-x"
        style={{ 
          WebkitOverflowScrolling: 'touch'
        }}
      >
        {testimonials.map((t, i) => (
          <TestimonialCard key={`first-${i}`} t={t} />
        ))}
        {testimonials.map((t, i) => (
          <TestimonialCard key={`second-${i}`} t={t} />
        ))}
      </div>
    </div>
  )
}

export default function HomePage() {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50)
    }

    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <div className="min-h-screen bg-white">
      {/* Floating Glass Navigation - background appears on scroll */}
      <nav className="fixed top-4 left-4 right-4 z-50">
        <div className="max-w-6xl mx-auto">
          <div 
            className={`relative rounded-2xl px-4 md:px-6 transition-all duration-300 ${
              isScrolled || isMobileMenuOpen
                ? 'bg-white/80 backdrop-blur-xl border border-gray-200 shadow-lg shadow-black/5' 
                : 'bg-transparent'
            }`}
          >
            <div className="flex items-center justify-between h-16">
              {/* Logo */}
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 shadow-md shadow-primary-600/30">
                  <Headphones className="h-5 w-5 text-white" />
                </div>
                <span className="font-display text-xl font-bold text-gray-900">
                  klantenservice<span className="text-primary-600">.ai</span>
                </span>
              </div>

              {/* Desktop Navigation */}
              <div className="hidden md:flex items-center gap-8">
                <Link href="#features" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                  Functies
                </Link>
                <Link href="#pricing" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                  Prijzen
                </Link>
                <Link href="#faq" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                  FAQ
                </Link>
              </div>

              {/* Desktop CTA */}
              <div className="hidden md:flex items-center gap-4">
                <Link href="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                  Inloggen
                </Link>
                <Link href="/register" className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-primary-700 transition-colors shadow-md shadow-primary-600/30">
                  Gratis proberen
                </Link>
              </div>

              {/* Mobile Hamburger */}
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="md:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
                aria-label="Menu"
              >
                {isMobileMenuOpen ? (
                  <X className="h-6 w-6 text-gray-700" />
                ) : (
                  <Menu className="h-6 w-6 text-gray-700" />
                )}
              </button>
            </div>

            {/* Mobile Menu */}
            {isMobileMenuOpen && (
              <div className="md:hidden pb-4 border-t border-gray-200 mt-2 pt-4">
                <div className="flex flex-col gap-3">
                  <Link 
                    href="#features" 
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                  >
                    Functies
                  </Link>
                  <Link 
                    href="#pricing" 
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                  >
                    Prijzen
                  </Link>
                  <Link 
                    href="#faq" 
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                  >
                    FAQ
                  </Link>
                  <hr className="border-gray-200 my-2" />
                  <Link 
                    href="/login" 
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                  >
                    Inloggen
                  </Link>
                  <Link 
                    href="/register" 
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="bg-primary-600 text-white px-4 py-3 rounded-lg text-base font-semibold hover:bg-primary-700 transition-colors text-center shadow-md shadow-primary-600/30"
                  >
                    Gratis proberen
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Fixed Grid Background - stays in place while content scrolls */}
      <div 
        className="fixed top-0 left-0 right-0 pointer-events-none"
        style={{
          height: '100vh',
          zIndex: 0,
          backgroundImage: 'linear-gradient(to right, #f5f5f5 1px, transparent 1px), linear-gradient(to bottom, #f5f5f5 1px, transparent 1px)',
          backgroundSize: '4rem 4rem',
        }}
      />

      {/* Hero */}
      <section className="min-h-screen pt-24 flex items-center justify-center px-4 relative overflow-hidden z-10">
        {/* Fade to white at bottom of hero */}
        <div 
          className="absolute bottom-0 left-0 right-0 h-32 pointer-events-none"
          style={{
            background: 'linear-gradient(to bottom, transparent, white)',
            zIndex: 5,
          }}
        />
        <div className="max-w-4xl mx-auto text-center relative">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-full text-sm font-medium mb-8 shadow-md shadow-primary-600/30">
            <Phone className="h-4 w-4" />
            24/7 Beschikbaar voor uw klanten
          </div>
          
          <h1 className="text-4xl sm:text-5xl md:text-7xl font-display font-bold text-gray-900 leading-tight">
            AI-telefonisten voor{' '}
            <span className="gradient-text">uw bedrijf</span>
          </h1>
          <p className="mt-6 text-xl text-gray-600 max-w-2xl mx-auto">
            Automatiseer uw klantenservice met intelligente AI-medewerkers die 24/7 beschikbaar zijn, 
            afspraken maken en uw bedrijf perfect vertegenwoordigen.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="bg-primary-600 text-white px-8 py-4 rounded-lg text-base font-semibold hover:bg-primary-700 transition-colors inline-flex items-center shadow-lg shadow-primary-600/30">
              Start gratis proefperiode
              <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
            <Link href="#features" className="bg-white text-gray-900 px-8 py-4 rounded-lg text-base font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">
              Boek een demo
            </Link>
          </div>
          <p className="mt-4 text-sm text-gray-500">
            Probeer het gratis • Annuleren kan altijd
          </p>
        </div>
      </section>

      {/* Demo Video Section */}
      <section className="min-h-[80vh] md:min-h-screen flex items-center justify-center py-16 md:py-20 px-4 relative bg-white z-10">
        <div className="max-w-5xl mx-auto w-full">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Zie het in actie
            </h2>
            <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
              Bekijk hoe onze AI-telefonist uw klanten te woord staat en afspraken inplant.
            </p>
          </div>

          {/* Video Frame with Browser Mockup */}
          <div className="relative mx-auto max-w-4xl">
            {/* Browser window frame */}
            <div className="rounded-2xl overflow-hidden shadow-2xl shadow-primary-600/20 border border-gray-200">
              {/* Browser header */}
              <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-gray-200">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                </div>
                <div className="flex-1 mx-4">
                  <div className="bg-white rounded-lg px-4 py-1.5 text-sm text-gray-500 max-w-md mx-auto text-center">
                    klantenservice.ai/demo
                  </div>
                </div>
              </div>
              
              {/* Video placeholder */}
              <div className="relative bg-gradient-to-br from-gray-900 to-gray-800 aspect-video flex items-center justify-center">
                {/* Decorative elements */}
                <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:2rem_2rem]" />
                
                {/* Play button */}
                <button className="relative z-10 flex items-center justify-center w-20 h-20 bg-primary-600 rounded-full shadow-lg shadow-primary-600/50 hover:bg-primary-500 hover:scale-105 transition-all group">
                  <Play className="h-8 w-8 text-white ml-1" fill="currentColor" />
                </button>
                
                {/* Decorative ring animation */}
                <div className="absolute w-20 h-20 rounded-full border-2 border-primary-400 animate-ping opacity-20" />
                
                {/* Corner accent */}
                <div className="absolute bottom-4 right-4 flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-2">
                  <Headphones className="h-4 w-4 text-primary-400" />
                  <span className="text-sm text-white/80">Demo gesprek</span>
                </div>
              </div>
            </div>

            {/* Floating indicators */}
            <div className="absolute -left-4 top-1/2 -translate-y-1/2 bg-white rounded-xl shadow-lg p-4 hidden lg:block">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                  <Phone className="h-5 w-5 text-primary-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Inkomend gesprek</p>
                  <p className="text-xs text-gray-500">+31 20 123 4567</p>
                </div>
              </div>
            </div>

            <div className="absolute -right-4 bottom-1/4 bg-white rounded-xl shadow-lg p-4 hidden lg:block">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                  <Calendar className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Afspraak ingepland</p>
                  <p className="text-xs text-gray-500">Morgen om 14:00</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 md:py-24 bg-white relative z-10">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <span className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
              <Zap className="h-4 w-4" />
              Binnen 8 minuten live
            </span>
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Zo simpel werkt het
            </h2>
            <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
              In drie eenvoudige stappen is uw AI-telefonist operationeel
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 md:gap-8">
            {howItWorks.map((item, index) => (
              <AnimatedCard key={item.step} delay={index * 150}>
                <div className="relative h-full pt-2 md:pt-0">
                  {/* Connector line */}
                  {index < howItWorks.length - 1 && (
                    <div className="hidden md:block absolute top-16 left-[60%] w-[80%] h-0.5 bg-gradient-to-r from-primary-300 to-primary-100" />
                  )}
                  
                  <div className="bg-white rounded-2xl p-6 md:p-8 border border-gray-200 hover:shadow-xl hover:border-primary-200 transition-all relative h-full flex flex-col">
                    {/* Step number */}
                    <div className="absolute -top-4 left-4 md:-top-4 md:-left-4 w-8 h-8 md:w-10 md:h-10 bg-primary-600 rounded-lg md:rounded-xl flex items-center justify-center text-white font-bold text-sm md:text-base shadow-lg shadow-primary-600/30">
                      {item.step}
                    </div>
                    
                    {/* Icon */}
                    <div className="w-16 h-16 rounded-2xl bg-primary-100 flex items-center justify-center mb-6 mt-3 md:mt-0">
                      <item.icon className="w-8 h-8 text-primary-600" />
                    </div>
                    
                    {/* Content */}
                    <h3 className="text-xl font-bold text-gray-900 mb-2">{item.title}</h3>
                    <p className="text-gray-600 mb-4 flex-grow">{item.description}</p>
                    
                    {/* Time badge */}
                    <span className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 bg-primary-50 px-3 py-1 rounded-full self-start">
                      ⏱️ {item.time}
                    </span>
                  </div>
                </div>
              </AnimatedCard>
            ))}
          </div>

          {/* CTA */}
          <div className="text-center mt-12">
            <Link 
              href="/register" 
              className="inline-flex items-center gap-2 bg-primary-600 text-white px-8 py-4 rounded-xl font-semibold hover:bg-primary-700 transition-colors shadow-lg shadow-primary-600/30"
            >
              Start nu - het is gratis
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Testimonials / Case Studies - Full Width Scrolling */}
      <section className="min-h-[70vh] md:min-h-screen flex flex-col justify-center py-16 md:py-20 bg-white overflow-hidden relative z-10">
        <div className="text-center mb-16 px-4">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
            Wat onze klanten bereiken
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Echte resultaten. Echte bedrijven. Echte tijdsbesparing.
          </p>
        </div>

        {/* Interactive Scrolling Cards */}
        <TestimonialSlider />

        {/* Stats */}
        <div className="mt-12 md:mt-20 max-w-5xl mx-auto px-4 grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8">
          <div className="text-center">
            <p className="text-3xl md:text-4xl font-bold text-primary-600">500+</p>
            <p className="text-sm md:text-base text-gray-600 mt-1">Tevreden bedrijven</p>
          </div>
          <div className="text-center">
            <p className="text-3xl md:text-4xl font-bold text-primary-600">2.5M+</p>
            <p className="text-sm md:text-base text-gray-600 mt-1">Gesprekken afgehandeld</p>
          </div>
          <div className="text-center">
            <p className="text-3xl md:text-4xl font-bold text-primary-600">98%</p>
            <p className="text-sm md:text-base text-gray-600 mt-1">Klanttevredenheid</p>
          </div>
          <div className="text-center">
            <p className="text-3xl md:text-4xl font-bold text-primary-600">24/7</p>
            <p className="text-sm md:text-base text-gray-600 mt-1">Altijd bereikbaar</p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-16 md:py-20 bg-white relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Alles wat u nodig heeft
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Een complete oplossing voor uw telefonische klantenservice
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <AnimatedCard key={feature.title} delay={index * 100}>
                <div className="bg-white rounded-2xl p-8 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all h-full">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100">
                    <feature.icon className="h-6 w-6 text-primary-600" />
                  </div>
                  <h3 className="mt-6 text-lg font-semibold text-gray-900">{feature.title}</h3>
                  <p className="mt-2 text-gray-600">{feature.description}</p>
                </div>
              </AnimatedCard>
            ))}
          </div>
        </div>
      </section>

      {/* Integrations */}
      <section className="py-16 md:py-24 bg-white relative z-10">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <span className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
              <Link2 className="h-4 w-4" />
              Naadloos geïntegreerd
            </span>
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Werkt met uw favoriete tools
            </h2>
            <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
              Onze AI-telefonist integreert direct met de agenda- en communicatietools die u al gebruikt
            </p>
          </div>

          {/* Integration logos grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
            {/* Google Calendar */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/google-calendar.png" alt="Google Calendar" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Google Calendar</span>
            </div>

            {/* Microsoft Outlook */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/Outlook_2013_23477.png" alt="Outlook" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Outlook</span>
            </div>

            {/* Apple Calendar */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/applecalendar.png" alt="Apple Calendar" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Apple Calendar</span>
            </div>

            {/* Google Meet */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/google-meet.png" alt="Google Meet" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Google Meet</span>
            </div>

            {/* Zoom */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/zoom.png" alt="Zoom" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Zoom</span>
            </div>

            {/* Microsoft Teams */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 hover:border-primary-200 hover:shadow-lg transition-all flex flex-col items-center justify-center gap-3">
              <div className="w-12 h-12 flex items-center justify-center">
                <Image src="/app-icons/teams.png" alt="Teams" width={40} height={40} className="object-contain" />
              </div>
              <span className="text-sm font-medium text-gray-700">Teams</span>
            </div>

            {/* TODO: Toevoegen zodra geïntegreerd: Shopify, RDW, WhatsApp, Mollie, Slack, Knipklok */}
          </div>

          {/* Additional info */}
          <div className="mt-12 text-center">
            <p className="text-gray-500 text-sm">
              Mist u een integratie? <Link href="/contact" className="text-primary-600 font-medium hover:underline">Laat het ons weten</Link>
            </p>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-16 md:py-20 relative bg-white z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Eenvoudige, transparante prijzen
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Kies het pakket dat bij uw bedrijf past
            </p>
            <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-orange-100 px-4 py-2">
              <span className="text-orange-600 font-semibold">🎉 Probeer het gratis</span>
              <span className="text-orange-500">•</span>
              <span className="text-orange-600">Annuleren kan altijd</span>
            </div>
          </div>
          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl p-8 transition-all ${
                  plan.popular
                    ? 'bg-primary-600 text-white shadow-xl shadow-primary-600/30'
                    : 'bg-white border border-gray-200'
                }`}
              >
                {plan.popular && (
                  <span className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 text-amber-900 px-4 py-1 text-xs font-semibold">
                    Meest gekozen
                  </span>
                )}
                <div className="text-center">
                  <h3 className={`text-lg font-semibold ${plan.popular ? 'text-white' : 'text-gray-900'}`}>
                    {plan.name}
                  </h3>
                  <div className="mt-4">
                    {typeof plan.price === 'string' && plan.price.includes('aanvraag') ? (
                      <span className={`text-3xl font-bold ${plan.popular ? 'text-white' : 'text-gray-900'}`}>
                        {plan.price}
                      </span>
                    ) : (
                      <>
                        <span className={`text-5xl font-bold ${plan.popular ? 'text-white' : 'text-gray-900'}`}>
                          €{plan.price}
                        </span>
                        <span className={`text-base ${plan.popular ? 'text-primary-200' : 'text-gray-500'}`}>
                          /maand
                        </span>
                        <p className={`mt-1 text-sm font-medium ${plan.popular ? 'text-orange-300' : 'text-orange-500'}`}>
                          14 dagen gratis
                        </p>
                      </>
                    )}
                  </div>
                  <p className={`mt-2 text-sm ${plan.popular ? 'text-primary-200' : 'text-gray-500'}`}>
                    {plan.description}
                  </p>
                </div>
                <ul className="mt-8 space-y-4">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-3">
                      <Check className={`h-5 w-5 flex-shrink-0 ${plan.popular ? 'text-primary-200' : 'text-primary-600'}`} />
                      <span className={`text-sm ${plan.popular ? 'text-primary-100' : 'text-gray-600'}`}>
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={typeof plan.price === 'string' && plan.price.includes('aanvraag') ? '/contact' : '/register'}
                  className={`mt-8 block w-full rounded-xl py-4 text-center text-sm font-semibold transition-colors ${
                    plan.popular
                      ? 'bg-white text-primary-600 hover:bg-primary-50'
                      : 'bg-primary-600 text-white hover:bg-primary-700'
                  }`}
                >
                  {typeof plan.price === 'string' && plan.price.includes('aanvraag') ? 'Plan een gesprek' : 'Probeer het gratis uit'}
                </Link>
                {typeof plan.price !== 'string' || !plan.price.includes('aanvraag') ? (
                  <p className={`mt-3 text-center text-xs ${plan.popular ? 'text-primary-200' : 'text-gray-400'}`}>
                    ✓ Nu geen betaling verschuldigd
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-16 md:py-20 bg-white relative z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Veelgestelde vragen
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Alles wat u wilt weten voordat u begint
            </p>
          </div>
          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <FAQItem key={index} question={faq.question} answer={faq.answer} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA Card */}
      <section className="py-20 px-4 bg-white relative z-10">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl border border-gray-200 p-8 md:p-12 lg:p-16 text-center">
            <h2 className="text-2xl md:text-3xl lg:text-4xl font-display font-bold text-gray-900">
              Klaar om te starten?
            </h2>
            <p className="mt-4 text-lg text-gray-600 max-w-xl mx-auto">
              Sluit u aan bij 500+ bedrijven die hun klantenservice al hebben geautomatiseerd.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/register" className="bg-gray-900 text-white px-8 py-4 rounded-lg text-base font-semibold hover:bg-gray-800 transition-colors inline-flex items-center">
                Start gratis proefperiode
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <Link href="/contact" className="text-gray-900 px-8 py-4 rounded-lg text-base font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">
                Bekijk demo
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 bg-white border-t border-gray-200 relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            {/* Logo & Description */}
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
                  <Headphones className="h-4 w-4 text-white" />
                </div>
                <span className="font-display text-lg font-bold text-gray-900">
                  klantenservice<span className="text-primary-600">.ai</span>
                </span>
              </div>
              <p className="text-sm text-gray-600">
                AI-telefonisten die uw klanten 24/7 te woord staan.
              </p>
            </div>

            {/* Product */}
            <div>
              <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Product</h4>
              <ul className="space-y-3">
                <li><Link href="#features" className="text-sm text-gray-600 hover:text-gray-900">Functies</Link></li>
                <li><Link href="#pricing" className="text-sm text-gray-600 hover:text-gray-900">Prijzen</Link></li>
                <li><Link href="#faq" className="text-sm text-gray-600 hover:text-gray-900">FAQ</Link></li>
              </ul>
            </div>

            {/* Company */}
            <div>
              <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Bedrijf</h4>
              <ul className="space-y-3">
                <li><Link href="/about" className="text-sm text-gray-600 hover:text-gray-900">Over ons</Link></li>
                <li><Link href="/blog" className="text-sm text-gray-600 hover:text-gray-900">Blog</Link></li>
                <li><Link href="/contact" className="text-sm text-gray-600 hover:text-gray-900">Contact</Link></li>
              </ul>
            </div>

            {/* Legal */}
            <div>
              <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Juridisch</h4>
              <ul className="space-y-3">
                <li><Link href="/privacy" className="text-sm text-gray-600 hover:text-gray-900">Privacy Policy</Link></li>
                <li><Link href="/terms" className="text-sm text-gray-600 hover:text-gray-900">Voorwaarden</Link></li>
                <li><Link href="/gdpr" className="text-sm text-gray-600 hover:text-gray-900">AVG/GDPR</Link></li>
              </ul>
            </div>
          </div>

          {/* Bottom */}
          <div className="pt-8 border-t border-gray-200 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-gray-500">
              © 2024 klantenservice.ai. Alle rechten voorbehouden.
            </p>
            <div className="flex items-center gap-4">
              <a href="mailto:info@klantenservice.ai" className="text-gray-400 hover:text-gray-600">
                <Mail className="h-5 w-5" />
              </a>
              <a href="tel:+31201234567" className="text-gray-400 hover:text-gray-600">
                <Phone className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
