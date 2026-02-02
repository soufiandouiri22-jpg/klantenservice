'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import PublicHeader from '@/components/layout/PublicHeader'
import Footer from '@/components/layout/Footer'

export default function VoorwaardenPage() {
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
            Algemene Voorwaarden
          </h1>
          <p className="text-gray-500 mb-8">Laatst bijgewerkt: {new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })}</p>

          <div className="prose prose-gray max-w-none">
            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 1 - Definities</h2>
            <p className="text-gray-600 mb-4">In deze algemene voorwaarden wordt verstaan onder:</p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li><strong>Klantenservice.ai:</strong> De besloten vennootschap Klantenservice.ai, gevestigd te Amsterdam, ingeschreven bij de KvK onder nummer [invullen].</li>
              <li><strong>Klant:</strong> De natuurlijke of rechtspersoon die een overeenkomst aangaat met Klantenservice.ai.</li>
              <li><strong>Diensten:</strong> De door Klantenservice.ai aangeboden AI-telefoniediensten en gerelateerde services.</li>
              <li><strong>Overeenkomst:</strong> De overeenkomst tussen Klantenservice.ai en Klant voor het leveren van Diensten.</li>
              <li><strong>Account:</strong> De persoonlijke omgeving van Klant binnen het platform van Klantenservice.ai.</li>
              <li><strong>AI-medewerker:</strong> De door Klantenservice.ai geleverde kunstmatige intelligentie die telefoongesprekken afhandelt.</li>
            </ul>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 2 - Toepasselijkheid</h2>
            <p className="text-gray-600 mb-4">
              2.1. Deze algemene voorwaarden zijn van toepassing op alle aanbiedingen, offertes en overeenkomsten tussen 
              Klantenservice.ai en Klant.
            </p>
            <p className="text-gray-600 mb-4">
              2.2. Afwijkingen van deze voorwaarden zijn alleen geldig indien schriftelijk overeengekomen.
            </p>
            <p className="text-gray-600 mb-4">
              2.3. De toepasselijkheid van eventuele inkoop- of andere voorwaarden van Klant wordt uitdrukkelijk van de hand gewezen.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 3 - Totstandkoming overeenkomst</h2>
            <p className="text-gray-600 mb-4">
              3.1. Een overeenkomst komt tot stand op het moment dat Klant een account aanmaakt en akkoord gaat met deze 
              algemene voorwaarden.
            </p>
            <p className="text-gray-600 mb-4">
              3.2. Klantenservice.ai behoudt zich het recht voor om een registratie te weigeren zonder opgave van redenen.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 4 - Proefperiode</h2>
            <p className="text-gray-600 mb-4">
              4.1. Nieuwe klanten kunnen gebruik maken van een gratis proefperiode van 14 dagen.
            </p>
            <p className="text-gray-600 mb-4">
              4.2. Tijdens de proefperiode heeft Klant toegang tot alle functionaliteiten van het gekozen abonnement.
            </p>
            <p className="text-gray-600 mb-4">
              4.3. Na afloop van de proefperiode wordt het abonnement automatisch omgezet naar een betaald abonnement, 
              tenzij Klant voor het einde van de proefperiode opzegt.
            </p>
            <p className="text-gray-600 mb-4">
              4.4. Klant kan de proefperiode op elk moment beëindigen zonder verdere verplichtingen.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 5 - Dienstverlening</h2>
            <p className="text-gray-600 mb-4">
              5.1. Klantenservice.ai levert AI-telefoniediensten waarmee inkomende telefoongesprekken automatisch worden 
              beantwoord en afgehandeld.
            </p>
            <p className="text-gray-600 mb-4">
              5.2. Klantenservice.ai spant zich in om een beschikbaarheid van 99,9% te realiseren, maar garandeert geen 
              ononderbroken werking van de Diensten.
            </p>
            <p className="text-gray-600 mb-4">
              5.3. Klantenservice.ai behoudt zich het recht voor om de Diensten te wijzigen of uit te breiden. 
              Wezenlijke wijzigingen worden minimaal 30 dagen van tevoren aangekondigd.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 6 - Verplichtingen Klant</h2>
            <p className="text-gray-600 mb-4">6.1. Klant is verplicht om:</p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>Correcte en actuele gegevens te verstrekken bij registratie</li>
              <li>Inloggegevens vertrouwelijk te behandelen</li>
              <li>De Diensten te gebruiken in overeenstemming met de wet en deze voorwaarden</li>
              <li>Geen misbruik te maken van de Diensten</li>
              <li>Eindgebruikers te informeren dat zij met een AI-systeem spreken (indien wettelijk vereist)</li>
            </ul>
            <p className="text-gray-600 mb-4">
              6.2. Klant is verantwoordelijk voor de configuratie van de AI-medewerker en de juistheid van de verstrekte 
              bedrijfsinformatie.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 7 - Tarieven en betaling</h2>
            <p className="text-gray-600 mb-4">
              7.1. De actuele tarieven staan vermeld op de website van Klantenservice.ai.
            </p>
            <p className="text-gray-600 mb-4">
              7.2. Alle genoemde prijzen zijn exclusief BTW, tenzij anders vermeld.
            </p>
            <p className="text-gray-600 mb-4">
              7.3. Betaling geschiedt maandelijks vooraf via automatische incasso of creditcard.
            </p>
            <p className="text-gray-600 mb-4">
              7.4. Bij niet-tijdige betaling is Klant van rechtswege in verzuim en kan Klantenservice.ai de toegang 
              tot de Diensten opschorten.
            </p>
            <p className="text-gray-600 mb-4">
              7.5. Klantenservice.ai behoudt zich het recht voor om tarieven aan te passen. Tariefwijzigingen worden 
              minimaal 30 dagen van tevoren aangekondigd.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 8 - Duur en opzegging</h2>
            <p className="text-gray-600 mb-4">
              8.1. De overeenkomst wordt aangegaan voor onbepaalde tijd met maandelijkse facturatie.
            </p>
            <p className="text-gray-600 mb-4">
              8.2. Klant kan de overeenkomst op elk moment opzeggen via het dashboard. De opzegging gaat in aan het 
              einde van de lopende maandperiode.
            </p>
            <p className="text-gray-600 mb-4">
              8.3. Bij opzegging heeft Klant tot het einde van de betaalde periode toegang tot de Diensten.
            </p>
            <p className="text-gray-600 mb-4">
              8.4. Klantenservice.ai kan de overeenkomst met onmiddellijke ingang beëindigen bij schending van deze 
              voorwaarden door Klant.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 9 - Intellectueel eigendom</h2>
            <p className="text-gray-600 mb-4">
              9.1. Alle intellectuele eigendomsrechten op de Diensten, software en documentatie berusten bij Klantenservice.ai.
            </p>
            <p className="text-gray-600 mb-4">
              9.2. Klant verkrijgt een niet-exclusief, niet-overdraagbaar gebruiksrecht voor de duur van de overeenkomst.
            </p>
            <p className="text-gray-600 mb-4">
              9.3. Klant behoudt alle rechten op de door Klant verstrekte content en bedrijfsgegevens.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 10 - Privacy en gegevensverwerking</h2>
            <p className="text-gray-600 mb-4">
              10.1. Klantenservice.ai verwerkt persoonsgegevens in overeenstemming met de AVG en de privacyverklaring.
            </p>
            <p className="text-gray-600 mb-4">
              10.2. Voor zover Klantenservice.ai persoonsgegevens verwerkt namens Klant, treedt Klantenservice.ai op 
              als verwerker en geldt de verwerkersovereenkomst die onderdeel uitmaakt van deze voorwaarden.
            </p>
            <p className="text-gray-600 mb-4">
              10.3. Klant is zelf verantwoordelijk voor het informeren van eindgebruikers over de verwerking van hun 
              persoonsgegevens.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 11 - Aansprakelijkheid</h2>
            <p className="text-gray-600 mb-4">
              11.1. De totale aansprakelijkheid van Klantenservice.ai is beperkt tot het bedrag dat Klant in de 
              12 maanden voorafgaand aan het schadeveroorzakende feit aan Klantenservice.ai heeft betaald.
            </p>
            <p className="text-gray-600 mb-4">
              11.2. Klantenservice.ai is niet aansprakelijk voor indirecte schade, gevolgschade, gederfde winst of 
              gemiste besparingen.
            </p>
            <p className="text-gray-600 mb-4">
              11.3. Klantenservice.ai is niet aansprakelijk voor schade als gevolg van onjuiste of onvolledige 
              informatie verstrekt door de AI-medewerker, voor zover dit het gevolg is van onjuiste configuratie 
              of informatie door Klant.
            </p>
            <p className="text-gray-600 mb-4">
              11.4. De beperkingen in dit artikel gelden niet indien de schade het gevolg is van opzet of grove 
              schuld van Klantenservice.ai.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 12 - Overmacht</h2>
            <p className="text-gray-600 mb-4">
              12.1. Klantenservice.ai is niet aansprakelijk voor tekortkomingen als gevolg van overmacht.
            </p>
            <p className="text-gray-600 mb-4">
              12.2. Onder overmacht wordt onder meer verstaan: storingen in internet of telecommunicatie, 
              stroomstoringen, natuurrampen, pandemieën, overheidsmaatregelen en tekortkomingen van toeleveranciers.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 13 - Wijzigingen voorwaarden</h2>
            <p className="text-gray-600 mb-4">
              13.1. Klantenservice.ai behoudt zich het recht voor deze voorwaarden te wijzigen.
            </p>
            <p className="text-gray-600 mb-4">
              13.2. Wijzigingen worden minimaal 30 dagen van tevoren aangekondigd via e-mail of het dashboard.
            </p>
            <p className="text-gray-600 mb-4">
              13.3. Bij bezwaar tegen wijzigingen kan Klant de overeenkomst opzeggen voor de ingangsdatum van de wijzigingen.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 14 - Toepasselijk recht en geschillen</h2>
            <p className="text-gray-600 mb-4">
              14.1. Op deze voorwaarden en alle overeenkomsten is Nederlands recht van toepassing.
            </p>
            <p className="text-gray-600 mb-4">
              14.2. Geschillen worden voorgelegd aan de bevoegde rechter in Amsterdam.
            </p>
            <p className="text-gray-600 mb-4">
              14.3. Partijen zullen eerst proberen geschillen in onderling overleg op te lossen voordat zij een 
              beroep doen op de rechter.
            </p>

            <h2 className="text-xl font-semibold text-gray-900 mt-8 mb-4">Artikel 15 - Contact</h2>
            <p className="text-gray-600 mb-4">
              Voor vragen over deze voorwaarden kunt u contact opnemen met:
            </p>
            <ul className="list-disc pl-6 text-gray-600 mb-4">
              <li>E-mail: info@klantenservice.ai</li>
              <li>Post: Klantenservice.ai, Amsterdam, Nederland</li>
            </ul>
          </div>
        </div>

        {/* Related links */}
        <div className="mt-8 flex flex-wrap gap-4">
          <Link href="/privacy" className="text-primary-600 hover:text-primary-700 font-medium">
            Privacyverklaring →
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
