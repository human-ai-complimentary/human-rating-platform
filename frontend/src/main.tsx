import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AppAuthProvider } from './auth';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppAuthProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppAuthProvider>
  </React.StrictMode>
);
