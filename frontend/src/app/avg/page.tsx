'use client'

import Link from 'next/link'
import { ArrowLeft, Shield, Server, Lock, FileCheck, Users, Clock, CheckCircle } from 'lucide-react'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'

export default function AVGPage() {
  const complianceFeatures = [
    {
      icon: Server,
      title: 'EU Hosting',
      description: 'Al onze servers staan in de Europese Unie. Uw gegevens verlaten nooit de EU.',
    },
    {
      icon: Lock,
      title: 'Versleuteling',
      description: 'Alle gegevens worden versleuteld opgeslagen (AES-256) en verstuurd (TLS 1.3).',
    },
    {
      icon: FileCheck,
      title: 'Verwerkersovereenkomst',
      description: 'Wij bieden een standaard verwerkersovereenkomst conform AVG artikel 28.',
    },
    {
      icon: Users,
      title: 'Rechten betrokkenen',
      description: 'Volledige ondersteuning voor inzage, rectificatie, verwijdering en portabiliteit.',
    },
    {
      icon: Clock,
      title: 'Configureerbare retentie',
      description: 'Stel zelf in hoe lang gespreksgegevens bewaard worden (30, 90 of onbeperkt dagen).',
    },
    {
      icon: Shield,
      title: 'Privacy by Design',
      description: 'Onze systemen zijn ontworpen met privacy als uitgangspunt, niet als nagedachte.',
    },
  ]

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

        {/* Hero */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 bg-green-100 text-green-800 px-4 py-2 rounded-full text-sm font-medium mb-6">
            <Shield className="h-4 w-4" />
            AVG/GDPR Compliant
          </div>
          <h1 className="text-4xl font-display font-bold text-gray-900 mb-4">
            AVG/GDPR Compliance
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Klantenservice.ai is volledig compliant met de Algemene Verordening Gegevensbescherming (AVG/GDPR). 
            Uw gegevens en die van uw klanten zijn bij ons in veilige handen.
          </p>
        </div>

        {/* Compliance features grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {complianceFeatures.map((feature) => (
            <div key={feature.title} className="bg-white rounded-2xl border border-gray-200 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-100 mb-4">
                <feature.icon className="h-6 w-6 text-primary-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
              <p className="text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>

        {/* Detailed content */}
        <div className="bg-white rounded-2xl shadow-soft border border-gray-200 p-8 md:p-12">
          <div className="prose prose-gray max-w-none">
            <h2 className="text-2xl font-semibold text-gray-900 mt-0 mb-6">Onze AVG-maatregelen in detail</h2>
            
            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">1. Gegevensverwerking</h3>
            <p className="text-gray-600 mb-4">
              Klantenservice.ai verwerkt persoonsgegevens uitsluitend voor de doeleinden waarvoor deze zijn verzameld. 
              Als verwerker handelen wij strikt volgens de instructies van onze klanten (verwerkingsverantwoordelijken).
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Wij verwerken alleen de gegevens die noodzakelijk zijn voor onze dienstverlening</li>
              <li>Gegevens worden niet gebruikt voor andere doeleinden dan overeengekomen</li>
              <li>Wij verkopen nooit gegevens aan derden</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">2. Technische beveiligingsmaatregelen</h3>
            <p className="text-gray-600 mb-4">
              Wij hebben uitgebreide technische maatregelen getroffen om persoonsgegevens te beschermen:
            </p>
            <div className="bg-gray-50 rounded-xl p-6 mb-4">
              <ul className="space-y-3">
                <li className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600"><strong>Versleuteling in rust:</strong> AES-256 encryptie voor alle opgeslagen gegevens</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600"><strong>Versleuteling in transit:</strong> TLS 1.3 voor alle dataverkeer</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600"><strong>Toegangscontrole:</strong> Role-based access control en multi-factor authenticatie</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600"><strong>Logging:</strong> Uitgebreide audit logging van alle gegevenstoegang</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-600"><strong>Back-ups:</strong> Versleutelde back-ups met geografische redundantie binnen de EU</span>
                </li>
              </ul>
            </div>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">3. Organisatorische maatregelen</h3>
            <p className="text-gray-600 mb-4">
              Naast technische maatregelen hebben wij ook organisatorische maatregelen getroffen:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Alle medewerkers zijn gebonden aan geheimhouding</li>
              <li>Regelmatige privacy-trainingen voor alle medewerkers</li>
              <li>Gedocumenteerde procedures voor gegevensverwerking</li>
              <li>Beperkte toegang op need-to-know basis</li>
              <li>Periodieke interne en externe audits</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">4. Rechten van betrokkenen</h3>
            <p className="text-gray-600 mb-4">
              Wij ondersteunen u volledig bij het uitoefenen van de rechten van betrokkenen:
            </p>
            <div className="grid md:grid-cols-2 gap-4 mb-4">
              <div className="bg-gray-50 rounded-xl p-4">
                <h4 className="font-medium text-gray-900 mb-2">Recht op inzage</h4>
                <p className="text-sm text-gray-600">Export alle gegevens van een specifieke beller via het dashboard</p>
              </div>
              <div className="bg-gray-50 rounded-xl p-4">
                <h4 className="font-medium text-gray-900 mb-2">Recht op verwijdering</h4>
                <p className="text-sm text-gray-600">Verwijder alle gegevens van een specifieke beller met één klik</p>
              </div>
              <div className="bg-gray-50 rounded-xl p-4">
                <h4 className="font-medium text-gray-900 mb-2">Recht op rectificatie</h4>
                <p className="text-sm text-gray-600">Pas opgeslagen gegevens aan via het dashboard</p>
              </div>
              <div className="bg-gray-50 rounded-xl p-4">
                <h4 className="font-medium text-gray-900 mb-2">Recht op dataportabiliteit</h4>
                <p className="text-sm text-gray-600">Download alle gegevens in machineleesbaar formaat (JSON/CSV)</p>
              </div>
            </div>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">5. Verwerkersovereenkomst</h3>
            <p className="text-gray-600 mb-4">
              Conform artikel 28 AVG bieden wij een verwerkersovereenkomst (Data Processing Agreement) aan alle klanten. 
              Deze overeenkomst bevat:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Beschrijving van de verwerkingsactiviteiten</li>
              <li>Categorieën persoonsgegevens en betrokkenen</li>
              <li>Beveiligingsmaatregelen</li>
              <li>Subverwerkers en locaties</li>
              <li>Procedures voor datalekken</li>
              <li>Auditmogelijkheden</li>
            </ul>
            <p className="text-gray-600 mb-4">
              De verwerkersovereenkomst is beschikbaar via uw dashboard en wordt automatisch geaccepteerd bij 
              het aangaan van een abonnement.
            </p>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">6. Subverwerkers</h3>
            <p className="text-gray-600 mb-4">
              Wij maken gebruik van de volgende subverwerkers, allen binnen de EU of met adequaatheidsbesluit:
            </p>
            <div className="overflow-x-auto mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Subverwerker</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Dienst</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Locatie</th>
                  </tr>
                </thead>
                <tbody className="text-gray-600">
                  <tr className="border-b border-gray-100">
                    <td className="py-3 px-4">Hetzner</td>
                    <td className="py-3 px-4">Cloud hosting</td>
                    <td className="py-3 px-4">Duitsland (EU)</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="py-3 px-4">OpenAI</td>
                    <td className="py-3 px-4">AI-verwerking</td>
                    <td className="py-3 px-4">EU Data Processing Agreement</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="py-3 px-4">ElevenLabs</td>
                    <td className="py-3 px-4">Spraak-AI en tekst-naar-spraak</td>
                    <td className="py-3 px-4">EU Data Processing Agreement</td>
                  </tr>
                  <tr className="border-b border-gray-100">
                    <td className="py-3 px-4">Stripe</td>
                    <td className="py-3 px-4">Betalingsverwerking</td>
                    <td className="py-3 px-4">Ierland (EU)</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-gray-600 mb-4">
              Wijzigingen in subverwerkers worden minimaal 30 dagen van tevoren aangekondigd.
            </p>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">7. Datalekprocedure</h3>
            <p className="text-gray-600 mb-4">
              In geval van een datalek handelen wij als volgt:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Onmiddellijke melding aan getroffen klanten (binnen 24 uur)</li>
              <li>Ondersteuning bij melding aan Autoriteit Persoonsgegevens (indien vereist)</li>
              <li>Uitgebreide documentatie van het incident</li>
              <li>Implementatie van aanvullende maatregelen</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-900 mt-8 mb-4">8. Contact</h3>
            <p className="text-gray-600 mb-4">
              Voor vragen over AVG-compliance of het uitoefenen van rechten:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Privacy Officer:</strong> privacy@klantenservice.ai</li>
              <li><strong>Algemeen:</strong> info@klantenservice.ai</li>
            </ul>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-12 bg-primary-600 rounded-2xl p-8 md:p-12 text-center">
          <h2 className="text-2xl font-display font-bold text-white mb-4">
            Verwerkersovereenkomst nodig?
          </h2>
          <p className="text-primary-100 mb-6 max-w-2xl mx-auto">
            Als klant kunt u de verwerkersovereenkomst downloaden via uw dashboard. 
            Heeft u vragen of specifieke eisen? Neem contact met ons op.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              href="/contact" 
              className="bg-white text-primary-600 px-6 py-3 rounded-lg font-semibold hover:bg-primary-50 transition-colors"
            >
              Contact opnemen
            </Link>
            <Link 
              href="/register" 
              className="bg-primary-700 text-white px-6 py-3 rounded-lg font-semibold hover:bg-primary-800 transition-colors"
            >
              Gratis proberen
            </Link>
          </div>
        </div>

        {/* Related links */}
        <div className="mt-8 flex flex-wrap gap-4">
          <Link href="/privacy" className="text-primary-600 hover:text-primary-700 font-medium">
            Privacyverklaring →
          </Link>
          <Link href="/voorwaarden" className="text-primary-600 hover:text-primary-700 font-medium">
            Algemene Voorwaarden →
          </Link>
        </div>
      </div>

      <Footer />
    </div>
  )
}
