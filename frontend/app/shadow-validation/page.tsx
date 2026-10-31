"use client";

import { useEffect, useState } from 'react';
import {
  fetchShadowStatus, 
  startShadowPeriod, 
  abortShadowPeriod, 
  generateShadowReport, 
  triggerShadowComparison,
  fetchShadowDailyLogs,
  ShadowValidationStatus,
  ShadowDailyLogData
} from '../../lib/api';
import styles from './page.module.css';

export default function ShadowValidationPage() {
  const [status, setStatus] = useState<ShadowValidationStatus | null>(null);
  const [logs, setLogs] = useState<ShadowDailyLogData[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await fetchShadowStatus();
      setStatus(data);
      
      if (data.active && data.period_id) {
        const logsData = await fetchShadowDailyLogs(data.period_id);
        setLogs(logsData.logs || []);
      } else if (data.latest_period && data.latest_period.id) {
        const logsData = await fetchShadowDailyLogs(data.latest_period.id);
        setLogs(logsData.logs || []);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load shadow validation status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleStart = async () => {
    try {
      setActionLoading(true);
      await startShadowPeriod();
      await loadStatus();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAbort = async () => {
    const reason = prompt("Enter reason for aborting:");
    if (!reason) return;
    try {
      setActionLoading(true);
      await abortShadowPeriod(status?.period_id!, reason);
      await loadStatus();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTrigger = async () => {
    try {
      setActionLoading(true);
      await triggerShadowComparison();
      alert("Triggered daily comparison. Refresh in a moment.");
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    try {
      setActionLoading(true);
      await generateShadowReport(status?.period_id || status?.latest_period?.id!);
      await loadStatus();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && !status) return <div className={styles.loading}>Loading...</div>;
  if (error) return <div className={styles.error}>{error}</div>;

  const renderLogsTable = () => {
    if (logs.length === 0) return null;
    
    return (
      <div className={styles.logsContainer}>
        <h3 className={styles.logsTitle}>Daily Comparison Logs</h3>
        <div className={styles.tableWrapper}>
          <table className={styles.logsTable}>
            <thead>
              <tr>
                <th>Day</th>
                <th>Date</th>
                <th>Control Dep. %</th>
                <th>Variant Dep. %</th>
                <th>Regime</th>
                <th>Control Return</th>
                <th>Variant Return</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.day_number}>
                  <td>{log.day_number}</td>
                  <td>{log.trading_day}</td>
                  <td>{log.control_deployment_pct.toFixed(1)}%</td>
                  <td>{log.variant_deployment_pct.toFixed(1)}%</td>
                  <td>{log.variant_regime}</td>
                  <td className={log.control_portfolio_return! >= 0 ? styles.positive : styles.negative}>
                    {log.control_portfolio_return !== null ? `${(log.control_portfolio_return * 100).toFixed(2)}%` : 'N/A'}
                  </td>
                  <td className={log.variant_portfolio_return! >= 0 ? styles.positive : styles.negative}>
                    {log.variant_portfolio_return !== null ? `${(log.variant_portfolio_return * 100).toFixed(2)}%` : 'N/A'}
                  </td>
                  <td className={log.return_delta! > 0 ? styles.positive : (log.return_delta! < 0 ? styles.negative : '')}>
                    {log.return_delta !== null ? `${(log.return_delta * 100).toFixed(2)}%` : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>60-Day Shadow Validation</h1>
        <p>Parallel testing of Deterministic (Control) vs Markov-Aware (Variant) allocation models</p>
      </header>

      {status?.active ? (
        <div className={styles.activePeriodCard}>
          <div className={styles.cardHeader}>
            <h2>{status.period_name}</h2>
            <span className={styles.badgeRunning}>RUNNING</span>
          </div>
          
          <div className={styles.progressSection}>
            <div className={styles.progressInfo}>
              <span>Day {status.days_logged} / {status.target_days}</span>
              <span>{status.progress_pct}% Completed</span>
            </div>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill} 
                style={{ width: `${status.progress_pct}%` }}
              ></div>
            </div>
          </div>

          {status.latest_day && (
            <div className={styles.latestStatsGrid}>
              <div className={styles.statBox}>
                <span className={styles.statLabel}>Latest Date</span>
                <span className={styles.statValue}>{status.latest_day.date}</span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statLabel}>Control Return (Cumulative)</span>
                <span className={`${styles.statValue} ${
                  status.latest_day.control_return! >= 0 ? styles.positive : styles.negative
                }`}>
                  {status.latest_day.control_return !== null 
                    ? `${(status.latest_day.control_return * 100).toFixed(2)}%` 
                    : 'N/A'}
                </span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statLabel}>Variant Return (Cumulative)</span>
                <span className={`${styles.statValue} ${
                  status.latest_day.variant_return! >= 0 ? styles.positive : styles.negative
                }`}>
                  {status.latest_day.variant_return !== null 
                    ? `${(status.latest_day.variant_return * 100).toFixed(2)}%` 
                    : 'N/A'}
                </span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statLabel}>Variant Regime</span>
                <span className={styles.statValue}>{status.latest_day.variant_regime || 'N/A'}</span>
              </div>
            </div>
          )}

          <div className={styles.actions}>
            <button 
              className={styles.btnSecondary} 
              onClick={handleTrigger}
              disabled={actionLoading}
            >
              Run Daily Comparison (Manual)
            </button>
            <button 
              className={styles.btnDanger} 
              onClick={handleAbort}
              disabled={actionLoading}
            >
              Abort Shadow Period
            </button>
            {status.days_logged! >= 60 && (
              <button 
                className={styles.btnPrimary} 
                onClick={handleGenerateReport}
                disabled={actionLoading}
              >
                Generate Final Report
              </button>
            )}
          </div>
          
          {renderLogsTable()}
        </div>
      ) : (
        <div className={styles.inactivePeriodCard}>
          <h2>No Active Shadow Period</h2>
          <p>Start a new 60-day shadow validation period to begin parallel testing.</p>
          <button 
            className={styles.btnPrimary} 
            onClick={handleStart}
            disabled={actionLoading}
          >
            Start New Period
          </button>

          {status?.latest_period && (
            <div className={styles.latestPeriodInfo}>
              <h3>Latest Completed Period</h3>
              <ul>
                <li><strong>Name:</strong> {status.latest_period.name}</li>
                <li><strong>Status:</strong> {status.latest_period.status}</li>
                <li><strong>Verdict:</strong> {status.latest_period.verdict || "Pending Report"}</li>
                <li><strong>Start Date:</strong> {status.latest_period.start_date}</li>
                <li><strong>End Date:</strong> {status.latest_period.end_date}</li>
              </ul>
              {!status.latest_period.verdict && status.latest_period.status === "COMPLETED" && (
                <button 
                  className={styles.btnPrimary} 
                  onClick={handleGenerateReport}
                  disabled={actionLoading}
                  style={{ marginTop: '1rem' }}
                >
                  Generate Final Report
                </button>
              )}
            </div>
          )}
          {renderLogsTable()}
        </div>
      )}
    </div>
  );
}
