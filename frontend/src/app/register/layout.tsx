import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Account aanmaken',
  description: 'Maak een gratis account aan en begin vandaag nog met uw eigen AI-telefonist. 14 dagen gratis proberen.',
  alternates: { canonical: 'https://klantenservice.ai/register' },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children
}
