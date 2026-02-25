import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Inloggen',
  description: 'Log in op uw klantenservice.ai dashboard om uw AI-telefonisten te beheren.',
  alternates: { canonical: 'https://klantenservice.ai/login' },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
