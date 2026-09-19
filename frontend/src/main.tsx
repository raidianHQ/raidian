import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthContext'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* basename tracks the same Vite `base` value the artwork resolver
        and the built index.html already use (Step 76) -- "/" locally
        and under any root/custom-domain deployment, or the configured
        GitHub Pages subpath when VITE_BASE_PATH is set at build time. */}
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
