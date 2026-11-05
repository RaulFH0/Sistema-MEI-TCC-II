
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import LojaCliente from './components/LojaCliente'

import './index.css'

// ============================================================
// ENTRADA PRINCIPAL DO SISTEMA MEI
// ============================================================

// A funcao App controla:
// - / : Painel administrativo
// - /lojas/{slug} : Catalogo publico Multi-MEI
// - /lojas/{slug}/atendimento : Atendimento IA Multi-MEI
//
// Mantemos /loja como endereco legado do portal antigo.

const caminho =
  window.location.pathname.replace(/\/+$/, '') || '/'

const conteudo =
  caminho === '/loja' ? (
    <LojaCliente />
  ) : (
    <App />
  )

const elementoRaiz = document.getElementById('root')

if (!elementoRaiz) {
  throw new Error(
    'Elemento principal da aplicacao nao encontrado.'
  )
}

createRoot(elementoRaiz).render(
  <StrictMode>
    {conteudo}
  </StrictMode>
)
