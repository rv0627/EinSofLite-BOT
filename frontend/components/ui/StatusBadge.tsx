import styles from './StatusBadge.module.css';

type BadgeVariant = 'active' | 'standby' | 'offline' | 'idle' | 'processing';

interface StatusBadgeProps {
  status: BadgeVariant;
  label?: string;
}

const defaultLabels: Record<BadgeVariant, string> = {
  active: 'Active',
  standby: 'Standby',
  offline: 'Offline',
  idle: 'Idle',
  processing: 'Processing',
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[status]}`}>
      <span className={styles.dot} />
      {label || defaultLabels[status]}
    </span>
  );
}
