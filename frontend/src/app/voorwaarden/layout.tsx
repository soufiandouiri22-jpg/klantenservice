import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Algemene voorwaarden',
  description: 'Lees de algemene voorwaarden van klantenservice.ai.',
  alternates: { canonical: 'https://klantenservice.ai/voorwaarden' },
}

export default function VoorwaardenLayout({ children }: { children: React.ReactNode }) {
  return children
}
