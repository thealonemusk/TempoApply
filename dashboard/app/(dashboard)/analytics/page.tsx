'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { api } from '@/lib/api';
import { PLATFORM_COLORS, platformLabel } from '@/lib/platforms';
import type { Analytics } from '@/lib/types';
import { Card, CardDescription, CardTitle } from '@/components/ui/Card';

const STATUS_COLORS: Record<string, string> = {
  discovered: '#8E8E93',
  scored: '#007AFF',
  tailored: '#5856D6',
  applied: '#34C759',
  interviewing: '#FF9500',
  rejected: '#FF3B30',
  offer: '#FFD60A',
  ignored: '#636366',
};

const tooltipStyle = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  fontSize: '12px',
  color: 'var(--text-primary)',
};

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAnalytics().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const statusData =
    data?.by_status
      ? Object.entries(data.by_status)
          .filter(([, v]) => v > 0)
          .map(([k, v]) => ({
            name: k.charAt(0).toUpperCase() + k.slice(1),
            value: v,
            color: STATUS_COLORS[k] || '#8E8E93',
          }))
      : [];

  const platformData =
    data?.by_platform
      ? Object.entries(data.by_platform)
          .filter(([, v]) => v > 0)
          .map(([k, v]) => ({
            name: platformLabel(k),
            value: v,
            fill: PLATFORM_COLORS[k] || '#8E8E93',
          }))
      : [];

  const applied = data?.by_status.applied || 0;
  const interviewing = data?.by_status.interviewing || 0;
  const offers = data?.by_status.offer || 0;

  return (
    <>
      <header className="glass sticky top-0 z-20 border-b border-[var(--border)] px-8 py-5">
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">Analytics</h1>
        <p className="mt-0.5 text-sm text-[var(--text-muted)]">Pipeline overview</p>
      </header>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-5xl space-y-6">
          {loading ? (
            <div className="py-24 text-center text-sm text-[var(--text-muted)]">Loading…</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                {[
                  { label: 'Total', value: data?.total_jobs || 0 },
                  { label: 'Applied', value: applied },
                  { label: 'Interviewing', value: interviewing },
                  { label: 'Offers', value: offers },
                ].map((s) => (
                  <Card key={s.label} padding>
                    <p className="text-sm text-[var(--text-muted)]">{s.label}</p>
                    <p className="mt-1 text-3xl font-semibold tabular-nums text-[var(--text-primary)]">{s.value}</p>
                  </Card>
                ))}
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardTitle>Pipeline</CardTitle>
                  <CardDescription>Jobs by status</CardDescription>
                  <div className="mt-4 h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={statusData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                        >
                          {statusData.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={tooltipStyle} />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card>
                  <CardTitle>Sources</CardTitle>
                  <CardDescription>Jobs by platform</CardDescription>
                  <div className="mt-4 h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={platformData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--surface-2)' }} />
                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                          {platformData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              </div>

              {data?.top_companies && data.top_companies.length > 0 && (
                <Card>
                  <CardTitle>Top companies</CardTitle>
                  <CardDescription>Highest relevance scores</CardDescription>
                  <div className="mt-4 space-y-3">
                    {data.top_companies.map((c, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <span className="w-5 text-right text-xs tabular-nums text-[var(--text-muted)]">{i + 1}</span>
                        <div className="flex-1">
                          <div className="flex justify-between text-sm">
                            <span className="font-medium text-[var(--text-primary)]">{c.company}</span>
                            <span className="tabular-nums text-[var(--text-muted)]">{Math.round(c.score)}</span>
                          </div>
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                            <div
                              className="h-full rounded-full bg-[var(--accent)] transition-all"
                              style={{ width: `${Math.min(100, c.score)}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
