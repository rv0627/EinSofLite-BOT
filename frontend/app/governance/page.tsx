"use client";

import { useState, useEffect } from "react";
import styles from "./page.module.css";
import { Shield, Activity, RefreshCw, AlertTriangle, CheckCircle2, History, Database, Cpu } from "lucide-react";
import {
  GovernanceSummary,
  GovernanceEvent,
  DriftReport,
  ModelVersion,
  fetchGovernanceSummary,
  fetchGovernanceEvents,
  fetchDriftReport,
  fetchModelVersions,
  triggerRecalibration,
  logGpOverride,
  triggerBot9DriftMonitor,
  fetchTaskStatus
} from "@/lib/api";

export default function GovernancePage() {
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [events, setEvents] = useState<GovernanceEvent[]>([]);
  const [driftReport, setDriftReport] = useState<DriftReport | null>(null);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "versions">("overview");
  const [toast, setToast] = useState<{ msg: string; type: "info" | "error" | "success" } | null>(null);

  const [gpOverrideModel, setGpOverrideModel] = useState("MARKOV");
  const [gpOverrideReason, setGpOverrideReason] = useState("");
  const [gpOverrideDecision, setGpOverrideDecision] = useState("APPROVED");

  const loadData = async () => {
    try {
      setLoading(true);
      const [sumRes, evRes, driftRes, verRes] = await Promise.all([
        fetchGovernanceSummary(),
        fetchGovernanceEvents(),
        fetchDriftReport("MARKOV", 30).catch(() => null),
        fetchModelVersions()
      ]);
      setSummary(sumRes);
      setEvents(evRes.events);
      setDriftReport(driftRes);
      setVersions(verRes.versions);
    } catch (err: any) {
      console.error("Failed to load governance data", err);
      showToast(err.message || "Failed to load governance data.", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const showToast = (msg: string, type: "info" | "error" | "success" = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const pollTask = async (taskId: string): Promise<string> => {
    if (!taskId) return "Completed";
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const status = await fetchTaskStatus(taskId);
        if (status.ready) {
          if (status.state === "SUCCESS") return status.result || "Completed successfully";
          throw new Error(status.error || "Task failed");
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }
    throw new Error("Task timed out");
  };

  const handleTriggerDrift = async () => {
    try {
      setIsProcessing(true);
      showToast("Triggering Bot 9 Drift Monitor...", "info");
      const result = await triggerBot9DriftMonitor();
      const finalMsg = await pollTask(result.task_id);
      await loadData();
      showToast(finalMsg, "success");
    } catch (err: any) {
      showToast(err.message || "Failed to run drift monitoring.", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRecalibrate = async (modelType: string) => {
    if (!window.confirm(`Are you sure you want to trigger manual recalibration for ${modelType}?`)) return;
    try {
      setIsProcessing(true);
      const res = await triggerRecalibration({ model_type: modelType, actor: "admin" });
      await loadData();
      showToast(res.message || "Recalibration triggered", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to trigger recalibration", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleGpOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gpOverrideReason.trim()) {
      showToast("Please provide a reason for the override.", "error");
      return;
    }
    try {
      setIsProcessing(true);
      const res = await logGpOverride({
        model_type: gpOverrideModel,
        decision: gpOverrideDecision,
        reason: gpOverrideReason,
        actor: "admin_gp" // In a real app, this would be the logged-in user
      });
      setGpOverrideReason("");
      await loadData();
      showToast(res.message || "Override logged", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to log override", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "N/A";
    const d = new Date(dateStr);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
        <RefreshCw className="animate-spin" style={{ marginRight: '12px' }} />
        Loading Governance & Audit Data...
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Toast Notification */}
      {toast && (
        <div style={{
            position: "fixed", top: "20px", right: "20px", padding: "1rem 2rem",
            background: toast.type === "error" ? "#ef4444" : toast.type === "success" ? "#10b981" : "#4facfe",
            color: "white", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            zIndex: 1000, fontWeight: "bold", transition: "all 0.3s ease",
        }}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <header className={styles.header}>
        <h1 className={styles.title}>
          <Shield className={styles.titleIcon} size={28} />
          Bot 9 — Model Governance & Audit
        </h1>
        <div className={styles.controls}>
          <button
            className={styles.btnAction}
            onClick={() => setActiveTab("overview")}
            style={activeTab === "overview" ? { borderColor: "var(--accent-purple)", color: "var(--accent-purple)" } : {}}
          >
            Dashboard
          </button>
          <button
            className={styles.btnAction}
            onClick={() => setActiveTab("versions")}
            style={activeTab === "versions" ? { borderColor: "var(--accent-purple)", color: "var(--accent-purple)" } : {}}
          >
            Version Registry
          </button>
          <button 
            className={styles.btnAction} 
            onClick={handleTriggerDrift}
            disabled={isProcessing}
          >
            <RefreshCw size={16} className={isProcessing ? "animate-spin" : ""} /> 
            Run Drift Monitor
          </button>
        </div>
      </header>

      {activeTab === "overview" && summary && (
        <>
          {/* Summary KPIs */}
          <div className={styles.gridSummary}>
            <div className={styles.summaryCard}>
              <div className={`${styles.iconWrapper} ${summary.latest_drift.status === 'DEGRADED' ? styles.statusDegraded : summary.latest_drift.status === 'WARNING' ? styles.statusWarning : styles.statusStable}`}>
                {summary.latest_drift.status === 'DEGRADED' ? <AlertTriangle size={24} /> : summary.latest_drift.status === 'WARNING' ? <Activity size={24} /> : <CheckCircle2 size={24} />}
              </div>
              <div className={styles.cardContent}>
                <span className={styles.cardLabel}>Overall Model Health</span>
                <span className={styles.cardValue}>{summary.latest_drift.status || "UNKNOWN"}</span>
              </div>
            </div>
            
            <div className={styles.summaryCard}>
              <div className={`${styles.iconWrapper} ${styles.info}`}>
                <Cpu size={24} />
              </div>
              <div className={styles.cardContent}>
                <span className={styles.cardLabel}>Active Markov Version</span>
                <span className={styles.cardValue}>{summary.active_versions.MARKOV?.version || "NONE"}</span>
              </div>
            </div>

            <div className={styles.summaryCard}>
              <div className={`${styles.iconWrapper} ${summary.recalibration.needs_recalibration ? styles.statusWarning : styles.statusStable}`}>
                <RefreshCw size={24} />
              </div>
              <div className={styles.cardContent}>
                <span className={styles.cardLabel}>Recalibration Status</span>
                <span className={styles.cardValue}>{summary.recalibration.needs_recalibration ? "NEEDED" : "UP-TO-DATE"}</span>
              </div>
            </div>

            <div className={styles.summaryCard}>
              <div className={`${styles.iconWrapper} ${styles.info}`}>
                <History size={24} />
              </div>
              <div className={styles.cardContent}>
                <span className={styles.cardLabel}>Events (Last 7D)</span>
                <span className={styles.cardValue}>
                  {Object.values(summary.recent_events_7d).reduce((a, b) => a + b, 0)}
                </span>
              </div>
            </div>
          </div>

          <div className={styles.mainGrid}>
            {/* Left Column: Drift Report & Timeline */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* Drift Monitoring Sub-panel */}
              {driftReport && (
                <div className={styles.sectionPanel}>
                  <h2 className={styles.panelTitle}>
                    <Activity size={20} className={styles.titleIcon} /> 
                    Quantitative Drift Monitoring (Last {driftReport.period_days} Days)
                  </h2>
                  
                  <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
                    <div style={{ flex: 1, padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>Avg Brier Score</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 600, color: (driftReport.summary.avg_brier || 0) > 0.35 ? '#ef4444' : '#10b981' }}>
                        {driftReport.summary.avg_brier ? driftReport.summary.avg_brier.toFixed(4) : "N/A"}
                      </div>
                    </div>
                    <div style={{ flex: 1, padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>Avg Log Loss</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 600, color: (driftReport.summary.avg_log_loss || 0) > 1.0 ? '#ef4444' : '#10b981' }}>
                        {driftReport.summary.avg_log_loss ? driftReport.summary.avg_log_loss.toFixed(4) : "N/A"}
                      </div>
                    </div>
                    <div style={{ flex: 1, padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>Degraded Days</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 600, color: driftReport.summary.degraded_days > 0 ? '#ef4444' : 'var(--text-main)' }}>
                        {driftReport.summary.degraded_days} / {driftReport.summary.total_records}
                      </div>
                    </div>
                  </div>

                  <div className={styles.tableWrapper}>
                    <table className={styles.table}>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Brier Score</th>
                          <th>Log Loss</th>
                          <th>Instability</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {driftReport.records.slice(0, 5).map((rec, i) => (
                          <tr key={i}>
                            <td>{rec.date}</td>
                            <td>{rec.brier_score?.toFixed(4) || "-"}</td>
                            <td>{rec.log_loss?.toFixed(4) || "-"}</td>
                            <td>{rec.probability_instability?.toFixed(4) || "-"}</td>
                            <td>
                              <span className={`${styles.badge} ${rec.drift_status === 'STABLE' ? styles.statusActive : rec.drift_status === 'WARNING' ? styles.statusWarning : styles.statusDegraded}`}>
                                {rec.drift_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                        {driftReport.records.length === 0 && (
                          <tr><td colSpan={5} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>No drift records found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Event Timeline */}
              <div className={styles.sectionPanel}>
                <h2 className={styles.panelTitle}>
                  <History size={20} className={styles.titleIcon} /> 
                  Immutable Audit Log
                </h2>
                <div className={styles.timeline}>
                  {events.map((ev) => (
                    <div key={ev.id} className={styles.timelineEvent}>
                      <div className={styles.eventIcon}>
                        {ev.event_type === 'VERSION_CHANGE' ? <Database size={16} /> :
                         ev.event_type === 'GP_OVERRIDE' ? <Shield size={16} /> :
                         ev.event_type === 'DEGRADATION' ? <AlertTriangle size={16} /> :
                         <History size={16} />}
                      </div>
                      <div className={styles.eventDetails}>
                        <div className={styles.eventHeader}>
                          <span className={styles.eventType}>{ev.event_type.replace('_', ' ')}: {ev.model_type}</span>
                          <span className={styles.eventTime}>{formatDate(ev.created_at)}</span>
                        </div>
                        <div className={styles.eventReason}>{ev.reason}</div>
                        <div className={styles.eventActor}>
                          By: {ev.actor} 
                          {ev.model_version && <span> • Ver: {ev.model_version}</span>}
                          {ev.new_status && <span> • Status: {ev.previous_status || 'NONE'} ➔ {ev.new_status}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                  {events.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>No governance events logged yet.</div>
                  )}
                </div>
              </div>
            </div>

            {/* Right Column: Actions */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* GP Override Form */}
              <div className={styles.sectionPanel} style={{ borderColor: 'var(--accent-purple)' }}>
                <h2 className={styles.panelTitle} style={{ color: 'var(--accent-purple)' }}>
                  <Shield size={20} /> 
                  Log GP Override
                </h2>
                <form onSubmit={handleGpOverride} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Target Model</label>
                    <select 
                      value={gpOverrideModel}
                      onChange={(e) => setGpOverrideModel(e.target.value)}
                      className={styles.selectInput}
                    >
                      <option value="MARKOV">MARKOV</option>
                      <option value="REGIME">REGIME</option>
                      <option value="MONTE_CARLO">MONTE_CARLO</option>
                      <option value="PORTFOLIO">PORTFOLIO</option>
                    </select>
                  </div>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Decision</label>
                    <select 
                      value={gpOverrideDecision}
                      onChange={(e) => setGpOverrideDecision(e.target.value)}
                      className={styles.selectInput}
                    >
                      <option value="APPROVED">APPROVED</option>
                      <option value="REJECTED">REJECTED</option>
                      <option value="OVERRIDE_DEPLOY">OVERRIDE DEPLOYMENT</option>
                    </select>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Justification / Reason (Required)</label>
                    <textarea 
                      value={gpOverrideReason}
                      onChange={(e) => setGpOverrideReason(e.target.value)}
                      placeholder="Explain the rationale for this override..."
                      rows={4}
                      style={{ padding: '10px', background: 'var(--bg-darker)', border: '1px solid var(--border-color)', color: 'var(--text-main)', borderRadius: '6px', fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                  
                  <button type="submit" disabled={isProcessing || !gpOverrideReason.trim()} className={styles.btnAction} style={{ justifyContent: 'center', background: 'rgba(179, 136, 255, 0.1)', color: 'var(--accent-purple)', borderColor: 'var(--accent-purple)' }}>
                    Record GP Decision
                  </button>
                </form>
              </div>

              {/* Recalibration Actions */}
              <div className={styles.sectionPanel}>
                <h2 className={styles.panelTitle}>
                  <RefreshCw size={20} className={styles.titleIcon} /> 
                  Recalibration
                </h2>
                
                {summary.recalibration.needs_recalibration ? (
                  <div style={{ padding: '12px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid #f59e0b', borderRadius: '8px', color: '#f59e0b', fontSize: '0.9rem', marginBottom: '16px' }}>
                    <AlertTriangle size={16} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'text-bottom' }} />
                    One or more models have exceeded their maximum age (45 days) and require recalibration.
                  </div>
                ) : (
                  <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid #10b981', borderRadius: '8px', color: '#10b981', fontSize: '0.9rem', marginBottom: '16px' }}>
                    <CheckCircle2 size={16} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'text-bottom' }} />
                    All models are up-to-date.
                  </div>
                )}
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <button className={styles.btnAction} onClick={() => handleRecalibrate('MARKOV')} disabled={isProcessing}>
                    Trigger MARKOV Recalibration
                  </button>
                  <button className={styles.btnAction} onClick={() => handleRecalibrate('MONTE_CARLO')} disabled={isProcessing}>
                    Trigger MONTE CARLO Recalibration
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === "versions" && (
        <div className={styles.sectionPanel}>
          <h2 className={styles.panelTitle}>
            <Database size={20} className={styles.titleIcon} /> 
            Model Version Registry
          </h2>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Model Type</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Promoted At</th>
                  <th>Retired At</th>
                  <th>Created At</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((ver) => (
                  <tr key={ver.id}>
                    <td style={{ fontWeight: 600 }}>{ver.model_type}</td>
                    <td>{ver.version}</td>
                    <td>
                      <span className={`${styles.badge} ${ver.status === 'ACTIVE' ? styles.statusActive : ver.status === 'SHADOW' ? styles.statusShadow : styles.statusDegraded}`}>
                        {ver.status}
                      </span>
                    </td>
                    <td>{formatDate(ver.promoted_at || "")}</td>
                    <td>{formatDate(ver.retired_at || "")}</td>
                    <td>{formatDate(ver.created_at)}</td>
                  </tr>
                ))}
                {versions.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>No versions registered yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
