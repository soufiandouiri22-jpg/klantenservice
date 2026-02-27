'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  Eye,
  Timer,
  ArrowUpRight,
  Globe,
  ExternalLink,
  RefreshCw,
  TrendingUp,
} from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { adminApi } from '@/lib/api'

const PERIODS = [
  { value: '7d', label: '7 dagen' },
  { value: '30d', label: '30 dagen' },
  { value: '6mo', label: '6 maanden' },
  { value: '12mo', label: '12 maanden' },
]

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function MiniBarChart({ data, dataKey }: { data: { date: string; visitors: number; pageviews: number }[]; dataKey: 'visitors' | 'pageviews' }) {
  if (!data || data.length === 0) return null
  const values = data.map(d => d[dataKey])
  const max = Math.max(...values, 1)

  return (
    <div className="flex items-end gap-[2px] h-32 w-full">
      {data.map((d, i) => {
        const height = (d[dataKey] / max) * 100
        return (
          <div
            key={d.date || i}
            className="flex-1 group relative"
          >
            <div
              className="w-full bg-primary-500 rounded-t-sm hover:bg-primary-600 transition-colors cursor-default"
              style={{ height: `${Math.max(height, 2)}%` }}
            />
            <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
              <div className="bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap shadow-lg">
                {d.date}: {d[dataKey].toLocaleString()}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function AnalyticsTab() {
  const [period, setPeriod] = useState('30d')

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['admin-analytics', period],
    queryFn: () => adminApi.getAnalytics(period),
    refetchInterval: 120000,
  })

  const agg = data?.aggregate || {}
  const timeseries = data?.timeseries || []
  const topPages = data?.top_pages || []
  const topSources = data?.top_sources || []

  const maxPageVisitors = Math.max(...topPages.map((p: any) => p.visitors || 0), 1)
  const maxSourceVisitors = Math.max(...topSources.map((s: any) => s.visitors || 0), 1)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Website Analytics</h2>
          <p className="text-sm text-gray-500">Bezoekersdata via Plausible Analytics</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  period === p.value
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <Card>
              <CardBody className="p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <Users className="h-4 w-4" />
                  <span className="text-xs font-medium">Bezoekers</span>
                </div>
                <p className="text-2xl font-semibold text-gray-900">
                  {(agg.visitors?.value || 0).toLocaleString()}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <TrendingUp className="h-4 w-4" />
                  <span className="text-xs font-medium">Sessies</span>
                </div>
                <p className="text-2xl font-semibold text-gray-900">
                  {(agg.visits?.value || 0).toLocaleString()}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <Eye className="h-4 w-4" />
                  <span className="text-xs font-medium">Paginaweergaven</span>
                </div>
                <p className="text-2xl font-semibold text-gray-900">
                  {(agg.pageviews?.value || 0).toLocaleString()}
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <ArrowUpRight className="h-4 w-4" />
                  <span className="text-xs font-medium">Bounce Rate</span>
                </div>
                <p className="text-2xl font-semibold text-gray-900">
                  {agg.bounce_rate?.value || 0}%
                </p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="p-4">
                <div className="flex items-center gap-2 text-gray-500 mb-1">
                  <Timer className="h-4 w-4" />
                  <span className="text-xs font-medium">Gem. bezoekduur</span>
                </div>
                <p className="text-2xl font-semibold text-gray-900">
                  {formatDuration(agg.visit_duration?.value || 0)}
                </p>
              </CardBody>
            </Card>
          </div>

          {/* Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Bezoekers</CardTitle>
            </CardHeader>
            <CardBody>
              {timeseries.length > 0 ? (
                <MiniBarChart data={timeseries} dataKey="visitors" />
              ) : (
                <p className="text-sm text-gray-400 text-center py-8">Geen data beschikbaar</p>
              )}
            </CardBody>
          </Card>

          {/* Top Pages & Sources */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Pages */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Top Pagina&apos;s
                </CardTitle>
              </CardHeader>
              <CardBody>
                {topPages.length > 0 ? (
                  <div className="space-y-3">
                    {topPages.map((page: any, i: number) => (
                      <div key={page.page || i}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-700 truncate max-w-[70%]">
                            {page.page === '/' ? 'Homepage' : page.page}
                          </span>
                          <div className="flex items-center gap-3 text-sm">
                            <span className="text-gray-500">{page.visitors} bezoekers</span>
                            <span className="text-gray-400">{page.pageviews} views</span>
                          </div>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5">
                          <div
                            className="bg-primary-500 h-1.5 rounded-full transition-all"
                            style={{ width: `${(page.visitors / maxPageVisitors) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-8">Geen data beschikbaar</p>
                )}
              </CardBody>
            </Card>

            {/* Top Sources */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ExternalLink className="h-4 w-4" />
                  Verwijzingsbronnen
                </CardTitle>
              </CardHeader>
              <CardBody>
                {topSources.length > 0 ? (
                  <div className="space-y-3">
                    {topSources.map((source: any, i: number) => (
                      <div key={source.source || i}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-700">
                            {source.source || 'Direct / Geen'}
                          </span>
                          <span className="text-sm text-gray-500">{source.visitors} bezoekers</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5">
                          <div
                            className="bg-blue-500 h-1.5 rounded-full transition-all"
                            style={{ width: `${(source.visitors / maxSourceVisitors) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-8">Geen data beschikbaar</p>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
