'use client';

import styles from './ApiHealthMap.module.css';
import StatusBadge from '../ui/StatusBadge';
import type { ApiSource } from '@/lib/api';
import { Server } from 'lucide-react';

interface ApiHealthMapProps {
  sources: ApiSource[];
  gatewayOnline: boolean;
  isLoading: boolean;
}

function SourceNode({ source }: { source: ApiSource }) {
  return (
    <div className={styles.sourceNode}>
      <div className={`${styles.sourceColor} ${styles[source.color]}`} />
      <div className={styles.sourceInfo}>
        <div className={styles.sourceName}>{source.name}</div>
        <div className={styles.sourceDesc}>{source.description}</div>
      </div>
      <StatusBadge status={source.status} />
    </div>
  );
}

export default function ApiHealthMap({
  sources,
  gatewayOnline,
  isLoading,
}: ApiHealthMapProps) {
  // Split sources: Offline/failed on the left, Online/active on the right.
  const offlineStatuses = ['OFFLINE', 'FAIL', 'ERROR', 'TIMEOUT'];
  const leftSources = sources.filter(s => offlineStatuses.includes(s.status.toUpperCase()));
  const rightSources = sources.filter(s => !offlineStatuses.includes(s.status.toUpperCase()));

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>API Health &amp; Routing Monitor</h3>
        <div className={styles.gatewayStatus}>
          <span className={`${styles.gatewayDot} ${gatewayOnline ? styles.online : styles.offline}`} />
          {isLoading ? 'Checking...' : gatewayOnline ? 'Online' : 'Offline'}
        </div>
      </div>

      <div className={styles.topology}>
        {/* Left Sources (Failed) */}
        <div className={styles.sourceColumn}>
          {isLoading ? (
            <>
              <div className={styles.sourceNodeSkeleton} />
              <div className={styles.sourceNodeSkeleton} />
            </>
          ) : (
            leftSources.map((source) => (
              <SourceNode key={source.name} source={source} />
            ))
          )}
        </div>

        {/* Connection Area Left */}
        <div className={styles.connectionArea}>
          <div className={`${styles.connectionLine} ${styles.lineLeft} ${gatewayOnline ? styles.lineActive : ''}`} />
        </div>

        {/* Central Hub */}
        <div className={`${styles.centralHub} ${gatewayOnline ? styles.hubOnline : ''}`}>
           <Server className={styles.hubIcon} size={26} />
        </div>

        {/* Connection Area Right */}
        <div className={styles.connectionArea}>
          <div className={`${styles.connectionLine} ${styles.lineRight} ${gatewayOnline ? styles.lineActive : ''}`} />
        </div>

        {/* Right Sources (Passed) */}
        <div className={styles.sourceColumn}>
          {isLoading ? (
            <>
              <div className={styles.sourceNodeSkeleton} />
              <div className={styles.sourceNodeSkeleton} />
            </>
          ) : (
            rightSources.map((source) => (
              <SourceNode key={source.name} source={source} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
