import type { Metadata } from 'next';
import './globals.css';
import LayoutClient from '@/components/layout/LayoutClient';

export const metadata: Metadata = {
  title: 'Ein Sof Lite — Institutional Grade Trading Platform',
  description:
    'Modular multi-bot investment intelligence system with real-time market data, API health monitoring, and automated trading workflows.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <LayoutClient>{children}</LayoutClient>
      </body>
    </html>
  );
}
