'use client';

import { useState, useEffect, useCallback } from 'react';
import styles from './page.module.css';
import TickerCard from '@/components/dashboard/TickerCard';
import MetricCard from '@/components/dashboard/MetricCard';
import ApiHealthMap from '@/components/dashboard/ApiHealthMap';
import BotController from '@/components/dashboard/BotController';
import ToastContainer from '@/components/ui/Toast';
import { TickerCardSkeleton, MetricCardSkeleton } from '@/components/ui/Skeleton';
import {
  fetchTickers,
  fetchMetrics,
  fetchApiHealth,
  type TickerData,
  type DashboardMetrics,
  type ApiHealthData,
} from '@/lib/api';

export default function DashboardPage() {
  // Ticker data state
  const [tickers, setTickers] = useState<TickerData[]>([]);
  const [tickersLoading, setTickersLoading] = useState(true);
  const [tickerLimit, setTickerLimit] = useState(3);

  // Metrics state
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  // API Health state
  const [apiHealth, setApiHealth] = useState<ApiHealthData | null>(null);
  const [apiHealthLoading, setApiHealthLoading] = useState(true);

  // ── Fetch Tickers ──
  const loadTickers = useCallback(async (forceLoading = false) => {
    try {
      if (forceLoading) {
        setTickersLoading(true);
      }
      const data = await fetchTickers(tickerLimit);
      setTickers(data);
    } catch (err) {
      console.error('Failed to fetch tickers:', err);
    } finally {
      setTickersLoading(false);
    }
  }, [tickerLimit]);

  // ── Fetch Metrics ──
  const loadMetrics = useCallback(async () => {
    try {
      const data = await fetchMetrics();
      setMetrics(data);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    } finally {
      setMetricsLoading(false);
    }
  }, []);

  // ── Fetch API Health ──
  const loadApiHealth = useCallback(async () => {
    try {
      const data = await fetchApiHealth();
      setApiHealth(data);
    } catch (err) {
      console.error('Failed to fetch API health:', err);
    } finally {
      setApiHealthLoading(false);
    }
  }, []);

  // ── Initial load + polling ──
  useEffect(() => {
    loadTickers();
    loadMetrics();
    loadApiHealth();

    // Poll tickers & metrics every 30 seconds
    const tickerInterval = setInterval(loadTickers, 30_000);
    const metricsInterval = setInterval(loadMetrics, 30_000);

    // Poll API health every 60 seconds
    const healthInterval = setInterval(loadApiHealth, 60_000);

    return () => {
      clearInterval(tickerInterval);
      clearInterval(metricsInterval);
      clearInterval(healthInterval);
    };
  }, [loadTickers, loadMetrics, loadApiHealth]);

  return (
    <div className={styles.dashboardGrid}>
      {/* Top Row: Metrics + Controls */}
      <div className={styles.topBar}>
        <div className={styles.titleGroup}>
          <h2 className={styles.sectionTitle}>Market Overview</h2>
          <div className={styles.dropdownWrapper}>
            <span>Showing:</span>
            <select 
              className={styles.limitSelect} 
              value={tickerLimit} 
              onChange={(e) => setTickerLimit(Number(e.target.value))}
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={20}>Top 20</option>
            </select>
          </div>
        </div>
        
        <div className={styles.controlsGroup}>
          <MetricCard
            label="System Latency"
            value={metricsLoading ? '—' : `${metrics?.system_latency_ms ?? 0}`}
            unit="ms"
            color="green"
            showDots
            isLoading={metricsLoading}
          />
        </div>
      </div>

      {/* Tickers Row */}
      <div className={styles.tickerGrid}>
        {tickersLoading ? (
          <>
            <TickerCardSkeleton />
            <TickerCardSkeleton />
            <TickerCardSkeleton />
          </>
        ) : (
          tickers.map((t) => (
            <TickerCard
              key={t.ticker}
              ticker={t.ticker}
              exchange={t.exchange}
              price={t.price}
              change={t.change}
              sparkData={t.sparkData}
              noData={t.noData}
            />
          ))
        )}
      </div>

      {/* Main Area: API Health + Bot Controller */}
      <div className={styles.mainArea}>
        <ApiHealthMap
          sources={apiHealth?.sources ?? []}
          gatewayOnline={apiHealth?.gateway_online ?? false}
          isLoading={apiHealthLoading}
        />
        <BotController />
      </div>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}
