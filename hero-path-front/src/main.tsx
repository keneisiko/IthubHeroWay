import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App.tsx'
import './index.css'
import { installTypingFx } from './lib/typingFx'
import { installSpotlight } from './lib/spotlight'

installTypingFx()
installSpotlight()

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#121212',
              color: '#f5f5f5',
              borderRadius: 14,
              fontFamily: 'Montserrat, sans-serif',
              fontWeight: 600,
              fontSize: 14,
            },
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)