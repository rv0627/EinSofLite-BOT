/**
 * Ein Sof Lite — Technical Indicator Calculation Engine
 * Pure TypeScript implementation of all Binance-style indicators.
 * Runs client-side for instant parameter changes.
 */

import type { AnalyticsChartData } from './api';

// ── Helper: EMA ──
function calcEMA(prices: number[], period: number): number[] {
  if (prices.length < period) return [];
  const multiplier = 2 / (period + 1);
  const ema = [prices.slice(0, period).reduce((a, b) => a + b, 0) / period];
  for (let i = period; i < prices.length; i++) {
    ema.push((prices[i] - ema[ema.length - 1]) * multiplier + ema[ema.length - 1]);
  }
  return ema;
}

// ── Helper: SMA ──
function calcSMA(prices: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = period - 1; i < prices.length; i++) {
    const slice = prices.slice(i - period + 1, i + 1);
    result.push(slice.reduce((a, b) => a + b, 0) / period);
  }
  return result;
}

// ── Indicator Result Types ──

export interface IndicatorSeries {
  label: string;
  data: number[];
  color: string;
  type: 'line' | 'bar';
}

export interface IndicatorResult {
  name: string;
  series: IndicatorSeries[];
  refLines?: { value: number; color: string; dash?: boolean }[];
  /** Aligned to the END of the chartData array (last N values) */
  alignedLength: number;
}

// ── MA (Moving Averages — overlaid on candlestick chart) ──

export interface MAConfig {
  periods: { period: number; color: string; enabled: boolean }[];
}

export function calcMA(data: AnalyticsChartData[], config: MAConfig): { period: number; values: number[]; color: string }[] {
  const closes = data.map(d => d.close);
  return config.periods
    .filter(p => p.enabled)
    .map(p => ({
      period: p.period,
      values: calcSMA(closes, p.period),
      color: p.color,
    }));
}

// ── VOL (Volume) ──

export function calcVOL(data: AnalyticsChartData[]): IndicatorResult {
  return {
    name: 'VOL',
    alignedLength: data.length,
    series: [
      {
        label: 'Volume',
        data: data.map(d => d.volume),
        color: 'var(--accent-cyan)',
        type: 'bar',
      },
    ],
  };
}

// ── RSI (Relative Strength Index — Wilder Smoothing) ──

export function calcRSI(data: AnalyticsChartData[], period: number = 14): IndicatorResult {
  const closes = data.map(d => d.close);
  const rsiValues: number[] = [];

  if (closes.length <= period) {
    return { name: `RSI(${period})`, alignedLength: 0, series: [], refLines: [] };
  }

  const deltas = closes.slice(1).map((c, i) => c - closes[i]);
  let avgGain = deltas.slice(0, period).reduce((s, d) => s + Math.max(d, 0), 0) / period;
  let avgLoss = deltas.slice(0, period).reduce((s, d) => s + Math.abs(Math.min(d, 0)), 0) / period;

  rsiValues.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));

  for (let i = period; i < deltas.length; i++) {
    avgGain = (avgGain * (period - 1) + Math.max(deltas[i], 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.abs(Math.min(deltas[i], 0))) / period;
    rsiValues.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  }

  return {
    name: `RSI(${period})`,
    alignedLength: rsiValues.length,
    series: [{
      label: `RSI ${period}`,
      data: rsiValues,
      color: '#f5c542',
      type: 'line',
    }],
    refLines: [
      { value: 70, color: 'rgba(255,23,68,0.4)', dash: true },
      { value: 30, color: 'rgba(0,229,255,0.4)', dash: true },
    ],
  };
}

// ── MACD ──

export function calcMACD(
  data: AnalyticsChartData[],
  fast: number = 12,
  slow: number = 26,
  signal: number = 9
): IndicatorResult {
  const closes = data.map(d => d.close);
  if (closes.length < slow) {
    return { name: `MACD(${fast},${slow},${signal})`, alignedLength: 0, series: [] };
  }

  const emaFast = calcEMA(closes, fast);
  const emaSlow = calcEMA(closes, slow);
  const offset = slow - fast;

  const macdLine: number[] = [];
  for (let i = 0; i < emaSlow.length; i++) {
    macdLine.push(emaFast[i + offset] - emaSlow[i]);
  }

  const signalLine = macdLine.length >= signal ? calcEMA(macdLine, signal) : [];
  const signalOffset = macdLine.length - signalLine.length;

  const histogram: number[] = [];
  for (let i = 0; i < signalLine.length; i++) {
    histogram.push(macdLine[i + signalOffset] - signalLine[i]);
  }

  return {
    name: `MACD(${fast},${slow},${signal})`,
    alignedLength: signalLine.length,
    series: [
      { label: 'Histogram', data: histogram, color: '#26a69a', type: 'bar' },
      { label: 'MACD', data: macdLine.slice(signalOffset), color: '#2196f3', type: 'line' },
      { label: 'Signal', data: signalLine, color: '#ff9800', type: 'line' },
    ],
    refLines: [{ value: 0, color: 'rgba(255,255,255,0.1)', dash: true }],
  };
}

