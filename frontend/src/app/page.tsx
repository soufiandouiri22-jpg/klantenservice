'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { ArrowRight, Check, Headphones, Calendar, Globe, MessageSquare, Shield, Zap, Plug, Plus, Minus, Phone, Mail, Play, UserPlus, Settings, PhoneCall, Link2, Mic, Eye, Puzzle, TrendingUp, ShieldCheck } from 'lucide-react'
import Image from 'next/image'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'
import { DemoCallWidget } from '@/components/DemoCallWidget'

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
    icon: Plug,
    title: 'CRM Integratie',
    description: 'Synchroniseer bellers, contacten en gespreksnotities automatisch met uw CRM.',
  },
  {
    icon: Shield,
    title: 'AVG Compliant',
    description: 'Volledig GDPR-compliant met EU hosting en configureerbare dataretentie.',
  },
]

const plans = [
  {
    name: 'Starter',
    monthlyPrice: '99',
    yearlyPrice: '83',
    yearlyTotal: '999',
    workers: 1,
    description: 'Perfect voor kleine ondernemers',
    features: ['1 AI-medewerker', '100 belminuten/maand', 'Agenda integratie', 'CRM integratie', 'Website kennis'],
  },
  {
    name: 'Business',
    monthlyPrice: '499',
    yearlyPrice: '417',
    yearlyTotal: '4.999',
    workers: 5,
    popular: true,
    description: 'Ideaal voor groeiende bedrijven',
    features: ['5 AI-medewerkers', '500 belminuten/maand', 'Alles van Starter', 'Prioriteit support', 'Dedicated onboarding'],
  },
  {
    name: 'Enterprise',
    monthlyPrice: '799',
    yearlyPrice: '667',
    yearlyTotal: '7.999',
    workers: 999,
    description: 'Voor grote organisaties',
    features: ['Onbeperkt AI-medewerkers', '1000 belminuten/maand', 'Alles van Business', 'Dedicated support', 'Custom integraties'],
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
    avatar: '/avatars/dr-van-der-berg.jpg',
    logo: '/company-logos/dentacare.png',
    logoType: 'image',
    gradient: 'from-blue-500 to-blue-600',
    stat: '+340 uur/maand',
    statColor: 'bg-primary-100 text-primary-700',
    challenge: 'Receptie overbelast met telefoontjes',
    quote: 'Nu handelt de AI 80% van de afspraken af. Onze receptie kan zich eindelijk focussen op patiënten in de praktijk.',
    author: 'Dr. van der Berg',
    location: 'Amsterdam',
  },
  {
    company: 'Van Dijk Makelaars',
    avatar: '/avatars/jeroen-k.jpg',
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
    avatar: '/avatars/patrick-s.jpg',
    logo: '/company-logos/autopro.png',
    logoType: 'image',
    gradient: 'from-red-500 to-rose-600',
    stat: '24/7 actief',
    statColor: 'bg-primary-100 text-primary-700',
    challenge: 'Monteurs gestoord door telefoon',
    quote: 'Onze monteurs kunnen nu ongestoord werken. De AI plant APK\'s in en beantwoordt prijsvragen.',
    author: 'Patrick S.',
    location: 'Breda',
  },
  {
    company: 'Brasserie Blauw',
    avatar: '/avatars/lisa-m.jpg',
    logo: '/company-logos/brasserie.jpg',
    logoType: 'image',
    gradient: 'from-indigo-500 to-purple-600',
    stat: '+200 reserv.',
    statColor: 'bg-primary-100 text-primary-700',
    challenge: 'Telefoon stoort tijdens service',
    quote: 'Nu neemt de AI alle reserveringen aan en vraagt zelfs naar allergieën. Gasten en personeel zijn blij!',
    author: 'Lisa M.',
    location: 'Rotterdam',
  },
  {
    company: 'TechFlow Solutions',
    avatar: '/avatars/mark-r.jpg',
    logo: '/company-logos/techflow.png',
    logoType: 'image',
    gradient: 'from-emerald-500 to-teal-600',
    stat: '-60% wachttijd',
    statColor: 'bg-primary-100 text-primary-700',
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
    question: 'Welke agenda\'s en CRM-systemen worden ondersteund?',
    answer: 'De AI plant afspraken in via Google Calendar, Microsoft Outlook of CalDAV. Voor CRM ondersteunen we HubSpot, Pipedrive en Salesforce. Bij afspraken kan automatisch een Zoom, Microsoft Teams of Google Meet link worden toegevoegd.',
  },
  {
    question: 'Kan ik gesprekken terugluisteren?',
    answer: 'Ja, alle gesprekken worden opgenomen en zijn terug te luisteren via het dashboard. U vindt ze onder Gesprekken, inclusief een samenvatting en transcriptie.',
  },
  {
    question: 'Wat gebeurt er als de AI een vraag niet kan beantwoorden?',
    answer: 'De AI maakt een interne notitie met de vraag en vraagt om een terugbelnummer. U ontvangt direct een notificatie zodat u de klant kunt terugbellen.',
  },
  {
    question: 'Wat kost het?',
    answer: 'Ons Starter-abonnement begint bij \u20ac99 per maand met 1 AI-medewerker en 100 belminuten. Het Business-abonnement kost \u20ac499 per maand met 5 AI-medewerkers en 500 belminuten. Enterprise kost \u20ac799 per maand met onbeperkt AI-medewerkers en 1000 belminuten. U kunt 14 dagen gratis proberen.',
  },
  {
    question: 'Wat gebeurt er als ik mijn belminuten overschrijd?',
    answer: 'Uw gesprekken worden nooit onderbroken. Extra minuten boven uw limiet worden automatisch gefactureerd aan het einde van uw facturatieperiode. De kosten per extra minuut zijn afhankelijk van uw plan: \u20ac0,75/min voor Starter, \u20ac0,40/min voor Business en \u20ac0,30/min voor Enterprise.',
  },
  {
    question: 'Hoe zit het met privacy en AVG?',
    answer: 'Wij zijn volledig AVG/GDPR compliant. Alle data wordt in de EU gehost, en u heeft volledige controle over dataretentie en verwijdering.',
  },
]

