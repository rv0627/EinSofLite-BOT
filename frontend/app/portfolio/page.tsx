'use client';

import styles from './page.module.css';
import { useEffect, useState } from 'react';
import { fetchPortfolioHoldings, PortfolioHolding, fetchPortfolioIntelligence, PortfolioIntelligence, downloadDailyPdfReport } from '@/lib/api';

export default function PortfolioPage() {
  const [portfolioData, setPortfolioData] = useState<PortfolioHolding[]>([]);
  const [intelData, setIntelData] = useState<PortfolioIntelligence[]>([]);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    fetchPortfolioHoldings().then(res => setPortfolioData(res.data)).catch(console.error);
    fetchPortfolioIntelligence().then(res => setIntelData(res.data)).catch(console.error);
  }, []);

  const itemsPerPage = 50;
  const totalItems = portfolioData.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const currentData = portfolioData.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  return (
    <div className={styles.page}>
      
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.titleArea}>
          <h1 className={styles.title}>System Tickers</h1>
          <p className={styles.subtitle}>Real-time list of tickers successfully processed by the system.</p>
        </div>
        <div className={styles.actionButtons}>
          <button 
            className={styles.btnNew} 
            onClick={async () => {
              try {
                await downloadDailyPdfReport();
              } catch (e) {
                alert('Failed to download PDF: ' + e);
              }
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '8px' }}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            Download Daily PDF
          </button>
        </div>
      </div>

      {/* ── Main Layout ── */}
      <div className={styles.mainArea}>
        
        {/* ── Left Column: Table ── */}
        <div className={styles.tableCard}>
          <div className={styles.cardHeader}>
            <div className={styles.cardTitle}>
              <svg className={styles.cardTitleIcon} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="9" y1="21" x2="9" y2="9"></line>
              </svg>
              System Tickers
            </div>
            <div className={styles.totalBadge}>{totalItems} TOTAL</div>
          </div>

          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Company Name</th>
                  <th>Current Price</th>
                  <th>24h Change</th>
                  <th>Last Sync</th>
                </tr>
              </thead>
              <tbody>
                {currentData.map((row, idx) => (
                  <tr key={idx}>
                    <td>
                      <div className={styles.tickerCell}>
                        <div className={styles.tickerAvatar} style={{ 
                            color: row.ticker === 'AAPL' || row.ticker === 'XOM' ? 'var(--accent-cyan)' : 
                                   row.ticker === 'TSLA' ? 'var(--accent-red)' : 
                                   row.ticker === 'MSFT' ? 'var(--accent-purple)' : 'var(--accent-green)',
                            borderColor: row.ticker === 'AAPL' || row.ticker === 'XOM' ? 'var(--accent-cyan-dim)' : 
                                        row.ticker === 'TSLA' ? 'var(--accent-red-dim)' : 
                                        row.ticker === 'MSFT' ? 'rgba(179, 136, 255, 0.2)' : 'rgba(0, 230, 118, 0.2)',
                        }}>
                          {row.ticker[0]}
                        </div>
                        <span className={styles.tickerSymbol}>{row.ticker}</span>
                      </div>
                    </td>
                    <td>
                      <div className={styles.companyName}>{row.name}</div>
                    </td>
                    <td>
                      <div className={styles.price}>{row.price}</div>
                    </td>
                    <td>
                      <div className={`${styles.changeCell} ${row.isPositive === true ? styles.positive : row.isPositive === false ? styles.negative : styles.neutral}`}>
                        {row.isPositive === true ? (
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>
                        ) : row.isPositive === false ? (
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"></polyline><polyline points="16 17 22 17 22 11"></polyline></svg>
                        ) : (
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                        )}
                        {row.change}
                      </div>
                    </td>
                    <td>
                      <div className={styles.syncTime}>
                        {row.sync.split(' ')[0]}
                        <span style={{fontSize: '0.65rem', opacity: 0.6}}>{row.sync.split(' ')[1] || ''}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.pagination}>
            <div className={styles.pageInfo}>Showing {currentData.length} of {totalItems} assets</div>
            {totalPages > 1 && (
              <div className={styles.pageControls}>
                <button 
                  className={styles.pageBtn} 
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                  style={{ opacity: currentPage === 1 ? 0.5 : 1, cursor: currentPage === 1 ? 'not-allowed' : 'pointer' }}
                >
                  &lt;
                </button>
                {(() => {
                  const pages = [];
                  const maxPagesToShow = 5;
                  let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
                  let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
                  if (endPage - startPage + 1 < maxPagesToShow) {
                    startPage = Math.max(1, endPage - maxPagesToShow + 1);
                  }
                  
                  if (startPage > 1) {
                    pages.push(
                      <button key={1} className={styles.pageBtn} onClick={() => setCurrentPage(1)}>1</button>
                    );
                    if (startPage > 2) pages.push(<span key="dots1" style={{color: 'var(--text-muted)', margin: '0 4px'}}>...</span>);
                  }
                  
                  for (let i = startPage; i <= endPage; i++) {
                    pages.push(
                      <button 
                        key={i}
                        className={`${styles.pageBtn} ${currentPage === i ? styles.active : ''}`}
                        onClick={() => setCurrentPage(i)}
                      >
                        {i}
                      </button>
                    );
                  }
                  
                  if (endPage < totalPages) {
                    if (endPage < totalPages - 1) pages.push(<span key="dots2" style={{color: 'var(--text-muted)', margin: '0 4px'}}>...</span>);
                    pages.push(
                      <button key={totalPages} className={styles.pageBtn} onClick={() => setCurrentPage(totalPages)}>{totalPages}</button>
                    );
                  }
                  
                  return pages;
                })()}
                <button 
                  className={styles.pageBtn} 
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                  style={{ opacity: currentPage === totalPages ? 0.5 : 1, cursor: currentPage === totalPages ? 'not-allowed' : 'pointer' }}
                >
                  &gt;
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── Right Column ── */}
        <div className={styles.rightPanel}>
          
          {/* Market Intelligence */}
          <div className={styles.intelligenceCard}>
            <div className={styles.intelHeader}>
              <svg className={styles.intelIcon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
              Market Intelligence
            </div>
            
            <div className={styles.intelList}>
              {intelData.length === 0 ? (
                <div className={styles.intelItem}>
                  <div className={styles.intelLabel}>Loading Intelligence...</div>
                  <div className={styles.intelDesc}>Analyzing system anomalies and signals.</div>
                </div>
              ) : (
                intelData.map((intel, idx) => (
                  <div key={idx} className={`${styles.intelItem} ${intel.type === 'bullish' ? styles.bullish : ''}`}>
                    <div className={styles.intelLabel}>{intel.label}</div>
                    <div className={styles.intelDesc}>{intel.desc}</div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
