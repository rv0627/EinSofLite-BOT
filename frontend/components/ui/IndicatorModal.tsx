'use client';

import { useState } from 'react';
import styles from './IndicatorModal.module.css';
import type { IndicatorConfig, IndicatorType, MAConfig } from '@/lib/indicators';
import { DEFAULT_INDICATORS, DEFAULT_MA_CONFIG } from '@/lib/indicators';

interface IndicatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  indicators: IndicatorConfig[];
  maConfig: MAConfig;
  onSave: (indicators: IndicatorConfig[], maConfig: MAConfig) => void;
}

const PARAM_LABELS: Record<string, string> = {
  period: 'Period',
  fast: 'Fast',
  slow: 'Slow',
  signal: 'Signal',
  k: 'K',
  d: 'D',
  j: 'J',
};

const INDICATOR_NAMES: Record<IndicatorType, string> = {
  VOL: 'Volume',
  MACD: 'MACD',
  RSI: 'RSI – Relative Strength Index',
  MFI: 'MFI – Money Flow Index',
  KDJ: 'KDJ – Stochastic Oscillator',
  OBV: 'OBV – On Balance Volume',
  CCI: 'CCI – Commodity Channel Index',
  StochRSI: 'Stochastic RSI',
  WR: 'WR – Williams %R',
};

export default function IndicatorModal({ isOpen, onClose, indicators, maConfig, onSave }: IndicatorModalProps) {
  const [activeTab, setActiveTab] = useState<'main' | 'sub'>('sub');
  const [localIndicators, setLocalIndicators] = useState<IndicatorConfig[]>([...indicators]);
  const [localMA, setLocalMA] = useState<MAConfig>(JSON.parse(JSON.stringify(maConfig)));
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!isOpen) return null;

  const toggleIndicator = (type: IndicatorType) => {
    setLocalIndicators(prev =>
      prev.map(ind => ind.type === type ? { ...ind, enabled: !ind.enabled } : ind)
    );
  };

  const updateParam = (type: IndicatorType, key: string, value: number) => {
    setLocalIndicators(prev =>
      prev.map(ind =>
        ind.type === type ? { ...ind, params: { ...ind.params, [key]: value } } : ind
      )
    );
  };

  const toggleMA = (index: number) => {
    setLocalMA(prev => {
      const updated = { ...prev, periods: [...prev.periods] };
      updated.periods[index] = { ...updated.periods[index], enabled: !updated.periods[index].enabled };
      return updated;
    });
  };

  const updateMAPeriod = (index: number, period: number) => {
    setLocalMA(prev => {
      const updated = { ...prev, periods: [...prev.periods] };
      updated.periods[index] = { ...updated.periods[index], period };
      return updated;
    });
  };

  const handleReset = () => {
    setLocalIndicators([...DEFAULT_INDICATORS]);
    setLocalMA(JSON.parse(JSON.stringify(DEFAULT_MA_CONFIG)));
  };

  const handleSave = () => {
    onSave(localIndicators, localMA);
    onClose();
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.tabs}>
            <button
              className={`${styles.tab} ${activeTab === 'main' ? styles.active : ''}`}
              onClick={() => setActiveTab('main')}
            >
              Main Indicator
            </button>
            <button
              className={`${styles.tab} ${activeTab === 'sub' ? styles.active : ''}`}
              onClick={() => setActiveTab('sub')}
            >
              Sub Indicator
            </button>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {activeTab === 'main' ? (
            <>
              <div className={styles.sectionTitle}>Moving Averages</div>
              {localMA.periods.map((ma, i) => (
                <div key={i} className={styles.maRow}>
                  <div
                    className={`${styles.checkbox} ${ma.enabled ? styles.checked : ''}`}
                    onClick={() => toggleMA(i)}
                  >
                    {ma.enabled && <span className={styles.checkmark}>✓</span>}
                  </div>
                  <span className={styles.maLabel}>MA</span>
                  <input
                    type="number"
                    className={styles.maPeriodInput}
                    value={ma.period}
                    onChange={e => updateMAPeriod(i, parseInt(e.target.value) || 1)}
                    min={1}
                    max={200}
                  />
                  <div className={styles.colorDot} style={{ background: ma.color }} />
                </div>
              ))}
            </>
          ) : (
            <>
              <div className={styles.sectionTitle}>Sub Indicators</div>
              {localIndicators.map((ind) => (
                <div key={ind.type}>
                  <div className={styles.indicatorRow}>
                    <div className={styles.indicatorLeft}>
                      <div
                        className={`${styles.checkbox} ${ind.enabled ? styles.checked : ''}`}
                        onClick={() => toggleIndicator(ind.type)}
                      >
                        {ind.enabled && <span className={styles.checkmark}>✓</span>}
                      </div>
                      <span className={styles.indicatorLabel}>{ind.type}</span>
                    </div>
                    {Object.keys(ind.params).length > 0 && (
                      <button
                        className={styles.expandBtn}
                        onClick={() => setExpanded(expanded === ind.type ? null : ind.type)}
                      >
                        {INDICATOR_NAMES[ind.type]}
                        <span style={{ transform: expanded === ind.type ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', display: 'inline-block' }}>›</span>
                      </button>
                    )}
                  </div>
                  {expanded === ind.type && Object.keys(ind.params).length > 0 && (
                    <div className={styles.paramPanel}>
                      {Object.entries(ind.params).map(([key, value]) => (
                        <div key={key} className={styles.paramRow}>
                          <span className={styles.paramLabel}>{PARAM_LABELS[key] || key}</span>
                          <input
                            type="number"
                            className={styles.paramInput}
                            value={value}
                            onChange={e => updateParam(ind.type, key, parseInt(e.target.value) || 1)}
                            min={1}
                            max={200}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button className={styles.resetBtn} onClick={handleReset}>Reset</button>
          <button className={styles.saveBtn} onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  );
}
