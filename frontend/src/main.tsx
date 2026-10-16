
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import LojaCliente from './components/LojaCliente'

import './index.css'

// ============================================================
// DEFINICAO DO AMBIENTE
// ============================================================

const caminho = window.location.pathname.replace(/\/+$/, '') || '/'

const conteudo =
  caminho === '/loja' ? (
    <LojaCliente />
  ) : caminho === '/' ? (
    <App />
  ) : (
    <main style={{ padding: 32 }}>
      <h1>Página não encontrada</h1>
      <p>Verifique o endereço informado.</p>
    </main>
  )

createRoot(document.getElementById('root')!).render(
  <StrictMode>{conteudo}</StrictMode>
)
