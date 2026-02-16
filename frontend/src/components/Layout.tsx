import { Outlet, NavLink } from 'react-router-dom';
import { LayoutDashboard, BookOpen, Activity, Zap, LogOut } from 'lucide-react';
import { SiteHeader } from './SiteHeader';
import { useAuth } from '../hooks/useAuth';
import { useRbac } from '../hooks/useRbac';
import { StatusTag } from './StatusTag';

export function Layout() {
  const { user, logout } = useAuth();
  const { role, label } = useRbac();

  const roleColour = role === 'L1-operator' ? 'green'
    : role === 'L2-engineer' ? 'orange'
    : role === 'L3-admin' ? 'blue'
    : 'grey';

  return (
    <>
      <SiteHeader />

      <nav className="cb_nav" aria-label="Main navigation">
        <div className="cb_nav__inner">
          <ul className="cb_nav__list">
            <li className="cb_nav__item">
              <NavLink to="/" end className={({ isActive }) =>
                `cb_nav__link${isActive ? ' cb_nav__link--active' : ''}`
              }><LayoutDashboard /> Home</NavLink>
            </li>
            <li className="cb_nav__item">
              <NavLink to="/kb" className={({ isActive }) =>
                `cb_nav__link${isActive ? ' cb_nav__link--active' : ''}`
              }><BookOpen /> Knowledge Base</NavLink>
            </li>
            <li className="cb_nav__item">
              <NavLink to="/status" className={({ isActive }) =>
                `cb_nav__link${isActive ? ' cb_nav__link--active' : ''}`
              }><Activity /> Status</NavLink>
            </li>
            <li className="cb_nav__item">
              <NavLink to="/actions" className={({ isActive }) =>
                `cb_nav__link${isActive ? ' cb_nav__link--active' : ''}`
              }><Zap /> Actions</NavLink>
            </li>
          </ul>

          {user && (
            <div className="cb_nav-user">
              <span className="cb_nav-user__name">{user.name}</span>
              <StatusTag colour={roleColour}>{label}</StatusTag>
              <button className="cb_nav-user__logout" onClick={logout}><LogOut /> Sign out</button>
            </div>
          )}
        </div>
      </nav>

      <main className="cb_wrapper cb_page">
        <Outlet />
      </main>

      <footer className="cb_wrapper cb_footer">
        CommandBridge — Scottish Government Digital Identity
      </footer>
    </>
  );
}
