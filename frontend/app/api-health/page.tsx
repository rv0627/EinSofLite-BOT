'use client';

import { useState, useEffect } from 'react';
import styles from './page.module.css';
import { fetchInfrastructureHealth, fetchRoutingLogs, InfrastructureNode, RoutingLog } from '@/lib/api';

export default function ApiHealthPage() {
  const [nodes, setNodes] = useState<InfrastructureNode[]>([]);
  const [routingLogs, setRoutingLogs] = useState<RoutingLog[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);

  const loadData = async () => {
    try {
      const [newNodes, newLogs] = await Promise.all([
        fetchInfrastructureHealth(),
        fetchRoutingLogs()
      ]);
      setNodes(newNodes);
      setRoutingLogs(newLogs);
    } catch (e) {
      console.error("Failed to load infrastructure data", e);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000); // refresh every 60 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.page}>
      
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.titleArea}>
          <h1 className={styles.title}>Infrastructure Connectivity</h1>
          <p className={styles.subtitle}>
            Monitoring global data providers and redundant routing protocols. 
          </p>
        </div>
        <div className={styles.globalUptimeBadge}>
          <span className={styles.uptimeDot}></span>
          ONLINE: {nodes.length > 0 ? (nodes.reduce((acc, node) => acc + parseFloat(node.uptime.replace('%', '')), 0) / nodes.length).toFixed(2) + '%' : 'Loading...'}
        </div>
      </div>

      {/* ── Node Cards ── */}
      <div className={styles.nodeGrid}>
        {nodes.map((node) => (
          <div key={node.id} className={styles.nodeCard}>
            <div className={styles.nodeHeader}>
              <span className={styles.nodeLabel}>NODE 0{node.id}</span>
              <span className={styles.nodeId}>{node.id}</span>
            </div>
            
            <div className={styles.nodeInfo}>
              <div className={styles.nodeName}>{node.name}</div>
              <div className={styles.nodeRole}>{node.role}</div>
            </div>

            <div className={styles.nodeStats}>
              <div className={styles.statRow}>
                <span className={styles.statLabel}>Uptime</span>
                <span className={`${styles.statValue} ${styles.green}`}>{node.uptime}</span>
              </div>
              <div className={styles.statRow}>
                <span className={styles.statLabel}>Latency</span>
                <span className={`${styles.statValue} ${styles.cyan}`}>{node.latency}</span>
              </div>
              <div className={styles.nodeBarContainer}>
                <div 
                    className={styles.nodeBarFill} 
                    style={{ 
                        width: `${node.health}%`, 
                        background: node.isPrimary || node.health === 100 ? 'var(--accent-cyan)' : node.health > 50 ? 'var(--accent-cyan-dim)' : 'var(--text-muted)' 
                    }}>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Fallback Sequence Protocol ── */}
      

      {/* ── Live Routing Log ── */}
      {/* <div className={styles.logSection}>
        <div className={styles.logHeader}>
          <h3 className={styles.logTitle}>Live Routing Log</h3>
          <div className={styles.autoScrollToggle} onClick={() => setAutoScroll(!autoScroll)} style={{cursor: 'pointer'}}>
            AUTO-SCROLL: {autoScroll ? 'ON' : 'OFF'}
            <div className={styles.toggleSwitch} style={{ opacity: autoScroll ? 1 : 0.5 }}>
              <div className={styles.toggleKnob} style={{ transform: autoScroll ? 'translateX(16px)' : 'translateX(0)' }}></div>
            </div>
          </div>
        </div>
        <div className={styles.logConsole}>
          {routingLogs.map((log, i) => (
            <div key={i} className={styles.logRow}>
              <span className={styles.logId}>{log.id}</span>
              <span className={styles.logProvider}>{log.provider}</span>
              <span className={styles.logPath}>{log.path}</span>
              <span className={`${styles.logStatus} ${log.isError ? styles.statusError : styles.statusOk}`}>
                {log.status}
              </span>
              <span className={styles.logLatency}>latency: {log.latency}</span>
            </div>
          ))}
        </div>
      </div> */}

    </div>
  );
}
