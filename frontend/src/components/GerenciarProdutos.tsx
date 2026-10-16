
import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  cadastrarProduto,
  atualizarEstoque,
  configurarEstoqueMinimo,
  type Produto,
} from '../services/api'

type Props = {
  produtos: Produto[]
  aoAtualizar: () => Promise<void>
}

export default function GerenciarProdutos({
  produtos,
  aoAtualizar,
}: Props) {
  // ============================================================
  // ESTADOS DO CADASTRO DE PRODUTOS
  // ============================================================

  const [nome, setNome] = useState('')
  const [preco, setPreco] = useState('')
  const [quantidade, setQuantidade] = useState('')
  const [categoria, setCategoria] = useState('')
  const [descricao, setDescricao] = useState('')

  // ============================================================
  // ESTADOS DA ATUALIZACAO DE ESTOQUE
  // ============================================================

  const [produtoId, setProdutoId] = useState('')
  const [novoEstoque, setNovoEstoque] = useState('')

  // ============================================================
  // ESTADOS DO ESTOQUE MINIMO
  // ============================================================

  const [produtoMinimoId, setProdutoMinimoId] = useState('')
  const [novoMinimo, setNovoMinimo] = useState('')

  // ============================================================
  // ESTADOS GERAIS
  // ============================================================

  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')

  // ============================================================
  // CADASTRAR PRODUTO
  // ============================================================

  async function salvarCadastro(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()

    if (salvando) return

    const valorPreco = Number(preco)
    const valorQuantidade = Number(quantidade)

    if (
      !nome.trim() ||
      !preco.trim() ||
      !quantidade.trim() ||
      !Number.isFinite(valorPreco) ||
      valorPreco <= 0 ||
      !Number.isInteger(valorQuantidade) ||
      valorQuantidade < 0
    ) {
      setErro('Confira o nome, preço e quantidade informados.')
      setSucesso('')
      return
    }

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await cadastrarProduto({
        nome: nome.trim(),
        preco: valorPreco,
        quantidade: valorQuantidade,
        categoria: categoria.trim(),
        descricao: descricao.trim(),
      })

      setNome('')
      setPreco('')
      setQuantidade('')
      setCategoria('')
      setDescricao('')

      setSucesso('Produto cadastrado com sucesso!')
      await aoAtualizar()
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao cadastrar produto.'
      )
    } finally {
      setSalvando(false)
    }
  }

  // ============================================================
  // ATUALIZAR ESTOQUE
  // ============================================================

  async function salvarEstoque(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()

    if (salvando) return

    const id = Number(produtoId)
    const quantidadeFinal = Number(novoEstoque)

    if (
      !produtoId ||
      !novoEstoque.trim() ||
      !Number.isInteger(id) ||
      id <= 0 ||
      !Number.isInteger(quantidadeFinal) ||
      quantidadeFinal < 0
    ) {
      setErro('Selecione um produto e informe um estoque válido.')
      setSucesso('')
      return
    }

    const produto = produtos.find((item) => item.id === id)

    if (!produto) {
      setErro('Produto não encontrado na lista.')
      setSucesso('')
      return
    }

    const confirmado = window.confirm(
      `Alterar o estoque de "${produto.nome}" ` +
        `de ${produto.quantidade} para ${quantidadeFinal} unidades?`
    )

    if (!confirmado) return

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await atualizarEstoque(id, quantidadeFinal)

      setProdutoId('')
      setNovoEstoque('')

      setSucesso('Estoque atualizado com sucesso!')
      await aoAtualizar()
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao atualizar estoque.'
      )
    } finally {
      setSalvando(false)
    }
  }

  // ============================================================
  // CONFIGURAR ESTOQUE MINIMO
  // ============================================================

  async function salvarEstoqueMinimo(
    evento: FormEvent<HTMLFormElement>
  ) {
    evento.preventDefault()

    if (salvando) return

    const id = Number(produtoMinimoId)
    const minimo = Number(novoMinimo)

    if (
      !produtoMinimoId ||
      !novoMinimo.trim() ||
      !Number.isInteger(id) ||
      id <= 0 ||
      !Number.isInteger(minimo) ||
      minimo < 0
    ) {
      setErro('Selecione um produto e informe um limite válido.')
      setSucesso('')
      return
    }

    const produto = produtos.find((item) => item.id === id)

    if (!produto) {
      setErro('Produto não encontrado.')
      setSucesso('')
      return
    }

    const confirmado = window.confirm(
      `Alterar o estoque mínimo de "${produto.nome}" ` +
        `de ${produto.estoque_minimo} para ${minimo} unidades?`
    )

    if (!confirmado) return

    setSalvando(true)
    setErro('')
    setSucesso('')

    try {
      await configurarEstoqueMinimo(id, minimo)

      setProdutoMinimoId('')
      setNovoMinimo('')

      setSucesso('Estoque mínimo atualizado com sucesso!')
      await aoAtualizar()
    } catch (falha) {
      setErro(
        falha instanceof Error
          ? falha.message
          : 'Erro ao configurar estoque mínimo.'
      )
    } finally {
      setSalvando(false)
    }
  }

  // ============================================================
  // INTERFACE
  // ============================================================

  return (
    <section className="content-card" style={{ marginTop: 24 }}>
      <h2>Gerenciar produtos</h2>

      <p className="subtitle">
        Cadastre produtos, atualize quantidades e configure alertas
        de reposição.
      </p>

      {erro && (
        <div className="error-message" role="alert">
          {erro}
        </div>
      )}

      {sucesso && (
        <p role="status" style={{ color: '#16875f', fontWeight: 600 }}>
          {sucesso}
        </p>
      )}

      <div className="gerenciar-grid">
        {/* ====================================================
            FORMULARIO 1 - CADASTRO
           ==================================================== */}

        <form onSubmit={salvarCadastro}>
          <h3>Cadastrar novo produto</h3>

          <label>
            Nome
            <input
              type="text"
              required
              value={nome}
              onChange={(evento) => setNome(evento.target.value)}
            />
          </label>

          <label>
            Preço (R$)
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={preco}
              onChange={(evento) => setPreco(evento.target.value)}
            />
          </label>

          <label>
            Estoque inicial
            <input
              type="number"
              step="1"
              min="0"
              required
              value={quantidade}
              onChange={(evento) => setQuantidade(evento.target.value)}
            />
          </label>

          <label>
            Categoria
            <input
              type="text"
              value={categoria}
              onChange={(evento) => setCategoria(evento.target.value)}
            />
          </label>

          <label>
            Descrição
            <input
              type="text"
              value={descricao}
              onChange={(evento) => setDescricao(evento.target.value)}
            />
          </label>

          <button type="submit" disabled={salvando}>
            {salvando ? 'Aguarde...' : 'Cadastrar produto'}
          </button>
        </form>

        {/* ====================================================
            FORMULARIO 2 - ATUALIZACAO DE ESTOQUE
           ==================================================== */}

        <form onSubmit={salvarEstoque}>
          <h3>Atualizar estoque</h3>

          <label>
            Produto
            <select
              required
              value={produtoId}
              onChange={(evento) => setProdutoId(evento.target.value)}
            >
              <option value="">Selecione um produto</option>

              {produtos.map((produto) => (
                <option key={produto.id} value={produto.id}>
                  {produto.nome} — atual: {produto.quantidade}
                </option>
              ))}
            </select>
          </label>

          <label>
            Nova quantidade total
            <input
              type="number"
              step="1"
              min="0"
              required
              value={novoEstoque}
              onChange={(evento) => setNovoEstoque(evento.target.value)}
            />
          </label>

          <p className="subtitle">
            Atenção: este valor substitui a quantidade atual em
            estoque. Não representa uma quantidade a acrescentar.
          </p>

          <button type="submit" disabled={salvando}>
            {salvando ? 'Aguarde...' : 'Atualizar estoque'}
          </button>
        </form>

        {/* ====================================================
            FORMULARIO 3 - ESTOQUE MINIMO
           ==================================================== */}

        <form onSubmit={salvarEstoqueMinimo}>
          <h3>Configurar estoque mínimo</h3>

          <label>
            Produto
            <select
              required
              value={produtoMinimoId}
              onChange={(evento) =>
                setProdutoMinimoId(evento.target.value)
              }
            >
              <option value="">Selecione um produto</option>

              {produtos.map((produto) => (
                <option key={produto.id} value={produto.id}>
                  {produto.nome} — mínimo atual:{' '}
                  {produto.estoque_minimo}
                </option>
              ))}
            </select>
          </label>

          <label>
            Quantidade mínima
            <input
              type="number"
              min="0"
              step="1"
              required
              value={novoMinimo}
              onChange={(evento) => setNovoMinimo(evento.target.value)}
            />
          </label>

          <p className="subtitle">
            O sistema alertará quando a quantidade disponível
            ficar igual ou abaixo desse limite.
          </p>

          <p className="subtitle">
            Definir o mínimo como zero desativa o alerta de
            estoque baixo, mas mantém a identificação de
            produtos sem estoque.
          </p>

          <button type="submit" disabled={salvando}>
            {salvando ? 'Aguarde...' : 'Salvar estoque mínimo'}
          </button>
        </form>
      </div>
    </section>
  )
}
