import styles from './MetricCard.module.css';

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  color?: 'cyan' | 'green';
  progressPercent?: number;
  showDots?: boolean;
  isLoading?: boolean;
}

export default function MetricCard({
  label,
  value,
  unit,
  color = 'cyan',
  progressPercent,
  showDots = false,
  isLoading = false,
}: MetricCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.label}>{label}</div>
      <div className={`${styles.value} ${styles[color]} ${isLoading ? styles.loading : ''}`}>
        {value}
      </div>
      {unit && <div className={styles.unit}>{unit}</div>}
      {showDots && (
        <div className={styles.dots}>
          <span className={styles.dot} />
          <span className={styles.dot} />
          <span className={styles.dot} />
        </div>
      )}
      {progressPercent !== undefined && (
        <div
          className={styles.progressBar}
          style={{ width: `${progressPercent}%` }}
        />
      )}
    </div>
  );
}

