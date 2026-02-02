'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      <PublicHeader />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-12">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-8"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Terug naar home
        </Link>

        <div className="bg-white rounded-2xl shadow-soft border border-gray-200 p-8 md:p-12">
          <h1 className="text-3xl font-display font-bold text-gray-900 mb-2">
            Privacyverklaring
          </h1>
          <p className="text-gray-500 mb-8">Laatst bijgewerkt: {new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })}</p>

          <div className="prose prose-gray max-w-none">
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">1. Inleiding</h2>
            <p className="text-gray-600 mb-4">
              Klantenservice.ai (hierna: "wij", "ons" of "onze") respecteert uw privacy en zorgt ervoor dat uw persoonlijke 
              gegevens vertrouwelijk worden behandeld. In deze privacyverklaring leggen wij uit welke persoonsgegevens wij 
              verzamelen, waarom wij dit doen en hoe wij deze gegevens gebruiken.
            </p>
            <p className="text-gray-600 mb-4">
              Deze privacyverklaring is van toepassing op alle diensten van klantenservice.ai, waaronder onze AI-telefoniediensten, 
              website en gerelateerde services.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">2. Verwerkingsverantwoordelijke</h2>
            <p className="text-gray-600 mb-4">
              Klantenservice.ai is de verwerkingsverantwoordelijke voor de verwerking van persoonsgegevens zoals beschreven 
              in deze privacyverklaring. Onze contactgegevens zijn:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Bedrijfsnaam: Klantenservice.ai</li>
              <li>Adres: Amsterdam, Nederland</li>
              <li>E-mail: privacy@klantenservice.ai</li>
              <li>KvK-nummer: [Invullen]</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">3. Welke persoonsgegevens verzamelen wij?</h2>
            <p className="text-gray-600 mb-4">Wij verzamelen de volgende categorieën persoonsgegevens:</p>
            
            <h3 className="text-lg font-medium text-gray-900 mt-6 mb-3">3.1 Accountgegevens</h3>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Naam en achternaam</li>
              <li>E-mailadres</li>
              <li>Telefoonnummer</li>
              <li>Bedrijfsnaam en -gegevens</li>
              <li>Factuuradres</li>
            </ul>

            <h3 className="text-lg font-medium text-gray-900 mt-6 mb-3">3.2 Gebruiksgegevens</h3>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>IP-adres</li>
              <li>Browser- en apparaatinformatie</li>
              <li>Inloggegevens en sessie-informatie</li>
              <li>Gebruiksstatistieken van onze diensten</li>
            </ul>

            <h3 className="text-lg font-medium text-gray-900 mt-6 mb-3">3.3 Gespreksgegevens</h3>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Telefoonnummers van bellers</li>
              <li>Datum, tijd en duur van gesprekken</li>
              <li>Transcripties van gesprekken (indien ingeschakeld)</li>
              <li>Gemaakte afspraken en notities</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">4. Doeleinden van de verwerking</h2>
            <p className="text-gray-600 mb-4">Wij verwerken uw persoonsgegevens voor de volgende doeleinden:</p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Dienstverlening:</strong> Het leveren en onderhouden van onze AI-telefoniediensten</li>
              <li><strong>Accountbeheer:</strong> Het aanmaken en beheren van uw account</li>
              <li><strong>Facturatie:</strong> Het verwerken van betalingen en versturen van facturen</li>
              <li><strong>Communicatie:</strong> Het beantwoorden van vragen en versturen van servicemeldingen</li>
              <li><strong>Verbetering:</strong> Het verbeteren van onze diensten en gebruikerservaring</li>
              <li><strong>Wettelijke verplichtingen:</strong> Het voldoen aan wettelijke verplichtingen</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">5. Rechtsgrond voor verwerking</h2>
            <p className="text-gray-600 mb-4">Wij verwerken uw persoonsgegevens op basis van de volgende rechtsgronden:</p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Uitvoering van de overeenkomst:</strong> Verwerking is noodzakelijk voor het uitvoeren van onze diensten</li>
              <li><strong>Wettelijke verplichting:</strong> Verwerking is noodzakelijk om te voldoen aan wettelijke verplichtingen</li>
              <li><strong>Gerechtvaardigd belang:</strong> Verwerking is noodzakelijk voor onze gerechtvaardigde belangen, zoals het verbeteren van onze diensten</li>
              <li><strong>Toestemming:</strong> Voor bepaalde verwerkingen vragen wij uw uitdrukkelijke toestemming</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">6. Bewaartermijnen</h2>
            <p className="text-gray-600 mb-4">
              Wij bewaren uw persoonsgegevens niet langer dan noodzakelijk voor de doeleinden waarvoor zij zijn verzameld:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Accountgegevens:</strong> Gedurende de looptijd van uw account en maximaal 2 jaar daarna</li>
              <li><strong>Gespreksgegevens:</strong> Configureerbaar per account (30, 90 of onbeperkt dagen)</li>
              <li><strong>Factuurgegevens:</strong> 7 jaar (wettelijke bewaarplicht)</li>
              <li><strong>Communicatie:</strong> Maximaal 2 jaar na laatste contact</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">7. Delen van gegevens</h2>
            <p className="text-gray-600 mb-4">
              Wij delen uw persoonsgegevens alleen met derden wanneer dit noodzakelijk is voor onze dienstverlening:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Hosting providers:</strong> Voor het hosten van onze servers (EU-gebaseerd)</li>
              <li><strong>Betalingsproviders:</strong> Voor het verwerken van betalingen</li>
              <li><strong>AI-dienstverleners:</strong> Voor het verwerken van spraak (met verwerkersovereenkomst)</li>
            </ul>
            <p className="text-gray-600 mb-4">
              Wij verkopen uw gegevens nooit aan derden en delen deze niet voor marketingdoeleinden van derden.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">8. Beveiliging</h2>
            <p className="text-gray-600 mb-4">
              Wij nemen passende technische en organisatorische maatregelen om uw persoonsgegevens te beschermen:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Versleuteling van gegevens in transit (TLS/SSL) en in rust</li>
              <li>Toegangscontrole en authenticatie</li>
              <li>Regelmatige security audits</li>
              <li>Hosting binnen de Europese Unie</li>
              <li>Verwerkersovereenkomsten met alle subverwerkers</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">9. Uw rechten</h2>
            <p className="text-gray-600 mb-4">Op grond van de AVG heeft u de volgende rechten:</p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Recht op inzage:</strong> U kunt opvragen welke gegevens wij van u verwerken</li>
              <li><strong>Recht op rectificatie:</strong> U kunt onjuiste gegevens laten corrigeren</li>
              <li><strong>Recht op verwijdering:</strong> U kunt verzoeken uw gegevens te verwijderen</li>
              <li><strong>Recht op beperking:</strong> U kunt de verwerking van uw gegevens laten beperken</li>
              <li><strong>Recht op dataportabiliteit:</strong> U kunt uw gegevens in een gangbaar formaat ontvangen</li>
              <li><strong>Recht op bezwaar:</strong> U kunt bezwaar maken tegen bepaalde verwerkingen</li>
              <li><strong>Recht om toestemming in te trekken:</strong> Indien verwerking op toestemming is gebaseerd</li>
            </ul>
            <p className="text-gray-600 mb-4">
              U kunt uw rechten uitoefenen door contact met ons op te nemen via privacy@klantenservice.ai.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">10. Cookies</h2>
            <p className="text-gray-600 mb-4">
              Wij gebruiken alleen noodzakelijke cookies voor het functioneren van onze website en diensten. 
              Deze cookies zijn essentieel voor het inloggen en het onthouden van uw voorkeuren. 
              Wij gebruiken geen tracking cookies of cookies voor marketingdoeleinden.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">11. Wijzigingen</h2>
            <p className="text-gray-600 mb-4">
              Wij kunnen deze privacyverklaring van tijd tot tijd wijzigen. Wijzigingen worden op deze pagina gepubliceerd. 
              Bij significante wijzigingen zullen wij u hierover informeren via e-mail of een melding in uw dashboard.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">12. Klachten</h2>
            <p className="text-gray-600 mb-4">
              Heeft u een klacht over de verwerking van uw persoonsgegevens? Neem dan eerst contact met ons op. 
              U heeft ook het recht om een klacht in te dienen bij de Autoriteit Persoonsgegevens: 
              <a href="https://autoriteitpersoonsgegevens.nl" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline ml-1">
                autoriteitpersoonsgegevens.nl
              </a>
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">13. Contact</h2>
            <p className="text-gray-600 mb-4">
              Voor vragen over deze privacyverklaring of de verwerking van uw persoonsgegevens kunt u contact met ons opnemen:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>E-mail: privacy@klantenservice.ai</li>
              <li>Post: Klantenservice.ai, Amsterdam, Nederland</li>
            </ul>
          </div>
        </div>

        {/* Related links */}
        <div className="mt-8 flex flex-wrap gap-4">
          <Link href="/voorwaarden" className="text-primary-600 hover:text-primary-700 font-medium">
            Algemene Voorwaarden →
          </Link>
          <Link href="/avg" className="text-primary-600 hover:text-primary-700 font-medium">
            AVG/GDPR Compliance →
          </Link>
        </div>
      </div>

      <Footer />
    </div>
  )
}
