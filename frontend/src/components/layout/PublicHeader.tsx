'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Menu, X } from 'lucide-react'
import Image from 'next/image'

export default function PublicHeader() {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20)
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <nav className="fixed top-4 left-4 right-4 z-50">
      <div className="max-w-6xl mx-auto">
        <div 
          className={`relative rounded-2xl px-4 md:px-6 transition-all duration-300 ${
            isScrolled || isMobileMenuOpen
              ? 'bg-white/80 backdrop-blur-xl border border-gray-200 shadow-lg shadow-black/5' 
              : 'bg-transparent'
          }`}
        >
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="klantenservice.ai" width={36} height={36} className="h-9 w-9 rounded-lg shadow-md shadow-primary-600/30" />
              <span className="font-display text-xl font-bold text-gray-900">
                klantenservice<span className="text-primary-600">.ai</span>
              </span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-8">
              <Link href="/#features" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                Functies
              </Link>
              <Link href="/#pricing" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                Prijzen
              </Link>
              <Link href="/#faq" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                FAQ
              </Link>
            </div>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-4">
              <Link href="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
                Inloggen
              </Link>
              <Link href="/register" className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-primary-700 transition-colors shadow-md shadow-primary-600/30">
                Gratis proberen
              </Link>
            </div>

            {/* Mobile Hamburger */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
              aria-label="Menu"
            >
              {isMobileMenuOpen ? (
                <X className="h-6 w-6 text-gray-700" />
              ) : (
                <Menu className="h-6 w-6 text-gray-700" />
              )}
            </button>
          </div>

          {/* Mobile Menu */}
          {isMobileMenuOpen && (
            <div className="md:hidden pb-4 border-t border-gray-200 mt-2 pt-4">
              <div className="flex flex-col gap-3">
                <Link 
                  href="/#features" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                >
                  Functies
                </Link>
                <Link 
                  href="/#pricing" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                >
                  Prijzen
                </Link>
                <Link 
                  href="/#faq" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                >
                  FAQ
                </Link>
                <hr className="border-gray-200 my-2" />
                <Link 
                  href="/login" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-base font-medium text-gray-600 hover:text-gray-900 transition-colors py-2"
                >
                  Inloggen
                </Link>
                <Link 
                  href="/register" 
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="bg-primary-600 text-white px-4 py-3 rounded-lg text-base font-semibold hover:bg-primary-700 transition-colors text-center shadow-md shadow-primary-600/30"
                >
                  Gratis proberen
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
