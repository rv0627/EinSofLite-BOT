"use client";

import { useState, useEffect, useCallback, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import styles from "./page.module.css";
import SparklineChart from "@/components/ui/SparklineChart";
import CandlestickChart from "@/components/ui/CandlestickChart";
import AnalyticsSkeleton from "@/components/ui/AnalyticsSkeleton";
import IndicatorPanel from "@/components/ui/IndicatorPanel";
import IndicatorModal from "@/components/ui/IndicatorModal";
import { fetchAnalyticsData, type AnalyticsData } from "@/lib/api";
import {
  calculateIndicator,
  calcMA,
  DEFAULT_INDICATORS,
  DEFAULT_MA_CONFIG,
} from "@/lib/indicators";
import type { IndicatorConfig, MAConfig } from "@/lib/indicators";

function AnalyticsContent() {
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get("ticker") || "RELIANCE";

  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [interval, setIntervalState] = useState<string>("D");

  // Indicator State
  const [indicatorsConfig, setIndicatorsConfig] =
    useState<IndicatorConfig[]>(DEFAULT_INDICATORS);
  const [maConfig, setMaConfig] = useState<MAConfig>(DEFAULT_MA_CONFIG);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(30);

  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const savedInd = localStorage.getItem("einsof_indicators");
    const savedMa = localStorage.getItem("einsof_ma");
    if (savedInd) {
      try {
        setIndicatorsConfig(JSON.parse(savedInd));
      } catch (e) {}
    }
    if (savedMa) {
      try {
        setMaConfig(JSON.parse(savedMa));
      } catch (e) {}
    }
  }, []);

  const handleSaveIndicators = (newInd: IndicatorConfig[], newMA: MAConfig) => {
    setIndicatorsConfig(newInd);
    setMaConfig(newMA);
    localStorage.setItem("einsof_indicators", JSON.stringify(newInd));
    localStorage.setItem("einsof_ma", JSON.stringify(newMA));
  };

  const loadData = useCallback(async () => {
    try {
      const result = await fetchAnalyticsData(tickerParam, interval);
      setData(result);
      setError(null);
    } catch (err: any) {
      console.error("Failed to fetch analytics:", err);
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [tickerParam, interval]);

  useEffect(() => {
    setLoading(true);
    loadData();

    // Poll every 30 seconds
    const pollInterval = setInterval(loadData, 30_000);
    return () => clearInterval(pollInterval);
  }, [loadData]);

  // Handle native wheel event to prevent page scroll
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !data?.rawOHLCV) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault(); // Stop page from scrolling
      const zoomDelta = e.deltaY > 0 ? 5 : -5;
      setZoomLevel((prev) =>
        Math.max(10, Math.min(data.rawOHLCV.length, prev + zoomDelta)),
      );
    };

    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, [data?.rawOHLCV]);

  if (loading) return <AnalyticsSkeleton />;

  if (error || !data) {
    return (
      <div className={styles.page}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            gap: "16px",
            color: "var(--text-muted)",
          }}
        >
          <div className={styles.intervalTabs} style={{ marginBottom: "24px" }}>
            {["1m", "5m", "15m", "1h", "D"].map((int) => (
              <button
                key={int}
                className={`${styles.intervalTab} ${interval === int ? styles.active : ""}`}
                onClick={() => setIntervalState(int)}
              >
                {int}
              </button>
            ))}
          </div>
          <div style={{ fontSize: "3rem" }}>📉</div>
          <h2>Data Not Available</h2>
          <p>We couldn&apos;t find analytics data for {tickerParam}.</p>

          <div
            style={{
              marginTop: "16px",
              display: "flex",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <span>Try another ticker:</span>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "20px",
                padding: "8px 16px",
              }}
            >
              <Search size={16} style={{ color: "var(--text-muted)" }} />
              <input
                type="text"
                placeholder="Search Ticker..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const value = (e.target as HTMLInputElement).value
                      .toUpperCase()
                      .trim();
                    if (value) {
                      const url = new URL(window.location.href);
                      url.searchParams.set("ticker", value);
                      window.location.href = url.toString();
                    }
                  }
                }}
                style={{
                  background: "transparent",
                  color: "var(--text-primary)",
                  border: "none",
                  fontSize: "1rem",
                  outline: "none",
                  width: "160px",
                }}
              />
            </div>
          </div>

          <p
            style={{
              fontSize: "0.8rem",
              color: "var(--accent-red)",
              marginTop: "16px",
              maxWidth: "600px",
              textAlign: "center",
              lineHeight: "1.5",
            }}
          >
            {error}
          </p>
        </div>
      </div>
    );
  }

  const { symbol, price, rawOHLCV, dataQuality, events, sentiment } = data;
  const isPositiveChange = price.change_pct >= 0;

  // Compute visible chart data based on zoomLevel
  const visibleChartData = rawOHLCV.slice(-zoomLevel);

  // Compute active indicators client-side (calculated over full rawOHLCV for accuracy)
  const activeIndicators = indicatorsConfig
    .filter((ind) => ind.enabled)
    .map((config) => calculateIndicator(rawOHLCV, config))
    .filter((res) => res !== null);

  const maOverlays = calcMA(visibleChartData, maConfig);

  return (
    <div className={styles.page}>
      {/* ── Stock Header ── */}
      <div className={styles.stockHeader}>
        <div>
          <div className={styles.breadcrumb}>
            Equities <span className={styles.breadcrumbSep}>›</span>
            {symbol.exchange} <span className={styles.breadcrumbSep}>›</span>
            <span>{symbol.ticker}</span>
          </div>
          <div
            className={styles.stockName}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              gap: "12px",
            }}
          >
            {symbol.name}
            <span className={styles.tickerBadge}>
              {symbol.ticker} : {symbol.exchange}
            </span>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "20px",
                padding: "6px 14px",
                marginLeft: "16px",
              }}
            >
              <Search size={14} style={{ color: "var(--text-muted)" }} />
              <input
                type="text"
                placeholder="Search Ticker..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const value = (e.target as HTMLInputElement).value
                      .toUpperCase()
                      .trim();
                    if (value) {
                      const url = new URL(window.location.href);
                      url.searchParams.set("ticker", value);
                      window.location.href = url.toString();
                    }
                  }
                }}
                style={{
                  background: "transparent",
                  color: "var(--text-primary)",
                  border: "none",
                  fontSize: "0.85rem",
                  outline: "none",
                  width: "120px",
                }}
              />
            </div>
          </div>
        </div>

        <div className={styles.priceGroup}>
          <div className={styles.priceCard}>
            <div className={styles.priceLabel}>Live Price</div>
            <div className={styles.priceValue}>
              {price.live.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>
          <div
            className={`${styles.priceCard} ${isPositiveChange ? styles.positive : styles.negative}`}
          >
            <div className={styles.priceLabel}>Day Change</div>
            <div className={styles.priceValue}>
              {isPositiveChange ? "+" : ""}
              {price.change_pct}%
            </div>
          </div>
        </div>
      </div>

      {/* ── Main Layout ── */}
      <div className={styles.mainArea}>
        {/* ── Left Column: Charts & Indicators ── */}
        <div className={styles.chartSection}>
          <div className={styles.chartContainer} ref={chartContainerRef}>
            <div className={styles.chartToolbar}>
              <div className={styles.intervalTabs}>
                {["1m", "5m", "15m", "1h", "D"].map((int) => (
                  <button
                    key={int}
                    className={`${styles.intervalTab} ${interval === int ? styles.active : ""}`}
                    onClick={() => setIntervalState(int)}
                  >
                    {int}
                  </button>
                ))}
              </div>

              <div className={styles.chartControls}>
                <button
                  className={styles.chartControl}
                  onClick={() =>
                    setZoomLevel((prev) => Math.max(10, prev - 10))
                  }
                  title="Zoom In"
                >
                  <span style={{ fontSize: "1.2rem", lineHeight: 1 }}>＋</span>
                </button>
                <button
                  className={styles.chartControl}
                  onClick={() =>
                    setZoomLevel((prev) => Math.min(rawOHLCV.length, prev + 10))
                  }
                  title="Zoom Out"
                >
                  <span style={{ fontSize: "1.2rem", lineHeight: 1 }}>−</span>
                </button>
                <button className={styles.chartControl}>
                  <span>⫟</span> Candles
                </button>
                <button
                  className={styles.chartControl}
                  onClick={() => setIsModalOpen(true)}
                >
                  <span>⊕</span> Indicators
                </button>
                <div className={styles.marketLive}>
                  <span className={styles.liveDot}></span>Online
                </div>
              </div>
            </div>

            {/* Candlestick Area */}
            <div className={styles.candlestickArea}>
              <CandlestickChart data={visibleChartData} overlays={maOverlays} />
            </div>

            {/* Dynamic Indicator Panels */}
            {activeIndicators.map(
              (result, idx) =>
                result && (
                  <IndicatorPanel
                    key={`${result.name}-${idx}`}
                    result={result}
                    chartLength={visibleChartData.length}
                    height={100}
                  />
                ),
            )}
          </div>
        </div>

        {/* ── Right Column: Insights & Execution ── */}
        <div className={styles.rightPanel}>
          {/* Data Quality */}
          <div className={styles.dataQualityCard}>
            <div className={styles.dqHeader}>
              <span className={styles.dqIcon}>⚙</span> Data Quality
            </div>
            <div className={styles.confidenceRing}>
              <svg width="120" height="120" viewBox="0 0 120 120">
                <circle
                  cx="60"
                  cy="60"
                  r="50"
                  fill="none"
                  stroke="var(--bg-elevated)"
                  strokeWidth="8"
                />
                <circle
                  cx="60"
                  cy="60"
                  r="50"
                  fill="none"
                  stroke="var(--accent-cyan)"
                  strokeWidth="8"
                  strokeDasharray="314"
                  strokeDashoffset={314 - (314 * dataQuality.confidence) / 100}
                  strokeLinecap="round"
                  transform="rotate(-90 60 60)"
                />
              </svg>
              <div className={styles.confidenceValue}>
                <div className={styles.confidencePercent}>
                  {dataQuality.confidence}%
                </div>
                <div className={styles.confidenceLabel}>Confidence</div>
              </div>
            </div>

            <div className={styles.anomalyRow}>
              <span className={styles.anomalyLabel}>Anomalous Points</span>
              <span className={styles.anomalyBadge}>
                {dataQuality.anomalies.toString().padStart(2, "0")} Detected
              </span>
            </div>
          </div>

          {/* Event Cards */}
          {events.map((event, idx) => (
            <div key={idx} className={styles.eventCard}>
              <div className={`${styles.eventIcon} ${styles[event.type]}`}>
                {event.type === "warning"
                  ? "⚠"
                  : event.type === "error"
                    ? "✕"
                    : "ℹ"}
              </div>
              <div>
                <div className={styles.eventTitle}>{event.title}</div>
                <div className={styles.eventDesc}>{event.desc}</div>
              </div>
            </div>
          ))}

          {/* Sentiment Analysis */}
          <div className={styles.sentimentCard}>
            <div className={styles.sentimentTitle}>Sentiment Analysis</div>
            <div className={styles.sentimentScores}>
              <div className={styles.sentimentScore}>
                <div className={`${styles.scoreValue} ${styles.bullish}`}>
                  {sentiment.bullish}%
                </div>
                <div className={styles.scoreLabel}>Bullish</div>
              </div>
              <div className={styles.sentimentScore}>
                <div className={`${styles.scoreValue} ${styles.bearish}`}>
                  {sentiment.bearish}%
                </div>
                <div className={styles.scoreLabel}>Bearish</div>
              </div>
            </div>
            <div className={styles.sentimentBar}>
              <div
                className={`${styles.sentimentBarFill} ${styles.bullish}`}
                style={{ width: `${sentiment.bullish}%` }}
              ></div>
              <div
                className={`${styles.sentimentBarFill} ${styles.bearish}`}
                style={{ width: `${sentiment.bearish}%` }}
              ></div>
            </div>

            <div className={styles.sentimentMeta}>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>News Sentiment</span>
                <span
                  className={`${styles.metaValue} ${sentiment.news === "Positive" ? styles.positive : styles.negative}`}
                >
                  {sentiment.news}
                </span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Social Volatility</span>
                <span className={`${styles.metaValue} ${styles.notable}`}>
                  {sentiment.social}
                </span>
              </div>
            </div>
          </div>

          {/* <div className={styles.executionCard}>
              <div className={styles.executionTitle}>Market Execution</div>
              <div className={styles.executionButtons}>
                  <button className={styles.buyBtn} onClick={() => alert("Order Execution is Disabled in Demo Mode")}>BUY</button>
                  <button className={styles.sellBtn} onClick={() => alert("Order Execution is Disabled in Demo Mode")}>SELL</button>
              </div>
              <button className={styles.alertBtn} onClick={() => alert("Alerts are Disabled in Demo Mode")}>SET ALERT</button>
          </div> */}
        </div>
      </div>

      {/* Settings Modal */}
      <IndicatorModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        indicators={indicatorsConfig}
        maConfig={maConfig}
        onSave={handleSaveIndicators}
      />
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<AnalyticsSkeleton />}>
      <AnalyticsContent />
    </Suspense>
  );
}
