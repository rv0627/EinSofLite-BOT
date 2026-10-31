'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import styles from './BotController.module.css';
import StatusBadge from '../ui/StatusBadge';
import { showToast } from '../ui/Toast';
import { triggerEOD, triggerLiveWatchlist, fetchTaskStatus, triggerDataProcessor } from '@/lib/api';

type TaskState = 'idle' | 'pending' | 'started' | 'success' | 'failure';

interface TaskInfo {
  taskId: string | null;
  state: TaskState;
  result?: string;
  error?: string;
}

function mapCeleryState(state: string): TaskState {
  switch (state) {
    case 'PENDING': return 'pending';
    case 'STARTED': return 'started';
    case 'SUCCESS': return 'success';
    case 'FAILURE': return 'failure';
    default: return 'pending';
  }
}

function getStatusBadgeVariant(state: TaskState): 'active' | 'standby' | 'offline' | 'idle' | 'processing' {
  switch (state) {
    case 'pending': return 'processing';
    case 'started': return 'processing';
    case 'success': return 'active';
    case 'failure': return 'offline';
    default: return 'idle';
  }
}

function getStatusLabel(state: TaskState): string {
  switch (state) {
    case 'pending': return 'Processing Queue';
    case 'started': return 'Running';
    case 'success': return 'Complete';
    case 'failure': return 'Failed';
    default: return 'Idle';
  }
}

