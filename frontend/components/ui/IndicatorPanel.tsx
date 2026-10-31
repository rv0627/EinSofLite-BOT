'use client';

import { useMemo } from 'react';
import type { IndicatorResult } from '@/lib/indicators';

interface IndicatorPanelProps {
  result: IndicatorResult;
  chartLength: number;
  height?: number;
}

export default function IndicatorPanel({ result, chartLength, height = 80 }: IndicatorPanelProps) {
  const { series, refLines, name, alignedLength } = result;

  const chartData = useMemo(() => {
    if (!series.length || alignedLength === 0) return null;

    // Flatten all data to find min/max for Y scaling
    const allValues = series.flatMap(s => s.data);
    const refValues = (refLines || []).map(r => r.value);
    const combined = [...allValues, ...refValues];

    let min = Math.min(...combined);
    let max = Math.max(...combined);
    const range = max - min;
    min -= range * 0.1 || 1;
    max += range * 0.1 || 1;

    return { min, max, range: max - min };
  }, [series, refLines, alignedLength]);

  if (!chartData || alignedLength === 0) {
    return (
      <div style={{
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontSize: '0.7rem',
        borderTop: '1px solid var(--border-subtle)',
      }}>
        Not enough data for {name}
      </div>
    );
  }

  const { min, range } = chartData;
  const numBars = chartLength;
  // Series are aligned to end of chart data
  const startOffset = numBars - alignedLength;

  const scaleY = (value: number) => {
    return height - ((value - min) / range) * height;
  };

  return (
    <div style={{
      height,
      position: 'relative',
      borderTop: '1px solid var(--border-subtle)',
      paddingTop: 2,
    }}>
      {/* Indicator Label */}
      <div style={{
        position: 'absolute',
        top: 4,
        left: 8,
        fontSize: '0.65rem',
        fontWeight: 600,
        color: 'var(--text-muted)',
        fontFamily: "'JetBrains Mono', monospace",
        zIndex: 10,
        display: 'flex',
        gap: 10,
        alignItems: 'center',
      }}>
        <span>{name}</span>
        {series.map((s, i) => (
          <span key={i} style={{ color: s.color, fontSize: '0.6rem' }}>
            {s.label}: {s.data[s.data.length - 1]?.toFixed(2) ?? '—'}
          </span>
        ))}
      </div>

      <svg width="100%" height={height} viewBox={`0 0 100 ${height}`} preserveAspectRatio="none">
        {/* Reference Lines */}
        {(refLines || []).map((ref, i) => {
          const y = scaleY(ref.value);
          return (
            <line
              key={`ref-${i}`}
              x1="0" y1={y} x2="100" y2={y}
              stroke={ref.color}
              strokeWidth="1"
              strokeDasharray={ref.dash ? "2 2" : "none"}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}

        {/* Data Series */}
        {series.map((s, si) => {
          if (s.type === 'bar') {
            return s.data.map((value, di) => {
              const idx = startOffset + di;
              const xPct = ((idx + 0.5) / numBars) * 100;
              const barWidth = Math.min((0.6 / numBars) * 100, 4);
              const y = scaleY(value);
              const zeroY = scaleY(0);
              const barTop = Math.min(y, zeroY);
              const barHeight = Math.abs(y - zeroY);

              // For volume, use cyan/red based on sign; for MACD histogram use green/red
              let color = s.color;
              if (name.startsWith('MACD')) {
                color = value >= 0 ? 'rgba(38,166,154,0.7)' : 'rgba(239,83,80,0.7)';
              } else if (name === 'VOL') {
                color = 'rgba(0,229,255,0.25)';
              }

              return (
                <rect
                  key={`bar-${si}-${di}`}
                  x={xPct - barWidth / 2}
                  y={barTop}
                  width={barWidth}
                  height={Math.max(barHeight, 0.3)}
                  fill={color}
                />
              );
            });
          }

          // Line type
          const points = s.data.map((value, di) => {
            const idx = startOffset + di;
            const x = ((idx + 0.5) / numBars) * 100;
            const y = scaleY(value);
            return `${x},${y}`;
          });

          return (
            <polyline
              key={`line-${si}`}
              points={points.join(' ')}
              fill="none"
              stroke={s.color}
              strokeWidth="1.2"
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
            />
          );
        })}
      </svg>
    </div>
  );
}