function FadeUp({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ duration: 0.6, delay, ease: [0.21, 0.47, 0.32, 0.98] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

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
        className="w-full flex items-center justify-between p-4 sm:p-6 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium text-gray-900">{question}</span>
        {isOpen ? (
          <Minus className="h-5 w-5 text-gray-400 flex-shrink-0" />
        ) : (
          <Plus className="h-5 w-5 text-gray-400 flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 sm:px-6 pb-4 sm:pb-6">
          <p className="text-gray-600">{answer}</p>
        </div>
      )}
    </div>
  )
}

// Demo section with scroll-based scale animation
function DemoSection() {
  const sectionRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start end', 'center center'],
  })
  const scale = useTransform(scrollYProgress, [0, 1], [0.85, 1])
  const opacity = useTransform(scrollYProgress, [0, 0.5], [0.4, 1])

  return (
    <section ref={sectionRef} className="py-20 md:py-32 px-4 sm:px-6 relative bg-white z-10">
      <div className="max-w-5xl mx-auto w-full">
        <FadeUp className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
            Probeer het zelf
          </h2>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
            Spreek live met onze AI-telefonist. Stel vragen, plan een demo in — ervaar het direct. Klik op ▶ en test het gratis.
          </p>
        </FadeUp>

        <motion.div
          style={{ scale, opacity }}
          className="relative mx-auto max-w-4xl"
        >
          <div className="rounded-2xl overflow-hidden shadow-2xl shadow-primary-600/20 border border-gray-200">
            <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-gray-200">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 mx-4">
                <div className="bg-white rounded-lg px-4 py-1.5 text-sm text-gray-500 max-w-md mx-auto text-center">
                  klantenservice.ai/demo
                </div>
              </div>
            </div>

            <div className="relative bg-gradient-to-br from-gray-900 to-gray-800 aspect-video flex items-center justify-center">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:2rem_2rem]" />
              <DemoCallWidget />
              <div className="absolute bottom-4 right-4 flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-lg px-3 py-2">
                <Headphones className="h-4 w-4 text-primary-400" />
                <span className="text-sm text-white/80">Live demo</span>
              </div>
            </div>
          </div>

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
        </motion.div>
      </div>
    </section>
  )
}

