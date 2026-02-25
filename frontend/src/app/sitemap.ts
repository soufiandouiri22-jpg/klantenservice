import type { MetadataRoute } from 'next'
import fs from 'fs'
import path from 'path'

const BASE_URL = 'https://klantenservice.ai'

const EXCLUDED_PREFIXES = [
  '/dashboard', '/admin', '/verify', '/checkout', '/invite', '/login/callback',
]

const PRIORITY_MAP: Record<string, number> = {
  '/': 1.0,
  '/boekeendemo': 0.8,
  '/register': 0.7,
  '/contact': 0.6,
  '/login': 0.5,
}

const CHANGE_FREQ_MAP: Record<string, MetadataRoute.Sitemap[number]['changeFrequency']> = {
  '/': 'weekly',
  '/privacy': 'yearly',
  '/voorwaarden': 'yearly',
  '/avg': 'yearly',
  '/terms': 'yearly',
}

function discoverRoutes(dir: string, basePath = ''): string[] {
  const routes: string[] = []

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    if (entry.name.startsWith('[') || entry.name.startsWith('_')) continue

    const fullPath = path.join(dir, entry.name)
    const routePath = `${basePath}/${entry.name}`

    const hasPage = ['page.tsx', 'page.ts', 'page.jsx', 'page.js']
      .some(f => fs.existsSync(path.join(fullPath, f)))

    if (hasPage) routes.push(routePath)
    routes.push(...discoverRoutes(fullPath, routePath))
  }

  return routes
}

export default function sitemap(): MetadataRoute.Sitemap {
  const appDir = path.join(process.cwd(), 'src', 'app')
  const now = new Date()

  const hasRootPage = ['page.tsx', 'page.ts', 'page.jsx', 'page.js']
    .some(f => fs.existsSync(path.join(appDir, f)))

  const routes = [
    ...(hasRootPage ? ['/'] : []),
    ...discoverRoutes(appDir),
  ].filter(route =>
    !EXCLUDED_PREFIXES.some(prefix => route === prefix || route.startsWith(prefix + '/'))
  )

  return routes.map(route => ({
    url: route === '/' ? BASE_URL : `${BASE_URL}${route}`,
    lastModified: now,
    changeFrequency: CHANGE_FREQ_MAP[route] || 'monthly',
    priority: PRIORITY_MAP[route] ?? 0.5,
  }))
}
