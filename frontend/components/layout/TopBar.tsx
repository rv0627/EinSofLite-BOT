'use client';

import styles from './TopBar.module.css';

interface TopBarProps {
  onMenuClick: () => void;
}

export default function TopBar({ onMenuClick }: TopBarProps) {
  return (
    <header className={styles.topbar}>
      {/* Mobile Menu Button */}
      <button className={styles.menuButton} onClick={onMenuClick}>
        ☰
      </button>

      {/* Search removed as per request */}

      {/* Right Actions */}
      <div className={styles.actions}>
        {/* <button className={styles.iconBtn} title="Notifications" id="btn-notifications">
          🔔
        </button> */}
        {/* <button className={styles.iconBtn} title="Dark Mode" id="btn-darkmode">
          🌙
        </button> */}
        {/* <button className={styles.iconBtn} title="Grid Menu" id="btn-grid-menu">
          ⊞
        </button> */}

        {/* User Profile */}
        <div className={styles.userSection}>
          <div className={styles.userInfo}>
            <div className={styles.userName}>CIO Admin</div>
            <div className={styles.userRole}>Master Account</div>
          </div>
          <div className={styles.avatar}>CA</div>
        </div>
      </div>
    </header>
  );
}
