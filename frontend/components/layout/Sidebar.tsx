'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { HelpCircle, LayoutDashboard, LineChart, PieChart, Star, Activity, Settings, LogOut, Trophy, Shield } from 'lucide-react';
import styles from './Sidebar.module.css';

const navItems = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Analytics', href: '/analytics', icon: LineChart },
  { label: 'Portfolio', href: '/portfolio', icon: PieChart },
  { label: 'EIN Score', href: '/ein-score', icon: Star },
  { label: 'Top 20', href: '/top-20', icon: Trophy },
  { label: 'Governance', href: '/governance', icon: Shield },
  { label: 'Shadow Validation', href: '/shadow-validation', icon: Activity },
  { label: 'API Health', href: '/api-health', icon: Activity },
  { label: 'Settings', href: '/settings', icon: Settings },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className={`${styles.sidebar} ${isOpen ? styles.open : ''}`}>
      {/* Logo */}
      <div className={styles.logo}>
        <div>
          <div className={styles.logoTitle}>Ein Sof Lite</div>
          <div className={styles.logoSubtitle}>Institutional Grade</div>
        </div>
        <button className={styles.closeButton} onClick={onClose}>
          ✕
        </button>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`${styles.navItem} ${pathname === item.href ? styles.active : ''}`}
            >
              <span className={styles.navIcon}>
                <Icon size={18} strokeWidth={2.2} style={{ flexShrink: 0 }} />
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Trade Now CTA */}
      {/* <div className={styles.ctaSection}>
        <button className={styles.ctaButton}>Trade Now</button>
      </div> */}

      {/* Footer */}
      <div className={styles.footer}>
        <button className={styles.footerItem}>
          <HelpCircle size={16} strokeWidth={2.2} className={styles.footerIcon} style={{ flexShrink: 0 }} />
          Support
        </button>
        <button className={styles.footerItem}>
          <LogOut size={16} strokeWidth={2.2} className={styles.footerIcon} style={{ flexShrink: 0 }} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
