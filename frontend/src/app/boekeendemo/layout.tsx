import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Boek een demo',
  description: 'Plan een persoonlijke demo in en ontdek hoe klantenservice.ai uw telefoonverkeer kan automatiseren.',
  alternates: { canonical: 'https://klantenservice.ai/boekeendemo' },
}

export default function BoekEenDemoLayout({ children }: { children: React.ReactNode }) {
  return children
}
