'use client';

import { useEffect, useState } from 'react';
import { fetchScoringRankings, triggerBot3Score, ScoringRanking, fetchTaskStatus } from '@/lib/api';
import styles from './page.module.css';

export default function EinScorePage() {
  const [rankings, setRankings] = useState<ScoringRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const response = await fetchScoringRankings(page, 50);
        setRankings(response.data || []);
        setTotalPages(response.total_pages || 1);
      } catch (error) {
        console.error('Failed to fetch rankings', error);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [page]);

  const handleTriggerBot = async () => {
    setIsTriggering(true);
    try {
      const result = await triggerBot3Score();
      
      if (!result.task_id || result.task_id === 'sync-task') {
        const response = await fetchScoringRankings(50);
        setRankings(response.data || []);
        setIsTriggering(false);
        return;
      }
      
      // Poll task status until complete or failed
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 2000));
        try {
          const status = await fetchTaskStatus(result.task_id);
          if (status.ready) {
            if (status.state === 'SUCCESS') {
              setPage(1); // Reset to first page
              const response = await fetchScoringRankings(1, 50);
              setRankings(response.data || []);
              setTotalPages(response.total_pages || 1);
            } else {
              console.error("Task failed:", status.error);
            }
            break;
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }
      
    } catch (error) {
      console.error('Failed to trigger bot', error);
    } finally {
      setIsTriggering(false);
    }
  };

  if (loading) {
    return <div className={styles.loading}>Initializing Scoring Engine...</div>;
  }

  // Helper function to color the EIN Score
  const getScoreColor = (score: number) => {
    if (score >= 80) return '#48bb78'; // Green
    if (score >= 60) return '#ecc94b'; // Yellow
    if (score >= 40) return '#ed8936'; // Orange
    return '#f56565'; // Red
  };

  // Helper function to color factor bars
  const getFactorColor = (val: number) => {
    if (val >= 70) return 'linear-gradient(90deg, #48bb78, #38a169)';
    if (val >= 40) return 'linear-gradient(90deg, #ecc94b, #d69e2e)';
    return 'linear-gradient(90deg, #f56565, #e53e3e)';
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.titleWrapper}>
          <h1 className={styles.title}>EIN Score Rankings</h1>
          <button 
            className={styles.triggerBtn} 
            onClick={handleTriggerBot}
            disabled={isTriggering}
          >
            {isTriggering ? 'Calculating...' : 'Run Scoring Engine'}
          </button>
        </div>
        <p className={styles.subtitle}>
          Our proprietary multi-factor model evaluates assets across Value, Dividend, Quality, Momentum, and Volatility. 
          The final EIN Score is confidence-weighted by our AI data engine for institutional-grade reliability.
        </p>
      </header>

      <div className={styles.leaderboard}>
        {rankings.map((item) => (
          <div 
            key={item.ticker} 
            className={`${styles.row} ${item.rank === 1 ? styles.rank1 : item.rank === 2 ? styles.rank2 : item.rank === 3 ? styles.rank3 : ''}`}
          >
            {/* Rank */}
            <div className={styles.rankCol}>
              #{item.rank}
            </div>

            {/* Symbol */}
            <div className={styles.symbolCol}>
              <span className={styles.ticker}>{item.ticker}</span>
              <span className={styles.companyName}>{item.company_name || '—'}</span>
            </div>

            {/* Factors Breakdown */}
            <div className={styles.factorsCol}>
              {[
                { label: 'VAL', val: item.factors.value },
                { label: 'DIV', val: item.factors.dividend },
                { label: 'QLT', val: item.factors.quality },
                { label: 'MOM', val: item.factors.momentum },
                { label: 'VOL', val: item.factors.volatility },
              ].map((factor) => (
                <div key={factor.label} className={styles.factorItem}>
                  <span className={styles.factorLabel}>{factor.label}</span>
                  <div className={styles.factorBarWrap}>
                    <div 
                      className={styles.factorBar} 
                      style={{ 
                        width: `${Math.max(0, Math.min(100, factor.val))}%`,
                        background: getFactorColor(factor.val)
                      }} 
                    />
                  </div>
                  <span className={styles.factorValue}>{Math.round(factor.val)}</span>
                </div>
              ))}
            </div>

            {/* Overall Score */}
            <div className={styles.scoreCol}>
              <span className={styles.scoreValue} style={{ color: getScoreColor(item.confidence_weight * 100) }}>
                {(item.confidence_weight * 100).toFixed(0)}%
              </span>
              <span className={styles.scoreLabel}>Data Confidence</span>
              <span className={styles.confidence} style={{ marginTop: '4px', fontSize: '1rem', color: 'var(--text-muted)' }}>
                ★ {item.ein_score.toFixed(1)} EIN Score
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination Controls */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '2rem', paddingBottom: '2rem' }}>
        <button 
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1 || loading}
          style={{ padding: '0.5rem 1rem', background: 'var(--surface-light)', color: 'var(--text-main)', border: '1px solid var(--border)', borderRadius: '4px', cursor: (page === 1 || loading) ? 'not-allowed' : 'pointer', opacity: (page === 1 || loading) ? 0.5 : 1 }}
        >
          Previous
        </button>
        <span style={{ color: 'var(--text-muted)' }}>Page {page} of {totalPages}</span>
        <button 
          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages || loading}
          style={{ padding: '0.5rem 1rem', background: 'var(--surface-light)', color: 'var(--text-main)', border: '1px solid var(--border)', borderRadius: '4px', cursor: (page >= totalPages || loading) ? 'not-allowed' : 'pointer', opacity: (page >= totalPages || loading) ? 0.5 : 1 }}
        >
          Next
        </button>
      </div>
    </div>
  );
}
