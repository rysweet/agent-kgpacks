/**
 * Application entry point
 *
 * Renders React app. Service worker registration is handled
 * automatically by vite-plugin-pwa (see vite.config.ts).
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