const showcaseItems = [
  {
    icon: Mic,
    label: 'Instellen',
    title: 'Eén keer instellen, altijd klaar',
    description: 'Configureer uw AI-medewerker één keer en hij handelt alles af: telefoongesprekken, afspraken inplannen, CRM bijwerken en notities maken. Alles draait automatisch.',
    highlights: ['Telefoongesprekken', 'Afspraken inplannen', 'CRM bijwerken', 'Notities maken'],
  },
  {
    icon: Eye,
    label: 'Inzicht',
    title: 'Elk gesprek inzichtelijk',
    description: 'Luister gesprekken terug, lees automatische samenvattingen en bekijk volledige transcripties. Weet altijd precies wat er is besproken en waar actie nodig is.',
    highlights: ['Opnames terugluisteren', 'Samenvattingen', 'Transcripties', 'Actiepunten'],
  },
  {
    icon: Puzzle,
    label: 'Integraties',
    title: 'Koppel uw bestaande tools',
    description: 'Verbind met Google Calendar, Outlook, HubSpot, Salesforce, Zoom, Microsoft Teams en meer in een paar klikken. Geen technische kennis nodig, alles werkt direct samen.',
    highlights: ['Google Calendar', 'HubSpot & Salesforce', 'Zoom & Teams', 'Microsoft Outlook'],
  },
  {
    icon: TrendingUp,
    label: 'Schalen',
    title: 'Schaal zonder grenzen',
    description: 'Of het nu een rustige maandag is of een piekmoment, uw AI-medewerkers handelen elk gesprek af. Geen wachttijden, geen gemiste oproepen, geen extra personeel nodig.',
    highlights: ['Geen wachttijden', 'Geen gemiste oproepen', 'Piekbelasting opvangen', '24/7 beschikbaar'],
  },
  {
    icon: ShieldCheck,
    label: 'Controle',
    title: 'U blijft in controle',
    description: 'Bepaal precies wat de AI wel en niet mag zeggen, stel gedragsregels in en configureer dataretentie. Uw data blijft veilig met AVG-compliance en hosting in de EU.',
    highlights: ['Gedragsregels instellen', 'Dataretentie configureren', 'AVG-compliant', 'EU hosting'],
  },
]

