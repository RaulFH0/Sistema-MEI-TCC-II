
import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  cadastrarProduto,
  atualizarEstoque,
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
  const [nome, setNome] = useState('')
  const [preco, setPreco] = useState('')
  const [quantidade, setQuantidade] = useState('')
  const [categoria, setCategoria] = useState('')
  const [descricao, setDescricao] = useState('')

  const [produtoId, setProdutoId] = useState('')
  const [novoEstoque, setNovoEstoque] = useState('')

  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')

  async function salvarCadastro(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()

    if (salvando) return

    const valorPreco = Number(preco)
    const valorQuantidade = Number(quantidade)

    if (
      !nome.trim() ||
      !Number.isFinite(valorPreco) ||
      valorPreco <= 0 ||
      !Number.isInteger(valorQuantidade) ||
      valorQuantidade < 0
    ) {
      setErro('Confira o nome, preço e quantidade informados.')
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

  async function salvarEstoque(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()

    if (salvando) return

    const id = Number(produtoId)
    const quantidadeFinal = Number(novoEstoque)

    if (
      !Number.isInteger(id) ||
      id <= 0 ||
      !novoEstoque.trim() ||
      !Number.isInteger(quantidadeFinal) ||
      quantidadeFinal < 0
    ) {
      setErro('Selecione um produto e informe um estoque válido.')
      return
    }

    const produto = produtos.find((item) => item.id === id)

    if (!produto) {
      setErro('Produto não encontrado na lista.')
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

  return (
    <section className="content-card" style={{ marginTop: 24 }}>
      <h2>Gerenciar produtos</h2>
      <p className="subtitle">
        Cadastre produtos ou defina a quantidade total em estoque.
      </p>

      {erro && <div className="error-message" role="alert">{erro}</div>}
      {sucesso && <p role="status">{sucesso}</p>}

      <div className="gerenciar-grid">
        <form onSubmit={salvarCadastro}>
          <h3>Cadastrar novo produto</h3>

          <label>
            Nome
            <input
              required
              value={nome}
              onChange={(e) => setNome(e.target.value)}
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
              onChange={(e) => setPreco(e.target.value)}
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
              onChange={(e) => setQuantidade(e.target.value)}
            />
          </label>

          <label>
            Categoria
            <input
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
            />
          </label>

          <label>
            Descrição
            <input
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
            />
          </label>

          <button type="submit" disabled={salvando}>
            Cadastrar produto
          </button>
        </form>

        <form onSubmit={salvarEstoque}>
          <h3>Atualizar estoque</h3>

          <label>
            Produto
            <select
              required
              value={produtoId}
              onChange={(e) => setProdutoId(e.target.value)}
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
              onChange={(e) => setNovoEstoque(e.target.value)}
            />
          </label>

          <p className="subtitle">
            Atenção: este valor substitui o estoque atual.
            Não representa uma quantidade a acrescentar.
          </p>

          <button type="submit" disabled={salvando}>
            Atualizar estoque
          </button>
        </form>
      </div>
    </section>
  )
}