export default function BotController() {
  // EOD task state
  const [eodTask, setEodTask] = useState<TaskInfo>({ taskId: null, state: 'idle' });
  const [eodLoading, setEodLoading] = useState(false);
  const eodPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Live watchlist task state
  const [liveTask, setLiveTask] = useState<TaskInfo>({ taskId: null, state: 'idle' });
  const [liveLoading, setLiveLoading] = useState(false);
  const livePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Processing Bot task state
  const [processTask, setProcessTask] = useState<TaskInfo>({ taskId: null, state: 'idle' });
  const [processLoading, setProcessLoading] = useState(false);
  const processPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Poll task status ──
  const pollTask = useCallback((
    taskId: string,
    setTask: React.Dispatch<React.SetStateAction<TaskInfo>>,
    pollRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>,
    taskName: string,
    storageKey?: string,
  ) => {
    // Clear any existing poll
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchTaskStatus(taskId);
        const mappedState = mapCeleryState(status.state);

        setTask({
          taskId,
          state: mappedState,
          result: status.result,
          error: status.error,
        });

        // Stop polling if task is complete
        if (status.ready) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          
          if (storageKey) localStorage.removeItem(storageKey);

          if (status.state === 'SUCCESS') {
            showToast(status.result || `${taskName} completed successfully`, 'success');
          } else if (status.state === 'FAILURE') {
            showToast(status.error || `${taskName} failed: Unknown error`, 'error');
          }
        }
      } catch {
        // Network error — keep polling
        console.error(`Failed to poll task ${taskId}`);
      }
    }, 3000);
  }, []);

  // ── Cleanup intervals on unmount ──
  useEffect(() => {
    return () => {
      if (eodPollRef.current) clearInterval(eodPollRef.current);
      if (livePollRef.current) clearInterval(livePollRef.current);
      if (processPollRef.current) clearInterval(processPollRef.current);
    };
  }, []);

  // ── Resume active tasks from localStorage on mount ──
  useEffect(() => {
    const activeEod = localStorage.getItem('eodTaskId');
    if (activeEod) {
      setEodTask({ taskId: activeEod, state: 'pending' });
      pollTask(activeEod, setEodTask, eodPollRef, 'Master EOD', 'eodTaskId');
    }

    const activeLive = localStorage.getItem('liveTaskId');
    if (activeLive) {
      setLiveTask({ taskId: activeLive, state: 'pending' });
      pollTask(activeLive, setLiveTask, livePollRef, 'Live Watchlist', 'liveTaskId');
    }

    const activeProcess = localStorage.getItem('processTaskId');
    if (activeProcess) {
      setProcessTask({ taskId: activeProcess, state: 'pending' });
      pollTask(activeProcess, setProcessTask, processPollRef, 'Data Processor', 'processTaskId');
    }
  }, [pollTask]);

  // ── Trigger EOD ──
  const handleRunEOD = async () => {
    setEodLoading(true);
    try {
      const res = await triggerEOD();
      showToast('Master EOD Bot triggered', 'info');
      localStorage.setItem('eodTaskId', res.task_id);
      setEodTask({ taskId: res.task_id, state: 'pending' });
      pollTask(res.task_id, setEodTask, eodPollRef, 'Master EOD', 'eodTaskId');
    } catch (err) {
      console.error('Failed to trigger EOD:', err);
      showToast('Failed to trigger Master EOD', 'error');
    } finally {
      setEodLoading(false);
    }
  };

  // ── Trigger Live Watchlist ──
  const handleStartLive = async () => {
    setLiveLoading(true);
    try {
      const res = await triggerLiveWatchlist();
      showToast('Live Watchlist pull triggered', 'info');
      localStorage.setItem('liveTaskId', res.task_id);
      setLiveTask({ taskId: res.task_id, state: 'pending' });
      pollTask(res.task_id, setLiveTask, livePollRef, 'Live Watchlist', 'liveTaskId');
    } catch (err) {
      console.error('Failed to trigger live:', err);
      showToast('Failed to trigger Live Watchlist', 'error');
    } finally {
      setLiveLoading(false);
    }
  };

  // ── Trigger Data Processing ──
  const handleRunProcessor = async () => {
    setProcessLoading(true);
    try {
      const res = await triggerDataProcessor();
      showToast('Data Processing Bot triggered', 'info');
      localStorage.setItem('processTaskId', res.task_id);
      setProcessTask({ taskId: res.task_id, state: 'pending' });
      pollTask(res.task_id, setProcessTask, processPollRef, 'Data Processor', 'processTaskId');
    } catch (err) {
      console.error('Failed to trigger processor:', err);
      showToast('Failed to trigger Data Processor', 'error');
    } finally {
      setProcessLoading(false);
    }
  };

  // ── Reset Stuck Tasks ──
  const resetTask = useCallback((
    storageKey: string,
    setTask: React.Dispatch<React.SetStateAction<TaskInfo>>,
    pollRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>
  ) => {
    localStorage.removeItem(storageKey);
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setTask({ taskId: null, state: 'idle' });
  }, []);

  // ── Derive progress for EOD (simulated based on state) ──
  const eodProgress = eodTask.state === 'success' ? 100
    : eodTask.state === 'started' ? 65
    : eodTask.state === 'pending' ? 30
    : 0;

  const processProgress = processTask.state === 'success' ? 100
    : processTask.state === 'started' ? 65
    : processTask.state === 'pending' ? 30
    : 0;

  return (
    <div className={styles.container}>
      <h3 className={styles.header}>Bot Controller</h3>

      {/* Master EOD Bot */}
      <div className={styles.botSection}>
        <div className={styles.botHeader}>
          <span className={styles.botName}>Master EOD Bot</span>
          <StatusBadge
            status={getStatusBadgeVariant(eodTask.state)}
            label={getStatusLabel(eodTask.state)}
          />
        </div>

        <button
          className={styles.actionBtn}
          onClick={handleRunEOD}
          disabled={eodLoading || eodTask.state === 'pending' || eodTask.state === 'started'}
          id="btn-run-eod"
        >
          <span className={styles.actionIcon}>⟳</span>
          {eodLoading ? 'Triggering...' :
            eodTask.state === 'pending' || eodTask.state === 'started' ? 'Running...' :
            'Run Master EOD'}
        </button>

        <div className={styles.workerStatus}>
          <span>
            {eodTask.taskId ? `Task: ${eodTask.taskId.slice(0, 8)}` : 'Celery Worker: Idle'}
            {eodTask.taskId && (
              <span 
                style={{ marginLeft: '10px', color: '#f56565', cursor: 'pointer', fontSize: '0.75rem', textDecoration: 'underline' }}
                onClick={() => resetTask('eodTaskId', setEodTask, eodPollRef)}
              >
                Reset
              </span>
            )}
          </span>
          <span>{eodTask.state === 'success' ? 'Complete' :
            eodTask.state === 'failure' ? 'Failed' :
            eodProgress > 0 ? `${eodProgress}% Complete` : 'Pending'}</span>
        </div>
        {(eodTask.state !== 'idle') && (
          <div className={styles.progressWrap}>
            <div className={styles.progressFill} style={{ width: `${eodProgress}%` }} />
          </div>
        )}
      </div>

      <div className={styles.divider} />

      {/* Data Processing Bot */}
      <div className={styles.botSection}>
        <div className={styles.botHeader}>
          <span className={styles.botName}>Data Processing Bot</span>
          <StatusBadge
            status={getStatusBadgeVariant(processTask.state)}
            label={getStatusLabel(processTask.state)}
          />
        </div>

        <button
          className={styles.actionBtn}
          onClick={handleRunProcessor}
          disabled={processLoading || processTask.state === 'pending' || processTask.state === 'started'}
          id="btn-run-process"
        >
          <span className={styles.actionIcon}>⚙️</span>
          {processLoading ? 'Triggering...' :
            processTask.state === 'pending' || processTask.state === 'started' ? 'Running...' :
            'Run Data Processor'}
        </button>

        <div className={styles.workerStatus}>
          <span>
            {processTask.taskId ? `Task: ${processTask.taskId.slice(0, 8)}` : 'Celery Worker: Idle'}
            {processTask.taskId && (
              <span 
                style={{ marginLeft: '10px', color: '#f56565', cursor: 'pointer', fontSize: '0.75rem', textDecoration: 'underline' }}
                onClick={() => resetTask('processTaskId', setProcessTask, processPollRef)}
              >
                Reset
              </span>
            )}
          </span>
          <span>{processTask.state === 'success' ? 'Complete' :
            processTask.state === 'failure' ? 'Failed' :
            processProgress > 0 ? `${processProgress}% Complete` : 'Pending'}</span>
        </div>
        {(processTask.state !== 'idle') && (
          <div className={styles.progressWrap}>
            <div className={styles.progressFill} style={{ width: `${processProgress}%` }} />
          </div>
        )}
      </div>

      <div className={styles.divider} />

      {/* Live Watchlist */}
      <div className={styles.botSection}>
        <div className={styles.botHeader}>
          <span className={styles.botName}>Live Watchlist</span>
          <StatusBadge
            status={getStatusBadgeVariant(liveTask.state)}
            label={getStatusLabel(liveTask.state)}
          />
        </div>

        <button
          className={styles.actionBtn}
          onClick={handleStartLive}
          disabled={liveLoading || liveTask.state === 'pending' || liveTask.state === 'started'}
          id="btn-start-live"
        >
          <span className={styles.actionIcon}>▷</span>
          {liveLoading ? 'Triggering...' :
            liveTask.state === 'pending' || liveTask.state === 'started' ? 'Running...' :
            'Start Live Watchlist'}
        </button>

        <div className={styles.workerStatus}>
          <span>
            {liveTask.taskId ? `Task: ${liveTask.taskId.slice(0, 8)}` : 'Celery Worker: Idle'}
            {liveTask.taskId && (
              <span 
                style={{ marginLeft: '10px', color: '#f56565', cursor: 'pointer', fontSize: '0.75rem', textDecoration: 'underline' }}
                onClick={() => resetTask('liveTaskId', setLiveTask, livePollRef)}
              >
                Reset
              </span>
            )}
          </span>
          <span>{getStatusLabel(liveTask.state)}</span>
        </div>
      </div>

      <div className={styles.divider} />

      {/* Autopilot Status */}
      {/* <div className={styles.autopilot}>
        <div className={styles.autopilotIcon}>ℹ</div>
        <div className={styles.autopilotText}>
          Autopilot active. Bot logic follows &apos;Aggressive Rebalancing&apos; protocol v4.2.
        </div>
      </div> */}
    </div>
  );
}
