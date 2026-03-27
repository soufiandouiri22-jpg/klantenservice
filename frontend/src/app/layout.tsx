import type { Metadata } from 'next'
import { Inter, Plus_Jakarta_Sans } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-cabinet',
  weight: ['500', '700'],
})

export const metadata: Metadata = {
  metadataBase: new URL('https://klantenservice.ai'),
  title: {
    default: 'klantenservice.ai - AI-telefonisten voor uw bedrijf',
    template: '%s | klantenservice.ai',
  },
  description: 'Automatiseer uw klantenservice met intelligente AI-telefonisten die 24/7 beschikbaar zijn, afspraken inplannen en uw bedrijf perfect vertegenwoordigen.',
  keywords: ['AI', 'klantenservice', 'telefonie', 'automatisering', 'Nederlands', 'AI-telefonist', 'chatbot', 'telefonist', 'afspraken', 'CRM'],
  authors: [{ name: 'klantenservice.ai' }],
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml', sizes: 'any' },
      { url: '/favicon-48.png', sizes: '48x48', type: 'image/png' },
      { url: '/favicon-32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon-16.png', sizes: '16x16', type: 'image/png' },
    ],
    shortcut: '/favicon.svg',
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    type: 'website',
    locale: 'nl_NL',
    url: 'https://klantenservice.ai',
    siteName: 'klantenservice.ai',
    title: 'klantenservice.ai - AI-telefonisten voor uw bedrijf',
    description: 'Automatiseer uw klantenservice met intelligente AI-telefonisten die 24/7 beschikbaar zijn, afspraken inplannen en uw bedrijf perfect vertegenwoordigen.',
    images: [
      {
        url: '/klantenservice-logo/logo-klantenservice.png',
        width: 512,
        height: 512,
        alt: 'klantenservice.ai logo',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'klantenservice.ai - AI-telefonisten voor uw bedrijf',
    description: 'Automatiseer uw klantenservice met intelligente AI-telefonisten die 24/7 beschikbaar zijn.',
    images: ['/klantenservice-logo/logo-klantenservice.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
  alternates: {
    canonical: 'https://klantenservice.ai',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="nl" className={`${inter.variable} ${jakarta.variable}`}>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" content="#2563eb" />
        <script async src="https://plausible.io/js/pa-_iiB8Kn_rq2_TU71Le-tk.js" />
        <script
          dangerouslySetInnerHTML={{
            __html: `window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},plausible.init=plausible.init||function(i){plausible.o=i||{}};plausible.init()`,
          }}
        />
      </head>
      <body className="min-h-screen bg-gray-50 font-sans">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'Organization',
              name: 'klantenservice.ai',
              url: 'https://klantenservice.ai',
              logo: 'https://klantenservice.ai/klantenservice-logo/logo-klantenservice.png',
              description: 'AI-telefonisten voor uw bedrijf. Automatiseer uw klantenservice met intelligente AI-medewerkers die 24/7 beschikbaar zijn.',
              address: {
                '@type': 'PostalAddress',
                addressCountry: 'NL',
              },
              sameAs: [],
            }),
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
