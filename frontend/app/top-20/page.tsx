"use client";

import { useState, useEffect } from "react";
import styles from "./page.module.css";
import {
  Top20Entry,
  Top20Summary,
  fetchTop20Portfolio,
  fetchTop20Summary,
  triggerBot4Allocate,
  triggerBot5Top20,
  StressTestResult,
  fetchStressTestResult,
  triggerBot6StressTest,
  fetchTaskStatus,
  RegimeSnapshot,
  fetchRegimeSnapshot,
  AllocationRunResult,
  fetchAllocationRun
} from "@/lib/api";

export default function Top20Page() {
  const [portfolio, setPortfolio] = useState<Top20Entry[]>([]);
  const [summary, setSummary] = useState<Top20Summary | null>(null);
  const [stressTest, setStressTest] = useState<StressTestResult | null>(null);
  const [regime, setRegime] = useState<RegimeSnapshot | null>(null);
  const [allocation, setAllocation] = useState<AllocationRunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [toast, setToast] = useState<{
    msg: string;
    type: "info" | "error";
  } | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [portfolioRes, summaryRes, stressRes, regimeRes, allocRes] = await Promise.all([
        fetchTop20Portfolio(),
        fetchTop20Summary(),
        fetchStressTestResult().catch(() => null), // Optional
        fetchRegimeSnapshot().catch(() => null), // Optional
        fetchAllocationRun().catch(() => null), // Optional
      ]);
      setPortfolio(portfolioRes.data || []);
      // @ts-ignore
      if (!summaryRes.error) {
        setSummary(summaryRes);
      }
      if (stressRes && !stressRes.error) {
        setStressTest(stressRes);
      }
      if (regimeRes && !regimeRes.error) {
        setRegime(regimeRes);
      }
      if (allocRes && !allocRes.error) {
        setAllocation(allocRes);
      }
    } catch (err) {
      console.error("Failed to load Top 20 data", err);
      showToast(
        "Failed to load portfolio data. Is the backend running?",
        "error",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const showToast = (msg: string, type: "info" | "error" = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const pollTask = async (taskId: string): Promise<string> => {
    if (!taskId || taskId === "sync-task" || taskId === "failed")
      return "Completed";
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const status = await fetchTaskStatus(taskId);
        if (status.ready) {
          if (status.state === "SUCCESS")
            return status.result || "Completed successfully";
          throw new Error(status.error || "Task failed");
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }
    throw new Error("Task timed out after 2 minutes");
  };

  const handleRunBot4 = async () => {
    try {
      setIsGenerating(true);
      showToast("Running Bot 4: Calculating Allocations...", "info");
      const result = await triggerBot4Allocate();
      const finalMsg = await pollTask(result.task_id);
      showToast(finalMsg, "info");
    } catch (err: any) {
      showToast(err.message || "Bot 4 failed to run.", "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunBot5 = async () => {
    try {
      setIsGenerating(true);
      showToast("Running Bot 5: Generating Top 20...", "info");
      const result = await triggerBot5Top20();
      const finalMsg = await pollTask(result.task_id);
      await loadData();
      showToast(finalMsg, "info");
    } catch (err: any) {
      showToast(err.message || "Bot 5 failed to run.", "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunBot6 = async () => {
    try {
      setIsGenerating(true);
      showToast("Running Bot 6: Stress Testing Portfolio...", "info");
      const result = await triggerBot6StressTest();
      const finalMsg = await pollTask(result.task_id);
      await loadData();
      showToast(finalMsg, "info");
    } catch (err: any) {
      showToast(err.message || "Bot 6 failed to run.", "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (loading) {
    return <div className={styles.loading}>Loading AI Portfolio...</div>;
  }

  return (
    <div className={styles.container}>
      {/* Toast Notification */}
      {toast && (
        <div
          style={{
            position: "fixed",
            top: "20px",
            right: "20px",
            padding: "1rem 2rem",
            background: toast.type === "error" ? "#f56565" : "#4facfe",
            color: "white",
            borderRadius: "8px",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            zIndex: 1000,
            fontWeight: "bold",
            transition: "all 0.3s ease",
          }}
        >
          {toast.msg}
        </div>
      )}

      <header className={styles.header}>
        <div className={styles.titleWrapper}>
          <div>
            <h1 className={styles.title}>AI-Curated Top 20</h1>
            <p className={styles.subtitle}>
              Risk-managed portfolio allocation generated by Bot 4 & Bot 5
              {summary && ` • Last updated: ${summary.date}`}
            </p>
          </div>
          <div className={styles.controls}>
            <button
              className={styles.triggerBtn}
              onClick={handleRunBot4}
              disabled={isGenerating}
            >
              <span>1️⃣</span> Run Bot 4 (Allocate)
            </button>
            <button
              className={styles.triggerBtn}
              onClick={handleRunBot5}
              disabled={isGenerating}
              style={{ borderColor: "#ecc94b", color: "#ecc94b" }}
            >
              <span>2️⃣</span> Run Bot 5 (Top 20)
            </button>
            <button
              className={styles.triggerBtn}
              onClick={handleRunBot6}
              disabled={isGenerating}
              style={{ borderColor: "#f56565", color: "#f56565" }}
            >
              <span>3️⃣</span> Run Bot 6 (Stress Test)
            </button>
          </div>
        </div>
      </header>

      {summary && (
        <div className={styles.summaryGrid}>
          <div className={styles.summaryCard}>
            <span className={styles.cardLabel}>Total Capital Allocated</span>
            <span className={styles.cardValue}>
              {formatCurrency(summary.total_allocation)}
            </span>
          </div>
          <div className={styles.summaryCard}>
            <span className={styles.cardLabel}>Portfolio Risk Score</span>
            <span
              className={styles.cardValue}
              style={{
                color:
                  summary.risk_score < 40
                    ? "#48bb78"
                    : summary.risk_score < 70
                      ? "#ecc94b"
                      : "#f56565",
              }}
            >
              {summary.risk_score} / 100
            </span>
          </div>
          <div className={styles.summaryCard}>
            <span className={styles.cardLabel}>Average EIN Score</span>
            <span className={styles.cardValue}>
              {summary.avg_ein_score.toFixed(1)}
            </span>
          </div>
          <div className={styles.summaryCard}>
            <span className={styles.cardLabel}>Sectors Covered</span>
            <span className={styles.cardValue}>{summary.sector_count}</span>
          </div>
        </div>
      )}

      {(regime || allocation) && (
        <div className={styles.summaryGrid} style={{ marginTop: '1rem', borderTop: '1px solid #2d3748', paddingTop: '1rem' }}>
          {regime && (
            <>
              <div className={styles.summaryCard}>
                <span className={styles.cardLabel}>Markov Regime</span>
                <span
                  className={styles.cardValue}
                  style={{
                    color:
                      regime.regime === "RISK_ON"
                        ? "#48bb78"
                        : regime.regime === "NEUTRAL"
                          ? "#4facfe"
                          : regime.regime === "RECOVERY"
                            ? "#ecc94b"
                            : "#f56565",
                  }}
                >
                  {regime.regime}
                </span>
              </div>
              <div className={styles.summaryCard}>
                <span className={styles.cardLabel}>Transition Entropy</span>
                <span className={styles.cardValue}>{regime.entropy.toFixed(3)}</span>
              </div>
            </>
          )}
          
          {allocation && (
            <>
              <div className={styles.summaryCard}>
                <span className={styles.cardLabel}>Regime Modifier</span>
                <span className={styles.cardValue}>{(allocation.markov_modifier * 100).toFixed(1)}%</span>
              </div>
              <div className={styles.summaryCard}>
                <span className={styles.cardLabel}>Final Deployment</span>
                <span className={styles.cardValue} style={{ color: "#4facfe" }}>
                  {(allocation.m_final * 100).toFixed(1)}%
                </span>
              </div>
            </>
          )}
        </div>
      )}

      {stressTest && (
        <div className={styles.stressTestSection}>
          <div className={styles.stressHeader}>
            <div>
              <h2>Advanced Monte Carlo Stress Test</h2>
              <span style={{ fontSize: '0.8rem', color: '#a0aec0', fontFamily: 'monospace' }}>
                Seed: {stressTest.seed_hash}
              </span>
            </div>
            <span
              className={`${styles.statusBadge} ${styles[stressTest.status.toLowerCase()] || ''}`}
              style={{
                backgroundColor: 
                  stressTest.status === 'PASS' ? '#48bb78' :
                  stressTest.status === 'WATCH' ? '#38b2ac' :
                  stressTest.status === 'REVIEW' ? '#ecc94b' :
                  stressTest.status === 'REJECT' ? '#ed8936' :
                  '#f56565' // VETO
              }}
            >
              {stressTest.status}
            </span>
          </div>
          
          <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #2d3748', color: '#a0aec0' }}>
                  <th style={{ padding: '0.5rem' }}>Horizon</th>
                  <th style={{ padding: '0.5rem' }}>Expected Return (Mean)</th>
                  <th style={{ padding: '0.5rem' }}>VaR (95%)</th>
                  <th style={{ padding: '0.5rem' }}>CVaR (95%)</th>
                  <th style={{ padding: '0.5rem' }}>Prob of Loss</th>
                  <th style={{ padding: '0.5rem' }}>Prob &gt;20% DD</th>
                </tr>
              </thead>
              <tbody>
                {['20d', '60d', '125d'].map(horizon => {
                  const dist = stressTest.distribution_metrics?.[horizon];
                  const tail = stressTest.tail_risk_metrics?.[horizon];
                  const loss = stressTest.loss_probabilities?.[horizon];
                  
                  if (!dist || !tail || !loss) return null;
                  
                  return (
                    <tr key={horizon} style={{ borderBottom: '1px solid #1a202c' }}>
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: 'bold' }}>{horizon}</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: dist.mean > 0 ? '#48bb78' : '#f56565' }}>
                        {(dist.mean * 100).toFixed(2)}%
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>{(tail.var_95 * 100).toFixed(2)}%</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: tail.cvar_95 < -0.2 ? '#f56565' : 'inherit' }}>
                        {(tail.cvar_95 * 100).toFixed(2)}%
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>{(loss.loss * 100).toFixed(1)}%</td>
                      <td style={{ padding: '0.75rem 0.5rem', color: loss.dd_20pct > 0.1 ? '#f56565' : 'inherit' }}>
                        {(loss.dd_20pct * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {(stressTest.status === "REJECT" || stressTest.status === "VETO") && (
            <div className={styles.stressWarning} style={{ marginTop: '1rem', padding: '1rem', backgroundColor: 'rgba(245, 101, 101, 0.1)', border: '1px solid #f56565', borderRadius: '4px', color: '#f56565' }}>
              ⚠️ WARNING: The portfolio has failed the Monte Carlo stress test ({stressTest.status}). Tail risk exceeds acceptable thresholds. Please re-run Bot 4 with stricter risk parameters before proceeding.
            </div>
          )}
        </div>
      )}

      {portfolio.length === 0 ? (
        <div style={{ textAlign: "center", padding: "4rem", color: "#a0aec0" }}>
          <h2>No portfolio generated yet.</h2>
          <p>
            Run Bot 3, then Bot 4, then Bot 5 to generate your AI portfolio.
          </p>
        </div>
      ) : (
        <div className={styles.portfolioTable}>
          {portfolio.map((item) => (
            <div
              key={item.ticker}
              className={`${styles.row} ${item.rank === 1 ? styles.rank1 : item.rank === 2 ? styles.rank2 : item.rank === 3 ? styles.rank3 : ""}`}
            >
              {/* Rank */}
              <div className={styles.rankCol}>#{item.rank}</div>

              {/* Symbol & Name */}
              <div className={styles.symbolCol}>
                <div className={styles.ticker}>{item.ticker}</div>
                <div className={styles.companyName}>{item.company_name}</div>
              </div>

              {/* Allocation */}
              <div className={styles.allocCol}>
                <div className={styles.allocAmount}>
                  {formatCurrency(item.allocation_amount)}
                </div>
                <div className={styles.allocPct}>
                  {item.allocation_pct}% of Portfolio
                </div>
              </div>

              {/* Insights */}
              <div className={styles.insightCol}>
                <span className={styles.sectorBadge}>{item.sector}</span>
                <span className={styles.reasonText}>
                  {item.inclusion_reason}
                </span>
              </div>

              {/* Risk Category */}
              <div className={styles.riskCol}>
                <span
                  className={`${styles.riskBadge} ${styles[`risk${item.risk_category}`]}`}
                >
                  {item.risk_category} RISK
                </span>
              </div>

              {/* EIN Score */}
              <div
                className={styles.scoreCol}
                style={{
                  color:
                    item.ein_score >= 80
                      ? "#48bb78"
                      : item.ein_score >= 60
                        ? "#ecc94b"
                        : "#f56565",
                }}
              >
                <div className={styles.scoreValue}>
                  {item.ein_score.toFixed(1)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
