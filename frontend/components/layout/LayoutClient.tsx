'use client';

import { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import TopBar from '@/components/layout/TopBar';
import styles from '@/app/layout.module.css';

import ToastContainer from '@/components/ui/Toast';

export default function LayoutClient({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className={styles.layoutWrap}>
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <TopBar onMenuClick={() => setIsSidebarOpen(true)} />
      <main className={styles.mainContent}>{children}</main>
      
      {/* Global Toast Notifications */}
      <ToastContainer />
      
      {/* Overlay for mobile */}
      {isSidebarOpen && (
        <div 
          className={styles.overlay} 
          onClick={() => setIsSidebarOpen(false)}
        />
      )}
    </div>
  );
}
