'use client'

import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'gray'
  children: React.ReactNode
}

function Badge({ variant = 'gray', className, children, ...props }: BadgeProps) {
  const variants = {
    primary: 'badge-primary',
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
    gray: 'badge-gray',
  }

  return (
    <span className={cn(variants[variant], className)} {...props}>
      {children}
    </span>
  )
}

export { Badge }
