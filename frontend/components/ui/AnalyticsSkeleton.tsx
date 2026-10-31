import Skeleton from './Skeleton';
import styles from '@/app/analytics/page.module.css';

export default function AnalyticsSkeleton() {
  return (
    <div className={styles.page}>
      {/* ── Stock Header Skeleton ── */}
      <div className={styles.stockHeader}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Skeleton width="200px" height="14px" />
          <Skeleton width="300px" height="32px" />
        </div>
        
        <div className={styles.priceGroup}>
          <div className={styles.priceCard}>
             <Skeleton width="70px" height="14px" />
             <Skeleton width="120px" height="28px" />
          </div>
          <div className={styles.priceCard}>
             <Skeleton width="80px" height="14px" />
             <Skeleton width="90px" height="28px" />
          </div>
        </div>
      </div>

      {/* ── Main Layout Skeleton ── */}
      <div className={styles.mainArea}>
        {/* Left Column */}
        <div className={styles.chartSection}>
          <div className={styles.chartContainer}>
             <Skeleton width="100%" height="40px" borderRadius="0" />
             <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
                 <Skeleton width="100%" height="100%" />
             </div>
          </div>

          <div className={styles.indicatorsRow}>
            <div className={styles.indicatorCard}>
               <Skeleton width="100%" height="120px" />
            </div>
            <div className={styles.indicatorCard}>
               <Skeleton width="100%" height="120px" />
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className={styles.rightPanel}>
          <div className={styles.dataQualityCard}>
            <Skeleton width="100%" height="200px" />
          </div>
          <div className={styles.eventCard}>
            <Skeleton width="100%" height="60px" />
          </div>
          <div className={styles.eventCard}>
            <Skeleton width="100%" height="60px" />
          </div>
          <div className={styles.sentimentCard}>
            <Skeleton width="100%" height="220px" />
          </div>
          <div className={styles.executionCard}>
             <Skeleton width="100%" height="140px" />
          </div>
        </div>
      </div>
    </div>
  );
}
