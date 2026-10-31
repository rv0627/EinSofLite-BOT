"use client";

import { useState, useEffect } from "react";
import styles from "./page.module.css";
import {
  Bot3Config,
  fetchBot3Settings,
  updateBot3Settings,
  flushRedisCache,
  fetchCacheHealth,
  CacheHealth,
  ApiKeysConfig,
  ApiKeysUpdatePayload,
  fetchApiKeys,
  updateApiKeys,
  InternalConfig,
  fetchInternalConfig,
  updateInternalConfig,
  Bot4Config,
  fetchBot4Settings,
  updateBot4Settings,
  triggerBot4Allocate,
  triggerBot5Top20,
  fetchTaskStatus
} from "@/lib/api";

function PasswordInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className={styles.inputWrapper}>
      <input
        type={show ? "text" : "password"}
        className={styles.input}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ color: "var(--text-primary)", paddingRight: "40px" }}
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        style={{
          position: "absolute",
          right: "12px",
          top: "50%",
          transform: "translateY(-50%)",
          background: "none",
          border: "none",
          color: "var(--text-secondary)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 0,
        }}
      >
        {show ? (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
            <line x1="1" y1="1" x2="23" y2="23"></line>
          </svg>
        ) : (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
        )}
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [bot3Config, setBot3Config] = useState<Bot3Config | null>(null);
  const [cacheHealth, setCacheHealth] = useState<CacheHealth | null>(null);
  const [apiKeysStatus, setApiKeysStatus] = useState<ApiKeysConfig>({});
  const [newApiKeys, setNewApiKeys] = useState<ApiKeysUpdatePayload>({
    twelveData: "",
    eodhd: "",
    alphaVantage: "",
    marketstack: "",
    zerodhaApiKey: "",
    zerodhaAccessToken: "",
    upstoxAccessToken: "",
    nsebseApiKey: "",
  });
  const [isSavingKeys, setIsSavingKeys] = useState(false);
  const [saveKeysMessage, setSaveKeysMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [isFlushing, setIsFlushing] = useState(false);
  const [flushMessage, setFlushMessage] = useState("");
  const [internalConfig, setInternalConfig] = useState<InternalConfig>({
    schedulerEnabled: true,
    rateLimitReqs: 50,
  });
  const [isSavingInternal, setIsSavingInternal] = useState(false);
  const [saveInternalMessage, setSaveInternalMessage] = useState("");

  const [bot4Config, setBot4Config] = useState<Bot4Config | null>(null);
  const [isSavingBot4, setIsSavingBot4] = useState(false);
  const [saveBot4Message, setSaveBot4Message] = useState("");
  const [isTriggering, setIsTriggering] = useState(false);

  const loadCacheHealth = () => {
    fetchCacheHealth().then(setCacheHealth).catch(console.error);
  };

  useEffect(() => {
    fetchBot3Settings().then(setBot3Config).catch(console.error);
    fetchBot4Settings().then(setBot4Config).catch(console.error);
    fetchApiKeys()
      .then((keys) => setApiKeysStatus(keys))
      .catch(console.error);
    fetchInternalConfig()
      .then((config) => setInternalConfig(config))
      .catch(console.error);
    loadCacheHealth();
  }, []);

  const handleSaveApiKeys = async () => {
    setIsSavingKeys(true);
    setSaveKeysMessage("");
    try {
      // Only send keys that the user has actually typed a new value for
      const payload: ApiKeysUpdatePayload = {};
      for (const [key, value] of Object.entries(newApiKeys)) {
        if (value && (value as string).length > 0) {
          (payload as Record<string, string>)[key] = value as string;
        }
      }
      await updateApiKeys(payload);
      setSaveKeysMessage("API Keys saved successfully!");
      // Refresh masked status from server
      fetchApiKeys().then((keys) => setApiKeysStatus(keys)).catch(console.error);
      // Clear the input fields
      setNewApiKeys({
        twelveData: "", eodhd: "", alphaVantage: "", marketstack: "",
        zerodhaApiKey: "", zerodhaAccessToken: "", upstoxAccessToken: "", nsebseApiKey: "",
      });
      setTimeout(() => setSaveKeysMessage(""), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save API Keys.";
      setSaveKeysMessage(msg);
    } finally {
      setIsSavingKeys(false);
    }
  };

  const handleWeightChange = (
    key: keyof Bot3Config["weights"],
    value: number,
  ) => {
    if (!bot3Config) return;
    setBot3Config({
      ...bot3Config,
      weights: { ...bot3Config.weights, [key]: value },
    });
  };

  const handleSaveInternal = async () => {
    setIsSavingInternal(true);
    setSaveInternalMessage("");
    try {
      await updateInternalConfig(internalConfig);
      setSaveInternalMessage("Internal Config Saved!");
      setTimeout(() => setSaveInternalMessage(""), 3000);
    } catch (err) {
      console.error(err);
      setSaveInternalMessage("Failed to save.");
    } finally {
      setIsSavingInternal(false);
    }
  };

  const handleSaveBot3Config = async () => {
    if (!bot3Config) return;
    setIsSaving(true);
    setSaveMessage("");
    try {
      await updateBot3Settings(bot3Config);
      setSaveMessage("Settings saved successfully!");
      setTimeout(() => setSaveMessage(""), 3000);
    } catch (e) {
      setSaveMessage("Failed to save settings.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveBot4Config = async () => {
    if (!bot4Config) return;
    setIsSavingBot4(true);
    setSaveBot4Message("");
    try {
      await updateBot4Settings(bot4Config);
      setSaveBot4Message("Settings saved successfully!");
      setTimeout(() => setSaveBot4Message(""), 3000);
    } catch (e) {
      setSaveBot4Message("Failed to save settings.");
    } finally {
      setIsSavingBot4(false);
    }
  };

  const pollTask = async (taskId: string): Promise<string> => {
    if (!taskId || taskId === 'sync-task' || taskId === 'failed') return 'Completed';
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const status = await fetchTaskStatus(taskId);
        if (status.ready) {
          if (status.state === 'SUCCESS') return status.result || 'Completed successfully';
          throw new Error(status.error || 'Task failed');
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }
    throw new Error('Task timed out after 2 minutes');
  };

  const handleTriggerBot = async (botId: number) => {
    setIsTriggering(true);
    try {
      if (botId === 4) {
        const result = await triggerBot4Allocate();
        const finalMsg = await pollTask(result.task_id);
        alert(finalMsg);
      } else if (botId === 5) {
        const result = await triggerBot5Top20();
        const finalMsg = await pollTask(result.task_id);
        alert(finalMsg);
      }
    } catch (e: any) {
      alert(`Failed to trigger Bot ${botId}: ${e.message || 'Unknown error'}`);
    } finally {
      setIsTriggering(false);
    }
  };

  const handleFlushCache = async () => {
    setIsFlushing(true);
    setFlushMessage("");
    try {
      await flushRedisCache();
      setFlushMessage("Cache flushed successfully!");
      setTimeout(() => setFlushMessage(""), 3000);
      loadCacheHealth();
    } catch (e) {
      setFlushMessage("Failed to flush cache.");
      setTimeout(() => setFlushMessage(""), 3000);
    } finally {
      setIsFlushing(false);
    }
  };

  return (
    <div className={styles.page}>
      {/* ── Header ── */}
      <div className={styles.header}>
        <h1 className={styles.title}>System Configuration</h1>
        <p className={styles.subtitle}>
          Manage your institutional data feeds, automated trading schedules, and
          performance caching layers from one centralized interface.
        </p>
      </div>

      {/* ── Main Layout ── */}
      <div className={styles.mainArea}>
        {/* ── Left Column ── */}
        <div className={styles.column}>
          {/* API Configuration Card */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                  <circle cx="12" cy="14" r="3"></circle>
                  <path d="M12 11v-2"></path>
                  <path d="M12 19v-2"></path>
                  <path d="M15 14h2"></path>
                  <path d="M7 14h2"></path>
                </svg>
              </div>
              <div className={styles.cardTitleArea}>
                <h2 className={styles.cardTitle}>API Configuration</h2>
                <span className={styles.cardSubtitle}>
                  Connect high-frequency market data providers
                </span>
              </div>
            </div>

            <div className={styles.rowGrid}>
              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    Twelve Data {apiKeysStatus.twelveData?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.twelveData?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.twelveData.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.twelveData || ""}
                  onChange={(v) => setNewApiKeys({ ...newApiKeys, twelveData: v })}
                  placeholder={apiKeysStatus.twelveData?.configured ? "Enter new key to replace" : "Enter API Key"}
                />
              </div>

              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    EODHD APIs {apiKeysStatus.eodhd?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.eodhd?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.eodhd.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.eodhd || ""}
                  onChange={(v) => setNewApiKeys({ ...newApiKeys, eodhd: v })}
                  placeholder={apiKeysStatus.eodhd?.configured ? "Enter new key to replace" : "Enter API Key"}
                />
              </div>
            </div>

            <div className={styles.rowGrid} style={{ marginTop: "24px" }}>
              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    Marketstack {apiKeysStatus.marketstack?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.marketstack?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.marketstack.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.marketstack || ""}
                  onChange={(v) => setNewApiKeys({ ...newApiKeys, marketstack: v })}
                  placeholder={apiKeysStatus.marketstack?.configured ? "Enter new key to replace" : "Enter API Key"}
                />
              </div>
            </div>

            <div className={styles.rowGrid} style={{ marginTop: "24px" }}>
              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    Zerodha API Key {apiKeysStatus.zerodhaApiKey?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.zerodhaApiKey?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.zerodhaApiKey.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.zerodhaApiKey || ""}
                  onChange={(v) => setNewApiKeys({ ...newApiKeys, zerodhaApiKey: v })}
                  placeholder={apiKeysStatus.zerodhaApiKey?.configured ? "Enter new key to replace" : "Enter API Key"}
                />
              </div>

              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    Zerodha Access Token {apiKeysStatus.zerodhaAccessToken?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.zerodhaAccessToken?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.zerodhaAccessToken.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.zerodhaAccessToken || ""}
                  onChange={(v) =>
                    setNewApiKeys({ ...newApiKeys, zerodhaAccessToken: v })
                  }
                  placeholder={apiKeysStatus.zerodhaAccessToken?.configured ? "Enter new token to replace" : "Enter Access Token"}
                />
              </div>
            </div>

            <div className={styles.rowGrid} style={{ marginTop: "24px" }}>
              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    Upstox Access Token {apiKeysStatus.upstoxAccessToken?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.upstoxAccessToken?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.upstoxAccessToken.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.upstoxAccessToken || ""}
                  onChange={(v) =>
                    setNewApiKeys({ ...newApiKeys, upstoxAccessToken: v })
                  }
                  placeholder={apiKeysStatus.upstoxAccessToken?.configured ? "Enter new token to replace" : "Enter Access Token"}
                />
              </div>

              <div className={styles.formGroup} style={{ marginBottom: 0 }}>
                <div className={styles.labelRow}>
                  <div className={styles.labelTitle}>
                    NSE/BSE API Key {apiKeysStatus.nsebseApiKey?.configured && <span className={styles.statusDot} style={{ background: '#22c55e' }} title="Configured" />}
                    {apiKeysStatus.nsebseApiKey?.masked && <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px', fontFamily: 'monospace' }}>{apiKeysStatus.nsebseApiKey.masked}</span>}
                  </div>
                </div>
                <PasswordInput
                  value={newApiKeys.nsebseApiKey || ""}
                  onChange={(v) => setNewApiKeys({ ...newApiKeys, nsebseApiKey: v })}
                  placeholder={apiKeysStatus.nsebseApiKey?.configured ? "Enter new key to replace" : "Enter API Key"}
                />
              </div>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                gap: "16px",
                marginTop: "24px",
              }}
            >
              {saveKeysMessage && (
                <span className={styles.saveMessage}>{saveKeysMessage}</span>
              )}
              <button
                className={styles.btnSave}
                onClick={handleSaveApiKeys}
                disabled={isSavingKeys}
                style={{ marginTop: 0 }}
              >
                {isSavingKeys ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "24px",
            }}
          >
            {/* Cache Management Card */}
            <div className={`${styles.card} ${styles.cacheCard}`}>
              <div className={styles.cardHeader}>
                <div className={styles.cardIcon}>
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                  </svg>
                </div>
                <div className={styles.cardTitleArea}>
                  <h2 className={styles.cardTitle}>Cache Management</h2>
                  <span className={styles.cardSubtitle}>
                    {" "}
                    Flushing the cache will invalidate all active data sessions
                    and force a cold-reload from data providers.
                  </span>
                </div>
              </div>

              <div className={styles.redisHealth}>
                {/* <span className={styles.healthLabel}>REDIS HEALTH</span> */}
                <div className={styles.healthValue}>
                  <span
                    className={styles.statusDot}
                    style={{
                      width: "6px",
                      height: "6px",
                      boxShadow: "none",
                      backgroundColor:
                        cacheHealth?.status === "healthy" ? "#00e676" : "red",
                    }}
                  ></span>
                  {cacheHealth
                    ? `${cacheHealth.used_mb < 1024 ? `${cacheHealth.used_mb.toFixed(2)} MB` : `${(cacheHealth.used_mb / 1024).toFixed(2)} GB`} / ${cacheHealth.total_gb} GB`
                    : "Loading..."}
                </div>
              </div>
              <button
                className={styles.btnFlush}
                style={{ marginTop: "20px" }}
                onClick={handleFlushCache}
                disabled={isFlushing}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2-2v2"></path>
                </svg>
                {isFlushing ? "Flushing..." : "Flush Cache"}
              </button>
              {flushMessage && (
                <div
                  style={{
                    color: "#fff",
                    marginTop: "12px",
                    fontSize: "0.9rem",
                    textAlign: "center",
                  }}
                >
                  {flushMessage}
                </div>
              )}
            </div>

            {/* Bot Control Card */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.cardIcon}>
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 8V4H8"></path>
                    <rect
                      x="4"
                      y="8"
                      width="16"
                      height="12"
                      rx="2"
                      ry="2"
                    ></rect>
                    <path d="M2 14h2"></path>
                    <path d="M20 14h2"></path>
                    <path d="M15 13v2"></path>
                    <path d="M9 13v2"></path>
                  </svg>
                </div>
                <div className={styles.cardTitleArea}>
                  <h2 className={styles.cardTitle}>BOT Control</h2>
                  <span className={styles.cardSubtitle}>
                    Automated execution units
                  </span>
                </div>
              </div>

              <div className={styles.controlRow}>
                <div className={styles.controlLabelArea}>
                  <div className={styles.controlTitle}>Interval</div>
                  <div className={styles.controlDesc}>
                    Manage recurring task intervals
                  </div>
                </div>
                <div
                  className={styles.toggleSwitch}
                  onClick={() =>
                    setInternalConfig({
                      ...internalConfig,
                      schedulerEnabled: !internalConfig.schedulerEnabled,
                    })
                  }
                  style={{
                    background: internalConfig.schedulerEnabled
                      ? "var(--accent-cyan-dim)"
                      : "var(--bg-lighter)",
                  }}
                >
                  <div
                    className={styles.toggleKnob}
                    style={{
                      transform: internalConfig.schedulerEnabled
                        ? "translateX(20px)"
                        : "translateX(0px)",
                      transition: "transform 0.2s",
                    }}
                  ></div>
                </div>
              </div>

              <div className={styles.sliderGroup}>
                <div className={styles.sliderHeader}>
                  <div className={styles.sliderTitle}>Rate Limiting</div>
                  <div className={styles.sliderValue}>
                    {internalConfig.rateLimitReqs} req/s
                  </div>
                </div>
                <div className={styles.sliderTrack}>
                  <div
                    className={styles.sliderFill}
                    style={{
                      width: `${(internalConfig.rateLimitReqs / 200) * 100}%`,
                    }}
                  ></div>
                  <div
                    className={styles.sliderThumb}
                    style={{
                      left: `${(internalConfig.rateLimitReqs / 200) * 100}%`,
                    }}
                  ></div>
                  <input
                    type="range"
                    min="1"
                    max="200"
                    value={internalConfig.rateLimitReqs}
                    onChange={(e) =>
                      setInternalConfig({
                        ...internalConfig,
                        rateLimitReqs: parseInt(e.target.value),
                      })
                    }
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      opacity: 0,
                      cursor: "pointer",
                      margin: 0,
                    }}
                  />
                </div>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  gap: "16px",
                  marginTop: "16px",
                }}
              >
                {saveInternalMessage && (
                  <span className={styles.saveMessage}>
                    {saveInternalMessage}
                  </span>
                )}
                <button
                  className={styles.btnSave}
                  onClick={handleSaveInternal}
                  disabled={isSavingInternal}
                  style={{ marginTop: 0 }}
                >
                  {isSavingInternal ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ── Right Column ── */}
        <div className={styles.column}>
          {/* Bot 3 Configuration Card */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#FFD700"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
              </div>
              <div className={styles.cardTitleArea}>
                <h2 className={styles.cardTitle}>Bot 3 — Scoring Engine</h2>
                <span className={styles.cardSubtitle}>
                  Configure schedule & factor weights
                </span>
              </div>
            </div>

            {bot3Config ? (
              <>
                <div className={styles.controlRowBlock}>
                  <div className={styles.controlTitle}>Run Schedule</div>
                  <select
                    className={styles.selectInputWide}
                    value={bot3Config.schedule}
                    onChange={(e) =>
                      setBot3Config({
                        ...bot3Config,
                        schedule: e.target.value as "daily" | "weekly",
                      })
                    }
                  >
                    <option value="daily">
                      Daily — Every day at 6:00 PM IST
                    </option>
                    <option value="weekly">
                      Weekly — Every Friday at 6:00 PM IST
                    </option>
                  </select>
                </div>

                <div className={styles.sectionDividerRow}>
                  <div className={styles.sectionDividerText}>
                    Factor Weights
                  </div>
                  <div className={styles.sectionDividerTotal}>
                    TOTAL:{" "}
                    <span>
                      {Object.values(bot3Config.weights).reduce(
                        (a, b) => a + b,
                        0,
                      )}
                      %
                    </span>
                  </div>
                </div>

                {Object.entries(bot3Config.weights).map(([key, value]) => (
                  <div key={key} className={styles.sliderGroupHorizontal}>
                    <div
                      className={styles.sliderLabel}
                      style={{ textTransform: "capitalize" }}
                    >
                      {key}
                    </div>
                    <div className={styles.sliderTrackContainer}>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={value}
                        onChange={(e) =>
                          handleWeightChange(
                            key as keyof Bot3Config["weights"],
                            parseInt(e.target.value),
                          )
                        }
                        className={styles.rangeInput}
                        style={{ "--val": `${value}%` } as any}
                      />
                    </div>
                    <div className={styles.sliderInputArea}>
                      <input
                        type="number"
                        className={styles.weightNumberInput}
                        value={value}
                        onChange={(e) =>
                          handleWeightChange(
                            key as keyof Bot3Config["weights"],
                            parseInt(e.target.value) || 0,
                          )
                        }
                      />
                      <span className={styles.weightPercentSign}>%</span>
                    </div>
                  </div>
                ))}

                <div className={styles.actionRowFull}>
                  {saveMessage && (
                    <span className={styles.saveMessage}>{saveMessage}</span>
                  )}
                  <button
                    className={styles.btnSaveFull}
                    onClick={handleSaveBot3Config}
                    disabled={isSaving}
                  >
                    {isSaving ? "Saving..." : "Save Bot 3 Settings"}
                  </button>
                </div>
              </>
            ) : (
              <div className={styles.loadingState}>
                Loading configuration...
              </div>
            )}
          </div>

          {/* Bot 4 Configuration Card */}
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <line x1="3" y1="9" x2="21" y2="9"></line>
                  <line x1="9" y1="21" x2="9" y2="9"></line>
                </svg>
              </div>
              <div className={styles.cardTitleArea}>
                <h2 className={styles.cardTitle}>Bot 4: Risk & Allocation</h2>
                <span className={styles.cardSubtitle}>
                  Portfolio sizing and risk constraints
                </span>
              </div>
            </div>

            {bot4Config ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "1rem",
                }}
              >
                <div className={styles.sliderGroupHorizontal}>
                  <div className={styles.sliderLabel}>Total Capital (₹)</div>
                  <div className={styles.sliderTrackContainer}>
                    <input
                      type="number"
                      className={styles.input}
                      value={bot4Config.total_capital}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          total_capital: parseInt(e.target.value) || 0,
                        })
                      }
                    />
                  </div>
                </div>

                <div className={styles.sliderGroupHorizontal}>
                  <div className={styles.sliderLabel}>Max Position %</div>
                  <div className={styles.sliderTrackContainer}>
                    <input
                      type="range"
                      min="1"
                      max="50"
                      value={bot4Config.max_position_pct}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          max_position_pct: parseInt(e.target.value),
                        })
                      }
                      className={styles.rangeInput}
                      style={
                        { "--val": `${bot4Config.max_position_pct}%` } as any
                      }
                    />
                  </div>
                  <div className={styles.sliderInputArea}>
                    <input
                      type="number"
                      className={styles.weightNumberInput}
                      value={bot4Config.max_position_pct}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          max_position_pct: parseInt(e.target.value) || 0,
                        })
                      }
                    />
                    <span className={styles.weightPercentSign}>%</span>
                  </div>
                </div>

                <div className={styles.sliderGroupHorizontal}>
                  <div className={styles.sliderLabel}>Max Sector %</div>
                  <div className={styles.sliderTrackContainer}>
                    <input
                      type="range"
                      min="10"
                      max="100"
                      value={bot4Config.max_sector_pct}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          max_sector_pct: parseInt(e.target.value),
                        })
                      }
                      className={styles.rangeInput}
                      style={
                        { "--val": `${bot4Config.max_sector_pct}%` } as any
                      }
                    />
                  </div>
                  <div className={styles.sliderInputArea}>
                    <input
                      type="number"
                      className={styles.weightNumberInput}
                      value={bot4Config.max_sector_pct}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          max_sector_pct: parseInt(e.target.value) || 0,
                        })
                      }
                    />
                    <span className={styles.weightPercentSign}>%</span>
                  </div>
                </div>

                <div className={styles.sliderGroupHorizontal}>
                  <div className={styles.sliderLabel}>Min Confidence</div>
                  <div className={styles.sliderTrackContainer}>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={bot4Config.min_confidence}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          min_confidence: parseInt(e.target.value),
                        })
                      }
                      className={styles.rangeInput}
                      style={
                        { "--val": `${bot4Config.min_confidence}%` } as any
                      }
                    />
                  </div>
                  <div className={styles.sliderInputArea}>
                    <input
                      type="number"
                      className={styles.weightNumberInput}
                      value={bot4Config.min_confidence}
                      onChange={(e) =>
                        setBot4Config({
                          ...bot4Config,
                          min_confidence: parseInt(e.target.value) || 0,
                        })
                      }
                    />
                    <span className={styles.weightPercentSign}>%</span>
                  </div>
                </div>

                <div
                  className={styles.actionRowFull}
                  style={{ marginTop: "1rem" }}
                >
                  {saveBot4Message && (
                    <span className={styles.saveMessage}>
                      {saveBot4Message}
                    </span>
                  )}
                  <button
                    className={styles.btnSaveFull}
                    onClick={handleSaveBot4Config}
                    disabled={isSavingBot4}
                  >
                    {isSavingBot4 ? "Saving..." : "Save Bot 4 Settings"}
                  </button>
                </div>
              </div>
            ) : (
              <div className={styles.loadingState}>
                Loading configuration...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