function ShowcaseSection() {
  const [activeIndex, setActiveIndex] = useState(0)
  const [progress, setProgress] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const DURATION = 10000

  const startTimer = () => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    setProgress(0)
    const tick = 30
    let elapsed = 0
    intervalRef.current = setInterval(() => {
      elapsed += tick
      setProgress(elapsed / DURATION)
      if (elapsed >= DURATION) {
        setActiveIndex((prev) => (prev + 1) % showcaseItems.length)
      }
    }, tick)
  }

  useEffect(() => {
    startTimer()
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [activeIndex])

  const selectTab = (index: number) => {
    if (index === activeIndex) return
    setActiveIndex(index)
  }

  const item = showcaseItems[activeIndex]

  return (
    <section className="py-20 md:py-32 px-4 sm:px-6 bg-white relative z-10">
      <div className="max-w-5xl mx-auto w-full">
        <FadeUp className="text-center mb-12">
          <span className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Zap className="h-4 w-4" />
            Waarom klantenservice.ai?
          </span>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
            Gebouwd voor miljoenen, afgestemd op één
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Alles wat u nodig heeft, op één plek
          </p>
        </FadeUp>

        {/* Tabs */}
        <div className="flex justify-center mb-10">
          <div className="inline-flex gap-1 bg-gray-100 rounded-xl p-1">
            {showcaseItems.map((tab, index) => {
              const Icon = tab.icon
              const isActive = activeIndex === index
              return (
                <button
                  key={index}
                  onClick={() => selectTab(index)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                    isActive
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                  {isActive && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-primary-500"
                        style={{ width: `${progress * 100}%` }}
                      />
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Content card */}
        <div className="relative rounded-3xl bg-gradient-to-br from-primary-600 to-primary-700 p-8 md:p-12 overflow-hidden min-h-[420px] sm:min-h-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.1),transparent_60%)]" />
          <div className="absolute bottom-0 right-0 w-64 h-64 bg-white/5 rounded-full translate-x-20 translate-y-20" />

          <AnimatePresence mode="wait">
            <motion.div
              key={activeIndex}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.21, 0.47, 0.32, 0.98] }}
              className="relative grid md:grid-cols-2 gap-8 items-center"
            >
              <div>
                <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">
                  {item.title}
                </h3>
                <p className="text-white/80 text-base md:text-lg leading-relaxed">
                  {item.description}
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {item.highlights.map((highlight, i) => (
                  <motion.div
                    key={highlight}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.06, duration: 0.25 }}
                    className="bg-white/15 backdrop-blur-sm rounded-xl px-3 py-2.5 text-white text-sm font-medium flex items-center gap-2"
                  >
                    <Check className="h-4 w-4 text-white/70 flex-shrink-0" />
                    {highlight}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}

// Video section with scroll-based scale animation
function VideoSection() {
  const sectionRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start end', 'center center'],
  })
  const scale = useTransform(scrollYProgress, [0, 1], [0.85, 1])
  const opacity = useTransform(scrollYProgress, [0, 0.5], [0.4, 1])

  return (
    <section ref={sectionRef} className="py-20 md:py-32 px-4 sm:px-6 bg-white relative z-10">
      <div className="max-w-5xl mx-auto w-full">
        <div className="text-center mb-12">
          <span className="inline-flex items-center gap-2 bg-primary-100 text-primary-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Play className="h-4 w-4" />
            Bekijk de demo
          </span>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
            Waarom klantenservice.ai?
          </h2>
          <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
            Ontdek hoe bedrijven hun klantenservice automatiseren met een AI-telefonist.
          </p>
        </div>

        <motion.div
          style={{ scale, opacity }}
          className="relative mx-auto max-w-4xl"
        >
          <div className="rounded-2xl overflow-hidden shadow-2xl shadow-primary-600/20 border border-gray-200">
            <div className="bg-gray-100 px-4 py-3 flex items-center gap-2 border-b border-gray-200">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 mx-4">
                <div className="bg-white rounded-lg px-4 py-1.5 text-sm text-gray-500 max-w-md mx-auto text-center">
                  klantenservice.ai
                </div>
              </div>
            </div>

            <div className="relative aspect-video">
              <video
                src="/demo-video.mp4"
                autoPlay
                muted
                loop
                playsInline
                className="absolute inset-0 w-full h-full object-cover"
              />
            </div>
          </div>
        </motion.div>
      </div>
    </section>
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
      <div className="flex flex-col gap-3 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-full overflow-hidden flex-shrink-0 border-2 border-gray-100">
              <Image src={t.avatar} alt={t.author} width={48} height={48} className="w-full h-full object-cover" />
            </div>
            <span className="font-bold text-gray-900 text-base md:text-lg">{t.company}</span>
          </div>
          <span className={`${t.statColor} text-xs font-semibold px-2 md:px-3 py-1 md:py-1.5 rounded-full flex items-center gap-1 whitespace-nowrap`}>
            <ArrowRight className="w-3 h-3 rotate-[-45deg]" />
            {t.stat}
          </span>
        </div>
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

// Testimonial Slider component - swipeable on mobile, auto-scroll on desktop
function TestimonialSlider() {
  return (
    <div className="relative w-full">
      {/* Fade edges - only on desktop */}
      <div className="hidden md:block absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-white to-transparent z-10 pointer-events-none" />
      <div className="hidden md:block absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-white to-transparent z-10 pointer-events-none" />
      
      {/* Mobile: swipeable scroll, Desktop: auto-scroll animation */}
      <div 
        className="flex gap-4 md:gap-6 px-4 md:px-0 overflow-x-auto md:overflow-hidden snap-x snap-mandatory md:snap-none scrollbar-hide md:w-max md:animate-scroll md:hover:[animation-play-state:paused]"
        style={{ 
          WebkitOverflowScrolling: 'touch',
          scrollbarWidth: 'none',
          msOverflowStyle: 'none'
        }}
      >
        {testimonials.map((t, i) => (
          <TestimonialCard key={`first-${i}`} t={t} />
        ))}
        {/* Duplicate only for desktop infinite scroll */}
        <div className="hidden md:contents">
          {testimonials.map((t, i) => (
            <TestimonialCard key={`second-${i}`} t={t} />
          ))}
        </div>
      </div>
      
      {/* Mobile scroll hint */}
      <p className="md:hidden text-center text-xs text-gray-400 mt-4">
        ← Swipe voor meer →
      </p>
    </div>
  )
}

export default function HomePage() {
  const router = useRouter()
  const [checking, setChecking] = useState(true)
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly')

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    const remembered = localStorage.getItem('remember_me')
    if (token && remembered === 'true') {
      router.replace('/dashboard')
      return
    }
    setChecking(false)
  }, [router])

  if (checking) return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600" />
    </div>
  )

  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  }

  return (
    <div className="min-h-screen bg-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <PublicHeader />

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
      <section className="min-h-screen pt-20 sm:pt-24 md:pt-28 flex items-center justify-center px-4 sm:px-6 relative overflow-hidden z-10">
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
            <Link href="/boekeendemo" className="bg-white text-gray-900 px-8 py-4 rounded-lg text-base font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">
              Boek een demo
            </Link>
          </div>
          <p className="mt-4 text-sm text-gray-500">
            Probeer het gratis • Annuleren kan altijd
          </p>
        </div>
      </section>

      {/* Demo Video Section */}
      <DemoSection />

      {/* How It Works */}
      <section className="py-20 md:py-32 bg-white relative z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <FadeUp className="text-center mb-16">
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
          </FadeUp>

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

      {/* Feature Showcase Accordion */}
      <ShowcaseSection />

      {/* Testimonials / Case Studies - Full Width Scrolling */}
      <section className="py-20 md:py-32 bg-white overflow-hidden relative z-10">
        <FadeUp className="text-center mb-16 px-4 sm:px-6">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
            Wat onze klanten bereiken
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Echte resultaten. Echte bedrijven. Echte tijdsbesparing.
          </p>
        </FadeUp>

        {/* Interactive Scrolling Cards */}
        <TestimonialSlider />

        {/* Stats */}
        <div className="mt-12 md:mt-20 max-w-5xl mx-auto px-4 sm:px-6 grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 md:gap-8">
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
      <section id="features" className="py-20 md:py-32 bg-white relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <FadeUp className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Alles wat u nodig heeft
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Een complete oplossing voor uw telefonische klantenservice
            </p>
          </FadeUp>
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
      <section className="py-20 md:py-32 bg-white relative z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <FadeUp className="text-center mb-16">
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
          </FadeUp>

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
      <section id="pricing" className="py-20 md:py-32 relative bg-white z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <FadeUp className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Eenvoudige, transparante prijzen
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Kies het pakket dat bij uw bedrijf past
            </p>

            {/* Billing toggle */}
            <div className="mt-6 inline-flex items-center gap-3 rounded-full bg-gray-100 p-1">
              <button
                onClick={() => setBillingInterval('monthly')}
                className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${
                  billingInterval === 'monthly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Maandelijks
              </button>
              <button
                onClick={() => setBillingInterval('yearly')}
                className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${
                  billingInterval === 'yearly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Jaarlijks
                <span className="ml-1.5 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
                  -15%
                </span>
              </button>
            </div>
          </FadeUp>
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
                    {plan.monthlyPrice.includes('aanvraag') ? (
                      <span className={`text-3xl font-bold ${plan.popular ? 'text-white' : 'text-gray-900'}`}>
                        {plan.monthlyPrice}
                      </span>
                    ) : (
                      <>
                        <span className={`text-5xl font-bold ${plan.popular ? 'text-white' : 'text-gray-900'}`}>
                          €{billingInterval === 'yearly' ? plan.yearlyTotal : plan.monthlyPrice}
                        </span>
                        <span className={`text-base ${plan.popular ? 'text-primary-200' : 'text-gray-500'}`}>
                          {billingInterval === 'yearly' ? '/jaar' : '/maand'}
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
                  href={plan.monthlyPrice.includes('aanvraag') ? '/contact' : `/checkout?plan=${plan.name.toLowerCase()}&interval=${billingInterval}`}
                  className={`mt-8 block w-full rounded-xl py-4 text-center text-sm font-semibold transition-colors ${
                    plan.popular
                      ? 'bg-white text-primary-600 hover:bg-primary-50'
                      : 'bg-primary-600 text-white hover:bg-primary-700'
                  }`}
                >
                  {plan.monthlyPrice.includes('aanvraag') ? 'Plan een gesprek' : 'Probeer het gratis uit'}
                </Link>
                {!plan.monthlyPrice.includes('aanvraag') ? (
                  <p className={`mt-3 text-center text-xs ${plan.popular ? 'text-primary-200' : 'text-gray-400'}`}>
                    ✓ 14 dagen gratis proberen
                  </p>
                ) : null}
              </div>
            ))}
          </div>
          <p className="mt-8 text-center text-sm text-gray-500">
            Belminuten overschreden? Uw gesprekken worden nooit onderbroken. Extra minuten worden automatisch gefactureerd: Starter €0,75/min · Business €0,40/min · Enterprise €0,30/min.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="py-20 md:py-32 bg-white relative z-10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <FadeUp className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-gray-900">
              Veelgestelde vragen
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Alles wat u wilt weten voordat u begint
            </p>
          </FadeUp>
          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <FAQItem key={index} question={faq.question} answer={faq.answer} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA Card */}
      <section className="py-20 md:py-32 px-4 sm:px-6 bg-white relative z-10">
        <div className="max-w-4xl mx-auto">
          <FadeUp>
          <div className="bg-white rounded-2xl border border-gray-200 p-4 sm:p-6 md:p-8 lg:p-12 xl:p-16 text-center">
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
              <Link href="/boekeendemo" className="text-gray-900 px-8 py-4 rounded-lg text-base font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">
                Bekijk demo
              </Link>
            </div>
          </div>
          </FadeUp>
        </div>
      </section>

      <Footer />
    </div>
  )
}
