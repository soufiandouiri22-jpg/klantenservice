import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacybeleid',
  description: 'Lees het privacybeleid van klantenservice.ai. Wij zijn volledig AVG/GDPR compliant met hosting in de EU.',
  alternates: { canonical: 'https://klantenservice.ai/privacy' },
}

export default function PrivacyLayout({ children }: { children: React.ReactNode }) {
  return children
}