// ── MFI (Money Flow Index) ──

export function calcMFI(data: AnalyticsChartData[], period: number = 14): IndicatorResult {
  if (data.length <= period) {
    return { name: `MFI(${period})`, alignedLength: 0, series: [], refLines: [] };
  }

  const typicalPrices = data.map(d => (d.high + d.low + d.close) / 3);
  const rawMF = typicalPrices.map((tp, i) => tp * data[i].volume);

  const mfiValues: number[] = [];
  for (let i = period; i < data.length; i++) {
    let posFlow = 0, negFlow = 0;
    for (let j = i - period + 1; j <= i; j++) {
      if (typicalPrices[j] > typicalPrices[j - 1]) posFlow += rawMF[j];
      else negFlow += rawMF[j];
    }
    mfiValues.push(negFlow === 0 ? 100 : 100 - 100 / (1 + posFlow / negFlow));
  }

  return {
    name: `MFI(${period})`,
    alignedLength: mfiValues.length,
    series: [{ label: `MFI ${period}`, data: mfiValues, color: '#ab47bc', type: 'line' }],
    refLines: [
      { value: 80, color: 'rgba(255,23,68,0.4)', dash: true },
      { value: 20, color: 'rgba(0,229,255,0.4)', dash: true },
    ],
  };
}

// ── KDJ (Stochastic Oscillator) ──

export function calcKDJ(data: AnalyticsChartData[], kPeriod: number = 9, dPeriod: number = 3, jPeriod: number = 3): IndicatorResult {
  if (data.length < kPeriod) {
    return { name: `KDJ(${kPeriod},${dPeriod},${jPeriod})`, alignedLength: 0, series: [] };
  }

  const kValues: number[] = [];
  for (let i = kPeriod - 1; i < data.length; i++) {
    const slice = data.slice(i - kPeriod + 1, i + 1);
    const low = Math.min(...slice.map(d => d.low));
    const high = Math.max(...slice.map(d => d.high));
    const rsv = high === low ? 50 : ((data[i].close - low) / (high - low)) * 100;
    kValues.push(rsv);
  }

  const dValues = calcSMA(kValues, dPeriod);
  const kAligned = kValues.slice(kValues.length - dValues.length);

  const jValues = kAligned.map((k, i) => 3 * k - 2 * dValues[i]);

  return {
    name: `KDJ(${kPeriod},${dPeriod},${jPeriod})`,
    alignedLength: dValues.length,
    series: [
      { label: 'K', data: kAligned, color: '#f5c542', type: 'line' },
      { label: 'D', data: dValues, color: '#2196f3', type: 'line' },
      { label: 'J', data: jValues, color: '#ab47bc', type: 'line' },
    ],
    refLines: [
      { value: 80, color: 'rgba(255,23,68,0.3)', dash: true },
      { value: 20, color: 'rgba(0,229,255,0.3)', dash: true },
    ],
  };
}

// ── OBV (On-Balance Volume) ──

export function calcOBV(data: AnalyticsChartData[]): IndicatorResult {
  const obvValues: number[] = [data[0]?.volume ?? 0];
  for (let i = 1; i < data.length; i++) {
    if (data[i].close > data[i - 1].close) obvValues.push(obvValues[i - 1] + data[i].volume);
    else if (data[i].close < data[i - 1].close) obvValues.push(obvValues[i - 1] - data[i].volume);
    else obvValues.push(obvValues[i - 1]);
  }

  return {
    name: 'OBV',
    alignedLength: obvValues.length,
    series: [{ label: 'OBV', data: obvValues, color: '#26a69a', type: 'line' }],
  };
}

// ── CCI (Commodity Channel Index) ──

export function calcCCI(data: AnalyticsChartData[], period: number = 20): IndicatorResult {
  if (data.length < period) {
    return { name: `CCI(${period})`, alignedLength: 0, series: [], refLines: [] };
  }

  const tp = data.map(d => (d.high + d.low + d.close) / 3);
  const cciValues: number[] = [];

  for (let i = period - 1; i < tp.length; i++) {
    const slice = tp.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const meanDev = slice.reduce((a, v) => a + Math.abs(v - mean), 0) / period;
    cciValues.push(meanDev === 0 ? 0 : (tp[i] - mean) / (0.015 * meanDev));
  }

  return {
    name: `CCI(${period})`,
    alignedLength: cciValues.length,
    series: [{ label: `CCI ${period}`, data: cciValues, color: '#ff7043', type: 'line' }],
    refLines: [
      { value: 100, color: 'rgba(255,23,68,0.4)', dash: true },
      { value: -100, color: 'rgba(0,229,255,0.4)', dash: true },
      { value: 0, color: 'rgba(255,255,255,0.1)', dash: true },
    ],
  };
}

