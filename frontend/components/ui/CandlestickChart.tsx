'use client';

import { useMemo } from 'react';
import type { AnalyticsChartData } from '@/lib/api';

interface CandlestickChartProps {
  data: AnalyticsChartData[];
  width?: number | string;
  height?: number | string;
  overlays?: { period: number; values: number[]; color: string }[];
}

export default function CandlestickChart({ data, width = '100%', height = '100%', overlays = [] }: CandlestickChartProps) {
  const chartParams = useMemo(() => {
    if (!data || data.length === 0) return null;

    // Find min and max for scaling
    const prices = data.flatMap(d => [d.low, d.high]);
    const volumes = data.map(d => d.volume);
    
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const maxVolume = Math.max(...volumes);
    
    const priceRange = maxPrice - minPrice;
    
    // Add padding to range
    let paddedMin = minPrice - (priceRange * 0.1);
    let paddedMax = maxPrice + (priceRange * 0.1);
    let paddedRange = paddedMax - paddedMin;
    
    // Fallback if there is no price range (e.g., only 1 candle, or all prices identical)
    if (paddedRange === 0) {
       paddedMin = minPrice * 0.9;
       paddedMax = maxPrice * 1.1;
       paddedRange = paddedMax - paddedMin;
       
       if (paddedRange === 0) { // If price itself is 0
         paddedMin = 0;
         paddedMax = 100;
         paddedRange = 100;
       }
    }

    return { paddedMin, paddedMax, paddedRange, maxVolume: maxVolume || 1 };
  }, [data]);

  if (!chartParams || data.length === 0) {
    return (
      <div style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
        No chart data available
      </div>
    );
  }

  const { paddedMin, paddedRange, maxVolume } = chartParams;
  const numCandles = data.length;

  return (
    <div style={{ width, height, position: 'relative' }}>
      {/* Candlesticks Layer */}
      <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', top: 0, left: 0 }}>
        {data.map((candle, index) => {
          const isPositive = candle.close >= candle.open;
          const color = isPositive ? 'var(--accent-cyan)' : 'var(--accent-red)';
          
          // X positions (0-100 scale)
          const xPercent = ((index + 0.5) / numCandles) * 100;
          // Dynamically adjust candle width based on number of candles to avoid them being too wide
          const baseCandleWidth = (0.6 / numCandles) * 100;
          const candleWidthPercent = Math.min(baseCandleWidth, 5); // Max 5% width
          const rectXPercent = xPercent - (candleWidthPercent / 2);
          
          // Y positions (0-100 scale, inverted)
          const highY = 100 - (((candle.high - paddedMin) / paddedRange) * 100);
          const lowY = 100 - (((candle.low - paddedMin) / paddedRange) * 100);
          const openY = 100 - (((candle.open - paddedMin) / paddedRange) * 100);
          const closeY = 100 - (((candle.close - paddedMin) / paddedRange) * 100);
          
          const rectTopY = Math.min(openY, closeY);
          const rectHeight = Math.max(Math.abs(closeY - openY), 0.5); // min 0.5 height
          
          return (
            <g key={`${candle.date}-${index}`}>
              {/* Wick */}
              <line 
                x1={xPercent} 
                y1={highY} 
                x2={xPercent} 
                y2={lowY} 
                stroke={color} 
                strokeWidth="1.5" 
                vectorEffect="non-scaling-stroke"
              />
              {/* Body */}
              <rect 
                x={rectXPercent} 
                y={rectTopY} 
                width={candleWidthPercent} 
                height={rectHeight} 
                fill={color} 
                rx="0.2" 
              />
            </g>
          );
        })}
        
        {/* Current Price Line */}
        {data.length > 0 && (() => {
           const lastClose = data[data.length - 1].close;
           const lastY = 100 - (((lastClose - paddedMin) / paddedRange) * 100);
           return (
             <line 
               x1="0" 
               y1={lastY} 
               x2="100" 
               y2={lastY} 
               stroke="var(--accent-cyan)" 
               strokeWidth="1" 
               strokeDasharray="2 2" 
               opacity="0.5" 
               vectorEffect="non-scaling-stroke"
             />
           );
        })()}
      </svg>
      
      {/* Current Price Tag */}
      {data.length > 0 && (() => {
        const lastClose = data[data.length - 1].close;
        const lastY = 100 - (((lastClose - paddedMin) / paddedRange) * 100);
        return (
          <div 
            style={{ 
              position: 'absolute', 
              right: 0, 
              top: `${lastY}%`, 
              transform: 'translateY(-50%)',
              background: 'var(--accent-cyan)',
              color: '#000',
              padding: '2px 6px',
              fontSize: '0.7rem',
              fontWeight: 'bold',
              borderRadius: '4px',
              zIndex: 10
            }}
          >
            {lastClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        );
      })()}
      
      {/* Volume Layer */}
      <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
        {data.map((candle, index) => {
          const isPositive = candle.close >= candle.open;
          const color = isPositive ? 'var(--accent-cyan)' : 'var(--accent-red)';
          
          const xPercent = ((index + 0.5) / numCandles) * 100;
          const baseCandleWidth = (0.6 / numCandles) * 100;
          const candleWidthPercent = Math.min(baseCandleWidth, 5); // Max 5% width
          const rectXPercent = xPercent - (candleWidthPercent / 2);
          
          // Scale volume to take up max 30% of the chart height from the bottom
          const volumeHeightPercent = (candle.volume / maxVolume) * 30;
          const volumeY = 100 - volumeHeightPercent;
          
          return (
            <rect 
              key={`vol-${candle.date}-${index}`}
              x={rectXPercent} 
              y={volumeY} 
              width={candleWidthPercent} 
              height={volumeHeightPercent} 
              fill={color} 
              opacity="0.15" 
            />
          );
        })}
      </svg>
      
      {/* Moving Average Overlays Layer */}
      {overlays.length > 0 && (
        <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
          {overlays.map((ma, i) => {
             // Values array is aligned to the END of data array
             const startOffset = numCandles - ma.values.length;
             const points = ma.values.map((val, idx) => {
                const globalIdx = startOffset + idx;
                const x = ((globalIdx + 0.5) / numCandles) * 100;
                const y = 100 - (((val - paddedMin) / paddedRange) * 100);
                return `${x},${y}`;
             });
             return (
               <polyline 
                 key={`ma-${ma.period}-${i}`}
                 points={points.join(' ')}
                 fill="none"
                 stroke={ma.color}
                 strokeWidth="1.5"
                 vectorEffect="non-scaling-stroke"
                 strokeLinejoin="round"
                 opacity="0.8"
               />
             );
          })}
        </svg>
      )}
    </div>
  );
}
