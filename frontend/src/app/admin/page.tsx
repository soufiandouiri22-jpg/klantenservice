'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { 
  LayoutDashboard,
  Users,
  Shield, 
  ShieldCheck,
  Mic,
  FileText,
  BarChart3
} from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Header } from '@/components/layout/Header'
import { useAuthStore } from '@/lib/store'

// Tab components
import { OverviewTab } from './components/OverviewTab'
import { AnalyticsTab } from './components/AnalyticsTab'
import { CustomersTab } from './components/CustomersTab'
import { PoliciesTab } from './components/PoliciesTab'
import { VoiceTab } from './components/VoiceTab'
import { LogsTab } from './components/LogsTab'
import { PolicyTraceTab } from './components/PolicyTraceTab'

const tabs = [
  { id: 'overview', name: 'Overzicht', icon: LayoutDashboard },
  { id: 'analytics', name: 'Analytics', icon: BarChart3 },
  { id: 'customers', name: 'Klanten', icon: Users },
  { id: 'policies', name: 'Policies', icon: Shield },
  { id: 'policy-trace', name: 'Call Control', icon: ShieldCheck },
  { id: 'voice', name: 'Realtime Voice', icon: Mic },
  { id: 'logs', name: 'Logs & Debug', icon: FileText },
]

export default function AdminPage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('overview')

  // Check if user is superadmin
  useEffect(() => {
    if (user && !user.is_superadmin) {
      router.push('/dashboard')
    }
  }, [user, router])

  if (!user?.is_superadmin) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <Shield className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900">Geen toegang</h2>
            <p className="text-gray-500 mt-2">Je hebt geen rechten om deze pagina te bekijken.</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab />
      case 'analytics':
        return <AnalyticsTab />
      case 'customers':
        return <CustomersTab />
      case 'policies':
        return <PoliciesTab />
      case 'policy-trace':
        return <PolicyTraceTab />
      case 'voice':
        return <VoiceTab />
      case 'logs':
        return <LogsTab />
      default:
        return <OverviewTab />
    }
  }

  return (
    <DashboardLayout>
      <Header 
        title="Platform Admin" 
        description="Beheer platform-brede instellingen en monitor alle klanten."
      />

      <div className="p-4 sm:p-6">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200 mb-6 -mx-4 px-4 sm:mx-0 sm:px-0">
          <nav className="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto scrollbar-hide">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap
                    ${isActive 
                      ? 'border-primary-500 text-primary-600' 
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }
                  `}
                >
                  <Icon className="h-4 w-4" />
                  {tab.name}
                </button>
              )
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="mt-6">
          {renderTabContent()}
        </div>
        </div>
    </DashboardLayout>
  )
}
