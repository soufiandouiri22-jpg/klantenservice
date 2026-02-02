'use client'

import Link from 'next/link'
import { Headphones, Mail, Phone } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="py-16 bg-white border-t border-gray-200 relative z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          {/* Logo & Description */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
                <Headphones className="h-4 w-4 text-white" />
              </div>
              <span className="font-display text-lg font-bold text-gray-900">
                klantenservice<span className="text-primary-600">.ai</span>
              </span>
            </Link>
            <p className="text-sm text-gray-600">
              AI-telefonisten die uw klanten 24/7 te woord staan.
            </p>
          </div>

          {/* Product */}
          <div>
            <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Product</h4>
            <ul className="space-y-3">
              <li><Link href="/#features" className="text-sm text-gray-600 hover:text-gray-900">Functies</Link></li>
              <li><Link href="/#pricing" className="text-sm text-gray-600 hover:text-gray-900">Prijzen</Link></li>
              <li><Link href="/#faq" className="text-sm text-gray-600 hover:text-gray-900">FAQ</Link></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Bedrijf</h4>
            <ul className="space-y-3">
              <li><Link href="/about" className="text-sm text-gray-600 hover:text-gray-900">Over ons</Link></li>
              <li><Link href="/blog" className="text-sm text-gray-600 hover:text-gray-900">Blog</Link></li>
              <li><Link href="/contact" className="text-sm text-gray-600 hover:text-gray-900">Contact</Link></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-semibold text-gray-900 text-sm uppercase tracking-wide mb-4">Juridisch</h4>
            <ul className="space-y-3">
              <li><Link href="/privacy" className="text-sm text-gray-600 hover:text-gray-900">Privacy Policy</Link></li>
              <li><Link href="/voorwaarden" className="text-sm text-gray-600 hover:text-gray-900">Voorwaarden</Link></li>
              <li><Link href="/avg" className="text-sm text-gray-600 hover:text-gray-900">AVG/GDPR</Link></li>
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="pt-8 border-t border-gray-200 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-gray-500">
            © {new Date().getFullYear()} klantenservice.ai. Alle rechten voorbehouden.
          </p>
          <div className="flex items-center gap-4">
            <a href="mailto:info@klantenservice.ai" className="text-gray-400 hover:text-gray-600">
              <Mail className="h-5 w-5" />
            </a>
            <a href="tel:+31201234567" className="text-gray-400 hover:text-gray-600">
              <Phone className="h-5 w-5" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
