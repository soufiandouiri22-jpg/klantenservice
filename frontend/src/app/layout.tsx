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
  title: 'klantenservice.ai - AI-telefonisten voor uw bedrijf',
  description: 'Automatiseer uw klantenservice met intelligente AI-telefonisten die 24/7 beschikbaar zijn.',
  keywords: ['AI', 'klantenservice', 'telefonie', 'automatisering', 'Nederlands'],
  icons: {
    icon: '/klantenservice-logo/logo-klantenservice.png',
    shortcut: '/klantenservice-logo/logo-klantenservice.png',
    apple: '/klantenservice-logo/logo-klantenservice.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="nl" className={`${inter.variable} ${jakarta.variable}`}>
      <body className="min-h-screen bg-gray-50 font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
