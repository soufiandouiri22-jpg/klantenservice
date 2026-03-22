'use client'

import { cn } from '@/lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  return (
    <div
      className={cn(
        'animate-spin rounded-full border-2 border-gray-200 border-t-gray-900',
        sizes[size],
        className
      )}
    />
  )
}

function PageLoader() {
  return (
    <div className="flex h-full min-h-[400px] items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
}

export { Spinner, PageLoader }
