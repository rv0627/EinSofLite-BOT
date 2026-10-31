import styles from './Skeleton.module.css';

interface SkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
}

export default function Skeleton({
  width = '100%',
  height = '20px',
  borderRadius = 'var(--radius-sm)',
  className = '',
}: SkeletonProps) {
  return (
    <div
      className={`${styles.skeleton} ${className}`}
      style={{ width, height, borderRadius }}
    />
  );
}

/** Pre-built skeleton for a TickerCard */
export function TickerCardSkeleton() {
  return (
    <div className={styles.tickerSkeleton}>
      <div className={styles.tickerSkeletonLeft}>
        <Skeleton width="80px" height="14px" />
        <Skeleton width="60px" height="10px" />
      </div>
      <Skeleton width="70px" height="30px" />
      <div className={styles.tickerSkeletonRight}>
        <Skeleton width="90px" height="18px" />
        <Skeleton width="50px" height="12px" />
      </div>
    </div>
  );
}

/** Pre-built skeleton for a MetricCard */
export function MetricCardSkeleton() {
  return (
    <div className={styles.metricSkeleton}>
      <Skeleton width="90px" height="10px" />
      <Skeleton width="60px" height="28px" />
    </div>
  );
}
