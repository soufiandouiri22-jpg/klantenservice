import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Contact',
  description: 'Neem contact op met klantenservice.ai. Wij helpen u graag met vragen over onze AI-telefonisten.',
  alternates: { canonical: 'https://klantenservice.ai/contact' },
}

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children
}