// ── Stochastic RSI ──

export function calcStochRSI(data: AnalyticsChartData[], period: number = 14, kPeriod: number = 3, dPeriod: number = 3): IndicatorResult {
  const rsiResult = calcRSI(data, period);
  if (!rsiResult.series.length || rsiResult.series[0].data.length < period) {
    return { name: `StochRSI(${period})`, alignedLength: 0, series: [], refLines: [] };
  }

  const rsiData = rsiResult.series[0].data;
  const stochK: number[] = [];

  for (let i = period - 1; i < rsiData.length; i++) {
    const slice = rsiData.slice(i - period + 1, i + 1);
    const min = Math.min(...slice);
    const max = Math.max(...slice);
    stochK.push(max === min ? 50 : ((rsiData[i] - min) / (max - min)) * 100);
  }

  const smoothK = calcSMA(stochK, kPeriod);
  const smoothD = calcSMA(smoothK, dPeriod);
  const alignedK = smoothK.slice(smoothK.length - smoothD.length);

  return {
    name: `StochRSI(${period})`,
    alignedLength: smoothD.length,
    series: [
      { label: 'K', data: alignedK, color: '#2196f3', type: 'line' },
      { label: 'D', data: smoothD, color: '#ff9800', type: 'line' },
    ],
    refLines: [
      { value: 80, color: 'rgba(255,23,68,0.4)', dash: true },
      { value: 20, color: 'rgba(0,229,255,0.4)', dash: true },
    ],
  };
}

// ── WR (Williams %R) ──

export function calcWR(data: AnalyticsChartData[], period: number = 14): IndicatorResult {
  if (data.length < period) {
    return { name: `WR(${period})`, alignedLength: 0, series: [], refLines: [] };
  }

  const wrValues: number[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const high = Math.max(...slice.map(d => d.high));
    const low = Math.min(...slice.map(d => d.low));
    wrValues.push(high === low ? -50 : ((high - data[i].close) / (high - low)) * -100);
  }

  return {
    name: `WR(${period})`,
    alignedLength: wrValues.length,
    series: [{ label: `WR ${period}`, data: wrValues, color: '#e91e63', type: 'line' }],
    refLines: [
      { value: -20, color: 'rgba(255,23,68,0.4)', dash: true },
      { value: -80, color: 'rgba(0,229,255,0.4)', dash: true },
    ],
  };
}

// ── Indicator Config & Defaults ──

export type IndicatorType = 'VOL' | 'MACD' | 'RSI' | 'MFI' | 'KDJ' | 'OBV' | 'CCI' | 'StochRSI' | 'WR';

export interface IndicatorConfig {
  type: IndicatorType;
  enabled: boolean;
  params: Record<string, number>;
}

export const DEFAULT_INDICATORS: IndicatorConfig[] = [
  { type: 'VOL', enabled: true, params: {} },
  { type: 'MACD', enabled: true, params: { fast: 12, slow: 26, signal: 9 } },
  { type: 'RSI', enabled: true, params: { period: 14 } },
  { type: 'MFI', enabled: false, params: { period: 14 } },
  { type: 'KDJ', enabled: false, params: { k: 9, d: 3, j: 3 } },
  { type: 'OBV', enabled: false, params: {} },
  { type: 'CCI', enabled: false, params: { period: 20 } },
  { type: 'StochRSI', enabled: false, params: { period: 14, k: 3, d: 3 } },
  { type: 'WR', enabled: false, params: { period: 14 } },
];

export const DEFAULT_MA_CONFIG: MAConfig = {
  periods: [
    { period: 7, color: '#f5c542', enabled: true },
    { period: 25, color: '#ab47bc', enabled: true },
    { period: 99, color: '#00e5ff', enabled: false },
  ],
};

// ── Master Calculator ──

export function calculateIndicator(data: AnalyticsChartData[], config: IndicatorConfig): IndicatorResult | null {
  if (!data || data.length === 0) return null;

  switch (config.type) {
    case 'VOL': return calcVOL(data);
    case 'MACD': return calcMACD(data, config.params.fast, config.params.slow, config.params.signal);
    case 'RSI': return calcRSI(data, config.params.period);
    case 'MFI': return calcMFI(data, config.params.period);
    case 'KDJ': return calcKDJ(data, config.params.k, config.params.d, config.params.j);
    case 'OBV': return calcOBV(data);
    case 'CCI': return calcCCI(data, config.params.period);
    case 'StochRSI': return calcStochRSI(data, config.params.period, config.params.k, config.params.d);
    case 'WR': return calcWR(data, config.params.period);
    default: return null;
  }
}
