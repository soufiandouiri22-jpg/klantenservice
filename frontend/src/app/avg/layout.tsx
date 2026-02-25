import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AVG & Compliance',
  description: 'Ontdek hoe klantenservice.ai voldoet aan de AVG/GDPR. Volledige controle over dataretentie en privacy.',
  alternates: { canonical: 'https://klantenservice.ai/avg' },
}

export default function AvgLayout({ children }: { children: React.ReactNode }) {
  return children
}
