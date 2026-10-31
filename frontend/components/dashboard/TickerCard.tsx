import styles from './TickerCard.module.css';
import SparklineChart from '../ui/SparklineChart';

interface TickerCardProps {
  ticker: string;
  exchange: string;
  price: string;
  change: string;
  sparkData: number[];
  noData?: boolean;
}

export default function TickerCard({
  ticker,
  exchange,
  price,
  change,
  sparkData,
  noData = false,
}: TickerCardProps) {
  const isPositive = !change.startsWith('-');
  const color = isPositive ? 'var(--accent-green)' : 'var(--accent-red)';
  const currencySymbol = exchange === 'NASDAQ' ? '$' : '₹';

  return (
    <div className={`${styles.card} ${isPositive ? styles.positive : styles.negative} ${noData ? styles.noData : ''}`}>
      <div className={styles.info}>
        <div className={styles.ticker}>{ticker}</div>
        <div className={styles.exchange}>{exchange}</div>
      </div>
      <div className={styles.chartArea}>
        {sparkData.length >= 2 ? (
          <SparklineChart data={sparkData} color={color} width={70} height={30} />
        ) : (
          <div className={styles.noChart}>—</div>
        )}
      </div>
      <div className={styles.priceSection}>
        <div className={styles.price}>
          {noData ? 'No Data' : `${currencySymbol}${price}`}
        </div>
        <div className={`${styles.change} ${isPositive ? styles.positive : styles.negative}`}>
          {noData ? '' : change}
        </div>
      </div>
    </div>
  );
}
