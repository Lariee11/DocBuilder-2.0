import { useState, useRef, useCallback } from 'react'
import * as XLSX from 'xlsx'
import newLogo from '@/imports/magic_edit_TUFIUXNoeUZoMTgjMSNkOWFjYWZkOTg2ZTYyMGE5YzM0YWZjNTkyOTQ2MTUzNSM3ODgjI1RSQU5TRk9STUFUSU9OX1JFUVVFU1Q.png'

// Colour tokens (blue + green from logo)
const C = {
  bg: '#080d1c',
  sidebar: '#0a0f20',
  card: '#0e1528',
  cardBorder: 'rgba(59,130,246,0.12)',
  blue: '#3b82f6',
  blueLight: '#60a5fa',
  blueDim: 'rgba(59,130,246,0.12)',
  blueBorder: 'rgba(59,130,246,0.25)',
  green: '#22c55e',
  greenDim: 'rgba(34,197,94,0.12)',
  greenBorder: 'rgba(34,197,94,0.25)',
  text: '#e2e8f0',
  muted: '#64748b',
  subtle: '#1e2a42',
  divider: 'rgba(255,255,255,0.06)',
}

// Shared input className
const inputCls =
  'w-full rounded px-3 py-2.5 text-sm outline-none transition-all placeholder-[#374151]'
const inputStyle = {
  background: '#0b1122',
  border: `1px solid ${C.subtle}`,
  color: C.text,
}

const focusHandlers = (el: HTMLInputElement | HTMLTextAreaElement | null) => {
  if (!el) return
  el.addEventListener('focus', () => {
    el.style.borderColor = C.blue
    el.style.boxShadow = `0 0 0 2px ${C.blueDim}`
  })
  el.addEventListener('blur', () => {
    el.style.borderColor = C.subtle
    el.style.boxShadow = 'none'
  })
}

// Types
interface Page1 { pdflatexPath: string; documentTitle: string; fileName: string; documentCode: string }
interface Page2 { distributor: string; lastEditDate: string; technicalResponsible: string; revision: string }
interface ListItem { id: number; value: string }
interface Page3 { technicalReferences: ListItem[]; projectObjective: string; projectScope: ListItem[]; requirements: ListItem[]; detailedLogic: string }
type TableRow = Record<string, string>
interface DynTable { columns: string[]; rows: TableRow[] }
interface Annex { id: number; file: File | null; preview: string | null; title: string; description: string }

let _id = 1
const uid = () => _id++
const makeItem = (value = ''): ListItem => ({ id: uid(), value })
const makeRow = (cols: string[]): TableRow => Object.fromEntries(cols.map((c) => [c, '']))
const makeAnnex = (): Annex => ({ id: uid(), file: null, preview: null, title: '', description: '' })

// Field wrapper
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline gap-2">
        <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: C.blue }}>
          {label}
        </label>
        {hint && <span className="text-xs" style={{ color: C.muted }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

// Dynamic list
function DynamicList({ label, hint, items, onChange }: { label: string; hint: string; items: ListItem[]; onChange: (i: ListItem[]) => void }) {
  const update = (id: number, value: string) => onChange(items.map((it) => (it.id === id ? { ...it, value } : it)))
  const remove = (id: number) => onChange(items.filter((it) => it.id !== id))
  const add = () => onChange([...items, makeItem()])

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: C.blue }}>{label}</span>
        <span className="text-xs" style={{ color: C.muted }}>{hint}</span>
      </div>
      {items.map((item, idx) => (
        <div key={item.id} className="flex items-center gap-2 group">
          <span className="text-xs w-5 text-right shrink-0 select-none" style={{ color: C.muted, fontFamily: 'JetBrains Mono,monospace' }}>{idx + 1}.</span>
          <input
            type="text" value={item.value} placeholder={`Item ${idx + 1}`}
            onChange={(e) => update(item.id, e.target.value)}
            className={inputCls} style={inputStyle}
            ref={focusHandlers as never}
          />
          <button onClick={() => remove(item.id)} className="opacity-0 group-hover:opacity-100 transition-all w-6 h-6 flex items-center justify-center shrink-0 hover:text-red-400" style={{ color: C.muted }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
          </button>
        </div>
      ))}
      <button onClick={add} className="mt-1 self-start flex items-center gap-1.5 text-xs font-medium transition-colors hover:opacity-80" style={{ color: C.blue }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        Adicionar linha
      </button>
    </div>
  )
}

// Dynamic table
function DynamicTable({ label, table, onChange }: { label: string; table: DynTable; onChange: (t: DynTable) => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const addRow = () => onChange({ ...table, rows: [...table.rows, makeRow(table.columns)] })
  const removeRow = (idx: number) => onChange({ ...table, rows: table.rows.filter((_, i) => i !== idx) })
  const setCell = (rowIdx: number, col: string, val: string) => {
    const rows = table.rows.map((r, i) => i === rowIdx ? { ...r, [col]: val } : r)
    onChange({ ...table, rows })
  }

  const handleExcel = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const wb = XLSX.read(ev.target?.result, { type: 'binary' })
        const ws = wb.Sheets[wb.SheetNames[0]]
        const data = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws, { header: 1 }) as unknown[][]
        // skip header row, map to table columns
        const newRows: TableRow[] = data.slice(1).map((row) =>
          Object.fromEntries(table.columns.map((col, i) => [col, String(row[i] ?? '')]))
        )
        if (newRows.length) onChange({ ...table, rows: newRows })
      } catch {
        alert('Não foi possível ler o arquivo Excel.')
      }
    }
    reader.readAsBinaryString(file)
    e.target.value = ''
  }, [table, onChange])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: C.blue }}>{label}</span>
        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleExcel} />
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded transition-all hover:opacity-80"
            style={{ background: C.greenDim, border: `1px solid ${C.greenBorder}`, color: C.green }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
              <path d="M3.5 4.5L5.5 7l1-1.5L8.5 8" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Importar Excel
          </button>
          <button
            onClick={addRow}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded transition-all hover:opacity-80"
            style={{ background: C.blueDim, border: `1px solid ${C.blueBorder}`, color: C.blue }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            Adicionar linha
          </button>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg" style={{ border: `1px solid ${C.cardBorder}` }}>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr style={{ background: '#0b1530' }}>
              <th className="text-center text-xs py-2.5 px-2 w-8" style={{ color: C.muted, borderBottom: `1px solid ${C.subtle}` }}>#</th>
              {table.columns.map((col) => (
                <th key={col} className="text-left text-xs font-semibold py-2.5 px-3 tracking-wide" style={{ color: C.blueLight, borderBottom: `1px solid ${C.subtle}` }}>
                  {col}
                </th>
              ))}
              <th className="w-8" style={{ borderBottom: `1px solid ${C.subtle}` }} />
            </tr>
          </thead>
          <tbody>
            {table.rows.length === 0 && (
              <tr>
                <td colSpan={table.columns.length + 2} className="text-center py-6 text-xs" style={{ color: C.muted }}>
                  Nenhuma linha - clique em "Adicionar linha" ou importe um Excel.
                </td>
              </tr>
            )}
            {table.rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="group" style={{ borderBottom: `1px solid ${C.divider}` }}>
                <td className="text-center text-xs py-1.5 px-2 select-none" style={{ color: C.muted, fontFamily: 'JetBrains Mono,monospace' }}>{rowIdx + 1}</td>
                {table.columns.map((col) => (
                  <td key={col} className="px-1.5 py-1">
                    <input
                      type="text" value={row[col]} placeholder=""
                      onChange={(e) => setCell(rowIdx, col, e.target.value)}
                      className="w-full rounded px-2 py-1 text-xs outline-none transition-all"
                      style={{ background: 'transparent', border: '1px solid transparent', color: C.text }}
                      onFocus={(e) => { e.target.style.background = '#0b1122'; e.target.style.borderColor = C.blue }}
                      onBlur={(e) => { e.target.style.background = 'transparent'; e.target.style.borderColor = 'transparent' }}
                    />
                  </td>
                ))}
                <td className="px-2">
                  <button onClick={() => removeRow(rowIdx)} className="opacity-0 group-hover:opacity-100 transition-all w-5 h-5 flex items-center justify-center hover:text-red-400" style={{ color: C.muted }}>
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1 1l8 8M9 1L1 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs" style={{ color: C.muted }}>{table.rows.length} {table.rows.length === 1 ? 'linha' : 'linhas'}</p>
    </div>
  )
}

// Annexes
function AnnexesSection({ annexes, onChange }: { annexes: Annex[]; onChange: (a: Annex[]) => void }) {
  const add = () => onChange([...annexes, makeAnnex()])
  const remove = (id: number) => onChange(annexes.filter((a) => a.id !== id))
  const update = (id: number, patch: Partial<Annex>) => onChange(annexes.map((a) => a.id === id ? { ...a, ...patch } : a))

  const handleImage = (id: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const preview = URL.createObjectURL(file)
    update(id, { file, preview })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: C.blue }}>Anexos</span>
        <button onClick={add} className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded transition-all hover:opacity-80" style={{ background: C.blueDim, border: `1px solid ${C.blueBorder}`, color: C.blue }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
          Adicionar anexo
        </button>
      </div>
      {annexes.length === 0 && (
        <p className="text-xs text-center py-8" style={{ color: C.muted }}>Nenhum anexo - clique em "Adicionar anexo".</p>
      )}
      {annexes.map((annex, idx) => (
        <div key={annex.id} className="rounded-xl p-5 flex gap-5" style={{ background: '#0b1122', border: `1px solid ${C.cardBorder}` }}>
          {/* Image picker */}
          <div className="shrink-0">
            <input
              type="file" accept="image/*" id={`annex-img-${annex.id}`} className="hidden"
              onChange={(e) => handleImage(annex.id, e)}
            />
            <label
              htmlFor={`annex-img-${annex.id}`}
              className="flex flex-col items-center justify-center cursor-pointer rounded-lg transition-all hover:opacity-80 overflow-hidden"
              style={{ width: 96, height: 96, background: C.subtle, border: `1.5px dashed ${C.blueBorder}` }}
            >
              {annex.preview ? (
                <img src={annex.preview} alt="preview" className="w-full h-full object-cover" />
              ) : (
                <>
                  <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="mb-1">
                    <rect x="2" y="5" width="18" height="14" rx="2" stroke={C.blue} strokeWidth="1.3" />
                    <circle cx="7.5" cy="10" r="1.5" stroke={C.blue} strokeWidth="1.2" />
                    <path d="M2 16l5-4 3 3 3-2 7 5" stroke={C.blue} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M11 2v4M9 3l2-2 2 2" stroke={C.blue} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="text-xs" style={{ color: C.blue }}>Selecionar</span>
                </>
              )}
            </label>
          </div>
          {/* Fields */}
          <div className="flex-1 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold" style={{ color: C.muted, fontFamily: 'JetBrains Mono,monospace' }}>Anexo {idx + 1}</span>
              <button onClick={() => remove(annex.id)} className="hover:text-red-400 transition-colors" style={{ color: C.muted }}>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
              </button>
            </div>
            <input
              type="text" value={annex.title} placeholder="Título do anexo"
              onChange={(e) => update(annex.id, { title: e.target.value })}
              className={inputCls} style={inputStyle}
              onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
              onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }}
            />
            <textarea
              value={annex.description} placeholder="Descrição do anexo..." rows={3}
              onChange={(e) => update(annex.id, { description: e.target.value })}
              className={inputCls + ' leading-relaxed'} style={inputStyle}
              onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
              onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

// Pages
function Page1({ data, onChange }: { data: Page1; onChange: (d: Partial<Page1>) => void }) {
  const mono = { fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem' }
  return (
    <div className="flex flex-col gap-7">
      <Field label="Endereço do PDFLaTeX" hint="Caminho absoluto do executável">
        <input type="text" value={data.pdflatexPath} placeholder="/usr/local/texlive/2024/bin/x86_64-linux/pdflatex"
          onChange={(e) => onChange({ pdflatexPath: e.target.value })}
          className={inputCls} style={{ ...inputStyle, ...mono }}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Título do Documento">
        <input type="text" value={data.documentTitle} placeholder="Ex.: Relatório de Análise de Requisitos – Sistema XYZ"
          onChange={(e) => onChange({ documentTitle: e.target.value })}
          className={inputCls} style={inputStyle}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Nome do Arquivo" hint=".tex / .pdf - sem extensão">
        <input type="text" value={data.fileName} placeholder="relatorio_analise_xyz"
          onChange={(e) => onChange({ fileName: e.target.value })}
          className={inputCls} style={{ ...inputStyle, ...mono }}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Código do Documento" hint="Identificador único">
        <input type="text" value={data.documentCode} placeholder="DOC-2024-001"
          onChange={(e) => onChange({ documentCode: e.target.value })}
          className={`${inputCls} max-w-xs`} style={{ ...inputStyle, ...mono }}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
    </div>
  )
}

function Page2({ data, onChange }: { data: Page2; onChange: (d: Partial<Page2>) => void }) {
  return (
    <div className="flex flex-col gap-7">
      <Field label="Distribuidora" hint="Nome da empresa ou entidade">
        <input type="text" value={data.distributor} placeholder="Ex.: Companhia Energética do Estado - CEEE"
          onChange={(e) => onChange({ distributor: e.target.value })}
          className={inputCls} style={inputStyle}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Data da Última Edição">
        <input type="date" value={data.lastEditDate}
          onChange={(e) => onChange({ lastEditDate: e.target.value })}
          className={`${inputCls} w-full`} style={{ ...inputStyle, colorScheme: 'dark' } as React.CSSProperties}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Responsável Técnico">
        <input type="text" value={data.technicalResponsible} placeholder="Ex.: Eng. Ana Beatriz Ferreira - CREA 123456/RS"
          onChange={(e) => onChange({ technicalResponsible: e.target.value })}
          className={inputCls} style={inputStyle}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <Field label="Revisão" hint="Número ou código">
        <input type="text" value={data.revision} placeholder="Rev. 00"
          onChange={(e) => onChange({ revision: e.target.value })}
          className={`${inputCls} max-w-xs`}
          style={{ ...inputStyle, fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem' }}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
    </div>
  )
}

// Descrição detalhada: revisada automaticamente (gramática e linguagem técnica) ao sair do campo
function DetailedLogicField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [original, setOriginal] = useState<string | null>(null)
  const lastReviewed = useRef(value)

  const review = async (text: string) => {
    if (!text.trim() || text === lastReviewed.current) return
    setStatus('loading')
    setMessage('')
    const formData = new FormData()
    formData.append('texto', text)
    try {
      const response = await fetch('http://localhost:8000/melhorar-texto', { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok) {
        lastReviewed.current = text
        setStatus('error')
        setMessage(data.detail || 'Não foi possível revisar o texto.')
        return
      }
      lastReviewed.current = data.texto
      setOriginal(text)
      onChange(data.texto)
      setStatus('done')
    } catch (err) {
      console.error(err)
      setStatus('error')
      setMessage('Erro de conexão com o servidor local.')
    }
  }

  const undo = () => {
    if (original === null) return
    lastReviewed.current = original
    onChange(original)
    setOriginal(null)
    setStatus('idle')
  }

  return (
    <Field label="Descrição Detalhada da Lógica" hint="Ao sair do campo, o texto é revisado automaticamente (gramática e linguagem técnica)">
      <textarea value={value} readOnly={status === 'loading'}
        placeholder="Descreva o que foi realizado e por quê. O texto será revisado sem alterar o conteúdo..."
        onChange={(e) => { onChange(e.target.value); if (status === 'done') setStatus('idle') }}
        rows={8} className={`${inputCls} leading-relaxed`} style={{ ...inputStyle, opacity: status === 'loading' ? 0.6 : 1 }}
        onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
        onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none'; review(e.target.value) }} />
      {status === 'loading' && <span className="text-xs" style={{ color: C.blue }}>Revisando o texto...</span>}
      {status === 'done' && (
        <span className="text-xs flex items-center gap-2" style={{ color: C.green }}>
          Texto revisado automaticamente.
          <button onClick={undo} className="underline hover:opacity-80" style={{ color: C.blueLight }}>Desfazer</button>
        </span>
      )}
      {status === 'error' && <span className="text-xs" style={{ color: '#fbbf24' }}>{message}</span>}
    </Field>
  )
}

function Page3({ data, onChange }: { data: Page3; onChange: (d: Partial<Page3>) => void }) {
  return (
    <div className="flex flex-col gap-8">
      <DynamicList label="Referências Técnicas" hint="Normas, documentos, padrões"
        items={data.technicalReferences} onChange={(items) => onChange({ technicalReferences: items })} />
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <Field label="Objetivo do Projeto">
        <textarea value={data.projectObjective}
          placeholder="Descreva o objetivo principal do projeto de forma clara e objetiva..."
          onChange={(e) => onChange({ projectObjective: e.target.value })}
          rows={5} className={`${inputCls} leading-relaxed`} style={inputStyle}
          onFocus={(e) => { e.target.style.borderColor = C.blue; e.target.style.boxShadow = `0 0 0 2px ${C.blueDim}` }}
          onBlur={(e) => { e.target.style.borderColor = C.subtle; e.target.style.boxShadow = 'none' }} />
      </Field>
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <DynamicList label="Escopo do Projeto" hint="Delimite o que está incluso"
        items={data.projectScope} onChange={(items) => onChange({ projectScope: items })} />
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <DynamicList label="Requisitos" hint="Funcionais e não funcionais"
        items={data.requirements} onChange={(items) => onChange({ requirements: items })} />
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <DetailedLogicField value={data.detailedLogic} onChange={(v) => onChange({ detailedLogic: v })} />
    </div>
  )
}

function Page4({ data, onChange }: { data: { logica: DynTable; goose: DynTable }; onChange: (d: Partial<typeof data>) => void }) {
  return (
    <div className="flex flex-col gap-10">
      <DynamicTable label="Adaptações Lógicas"
        table={data.logica} onChange={(t) => onChange({ logica: t })} />
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <DynamicTable label="Matriz GOOSE"
        table={data.goose} onChange={(t) => onChange({ goose: t })} />
    </div>
  )
}

function Page5({ data, onChange }: { data: { sinalizacoes: DynTable; testes: DynTable }; onChange: (d: Partial<typeof data>) => void }) {
  return (
    <div className="flex flex-col gap-10">
      <DynamicTable label="Sinalizações"
        table={data.sinalizacoes} onChange={(t) => onChange({ sinalizacoes: t })} />
      <div style={{ borderTop: `1px solid ${C.divider}` }} />
      <DynamicTable label="Testes de Validação"
        table={data.testes} onChange={(t) => onChange({ testes: t })} />
    </div>
  )
}

function Page6({ annexes, onChange }: { annexes: Annex[]; onChange: (a: Annex[]) => void }) {
  return <AnnexesSection annexes={annexes} onChange={onChange} />
}

// Importação dos arquivos SEL (.rdb / .scd)
type SelFileKey = 'rdb_backup' | 'rdb_novo' | 'scd_backup' | 'scd_novo'
interface SelFiles { rdb_backup: File | null; rdb_novo: File | null; scd_backup: File | null; scd_novo: File | null }
interface SelResult {
  logica: TableRow[]
  goose: TableRow[]
  sinalizacoes: TableRow[]
  avisos: string[]
}

const SEL_FILE_SLOTS: { key: SelFileKey; label: string; hint: string; accept: string; required?: boolean }[] = [
  { key: 'rdb_backup', label: 'Ajustes - Backup', hint: '.rdb antes das alterações', accept: '.rdb' },
  { key: 'rdb_novo', label: 'Ajustes - Novo', hint: '.rdb com as lógicas desenvolvidas', accept: '.rdb', required: true },
  { key: 'scd_backup', label: 'SCD - Backup', hint: '.scd antes das alterações (opcional)', accept: '.scd,.xml' },
  { key: 'scd_novo', label: 'SCD - Novo', hint: '.scd com os GOOSEs implementados', accept: '.scd,.xml' },
]

function FileSlot({ label, hint, accept, required, file, onChange }: {
  label: string; hint: string; accept: string; required?: boolean; file: File | null; onChange: (f: File | null) => void
}) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <div className="rounded-lg p-4 flex flex-col gap-2" style={{ background: '#0b1122', border: `1px solid ${file ? C.greenBorder : C.cardBorder}` }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: C.blue }}>
          {label}{required && <span style={{ color: C.green }}> *</span>}
        </span>
        <span className="text-xs" style={{ color: C.muted }}>{hint}</span>
      </div>
      <input ref={ref} type="file" accept={accept} className="hidden"
        onChange={(e) => { onChange(e.target.files?.[0] ?? null); e.target.value = '' }} />
      <div className="flex items-center gap-2">
        <button onClick={() => ref.current?.click()}
          className="text-xs px-2.5 py-1.5 rounded transition-all hover:opacity-80 shrink-0"
          style={{ background: C.blueDim, border: `1px solid ${C.blueBorder}`, color: C.blue }}>
          Selecionar arquivo
        </button>
        <span className="text-xs truncate" style={{ color: file ? C.text : C.muted, fontFamily: 'JetBrains Mono,monospace' }}>
          {file ? file.name : 'Nenhum arquivo'}
        </span>
        {file && (
          <button onClick={() => onChange(null)} className="ml-auto hover:text-red-400 transition-colors" style={{ color: C.muted }} title="Remover">
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
          </button>
        )}
      </div>
    </div>
  )
}

function SelImportPage({ hasExistingData, onResult }: {
  hasExistingData: boolean
  onResult: (r: SelResult) => void
}) {
  const [files, setFiles] = useState<SelFiles>({ rdb_backup: null, rdb_novo: null, scd_backup: null, scd_novo: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SelResult | null>(null)

  const analyze = async () => {
    if (!files.rdb_novo) {
      setError('Selecione pelo menos o arquivo .rdb novo.')
      return
    }
    if (hasExistingData && !confirm('As tabelas de Lógicas, GOOSE e Sinalizações atuais serão substituídas. Continuar?')) return
    setError('')
    setLoading(true)
    const formData = new FormData()
    ;(Object.keys(files) as SelFileKey[]).forEach((k) => { if (files[k]) formData.append(k, files[k] as File) })
    try {
      const response = await fetch('http://localhost:8000/analisar-arquivos', { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok) {
        setError(data.detail || 'Erro ao analisar os arquivos.')
        return
      }
      setResult(data)
      onResult(data)
    } catch (err) {
      console.error(err)
      setError('Erro de conexão com o servidor local.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-7">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {SEL_FILE_SLOTS.map((slot) => (
          <FileSlot key={slot.key} label={slot.label} hint={slot.hint} accept={slot.accept} required={slot.required} file={files[slot.key]}
            onChange={(f) => setFiles((p) => ({ ...p, [slot.key]: f }))} />
        ))}
      </div>

      <div className="flex justify-end">
        <button onClick={analyze} disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-wait"
          style={{ background: C.green, color: '#0b1122' }}>
          {loading ? 'Analisando...' : 'Analisar e gerar tabelas'}
        </button>
      </div>

      {error && (
        <p className="text-xs rounded px-3 py-2" style={{ color: '#fca5a5', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>{error}</p>
      )}

      {result && (
        <div className="flex flex-col gap-3 rounded-lg p-4" style={{ background: '#0b1122', border: `1px solid ${C.greenBorder}` }}>
          <p className="text-xs" style={{ color: C.green }}>
            {result.logica.length} lógica(s) e {result.goose.length} sinal(is) GOOSE adicionados na página "Lógica & GOOSE";
            {' '}{result.sinalizacoes.length} ponto(s) novo(s) do mapa DNP adicionados em "Sinalizações" (página "Sinais & Testes").
          </p>
          {result.avisos.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: '#fbbf24' }}>Pontos de atenção</span>
              <ul className="list-disc pl-5 flex flex-col gap-1">
                {result.avisos.map((a, i) => <li key={i} className="text-xs" style={{ color: C.text }}>{a}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Sidebar
const PAGES = [
  { num: 1, title: 'Configuração', sub: 'Metadados do documento' },
  { num: 2, title: 'Autoria', sub: 'Responsáveis e revisão' },
  { num: 3, title: 'Conteúdo', sub: 'Seções técnicas' },
  { num: 4, title: 'Arquivos SEL', sub: 'Leitura dos .rdb e .scd' },
  { num: 5, title: 'Lógica & GOOSE', sub: 'Adaptações e matriz' },
  { num: 6, title: 'Sinais & Testes', sub: 'Sinalizações e validação' },
  { num: 7, title: 'Anexos', sub: 'Imagens e arquivos' },
]

function Sidebar({ current, onNav, onGenerateDocs, onLoadJson }: {
  current: number
  onNav: (p: number) => void
  onGenerateDocs: () => void
  onLoadJson: (file: File) => void
}) {
  const jsonRef = useRef<HTMLInputElement>(null)
  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 flex flex-col" style={{ background: C.sidebar, borderRight: `1px solid ${C.cardBorder}` }}>
      {/* Logo */}
      <div className="flex items-center justify-center px-4 pt-5 pb-5" style={{ borderBottom: `1px solid ${C.divider}` }}>
        <img src={newLogo} alt="DocBuilder" className="object-contain" style={{ width: 140, height: 'auto' }} />
      </div>
      {/* Steps */}
      <nav className="flex-1 px-3 py-5 flex flex-col gap-1 overflow-y-auto">
        {PAGES.map((page) => {
          const active = current === page.num
          const done = current > page.num
          return (
            <button key={page.num} onClick={() => onNav(page.num)}
              className="flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-all w-full"
              style={{ background: active ? C.blueDim : 'transparent', border: `1px solid ${active ? C.blueBorder : 'transparent'}` }}>
              <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-xs font-semibold transition-all"
                style={{
                  background: done ? C.green : active ? C.blueDim : 'rgba(255,255,255,0.04)',
                  border: active && !done ? `1px solid ${C.blue}` : done ? 'none' : '1px solid rgba(255,255,255,0.08)',
                  color: done ? '#0b1122' : active ? C.blue : C.muted,
                  fontSize: '0.65rem',
                }}>
                {done ? (
                  <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1.5 4.5l2 2 4-4" stroke="#0b1122" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                ) : page.num}
              </div>
              <div>
                <div className="text-xs font-medium transition-colors" style={{ color: active ? C.blue : done ? '#94a3b8' : C.muted }}>{page.title}</div>
                <div className="text-xs mt-0.5" style={{ color: '#334155', fontSize: '0.68rem' }}>{page.sub}</div>
              </div>
            </button>
          )
        })}
      </nav>
      {/* Bottom action buttons */}
      <div className="px-3 pb-5 pt-3 flex flex-col gap-2" style={{ borderTop: `1px solid ${C.divider}` }}>
        <input ref={jsonRef} type="file" accept=".json" className="hidden"
          onChange={(e) => {
            if (e.target.files?.[0]) {
              onLoadJson(e.target.files[0])
              e.target.value = ''
            }
          }} />
        <button onClick={() => jsonRef.current?.click()}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all hover:opacity-80"
          style={{ background: C.greenDim, border: `1px solid ${C.greenBorder}`, color: C.green }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M2 2.5A1.5 1.5 0 013.5 1H8l3 3v7A1.5 1.5 0 019.5 12h-6A1.5 1.5 0 012 10.5v-8z" stroke="currentColor" strokeWidth="1.2" />
            <path d="M8 1v3h3M4.5 7.5h4M4.5 9.5h2.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
          </svg>
          Carregar JSON
        </button>
        <button onClick={onGenerateDocs}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold transition-all hover:opacity-90 active:scale-95"
          style={{ background: C.blue, color: '#fff' }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 1v7M4 6l2.5 2.5L9 6M2 10v1.5A.5.5 0 002.5 12h8a.5.5 0 00.5-.5V10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Gerar Documentação
        </button>
      </div>
    </aside>
  )
}

// App
export default function App() {
  const [currentPage, setCurrentPage] = useState(1)

  const [page1, setPage1] = useState<Page1>({ pdflatexPath: '', documentTitle: '', fileName: '', documentCode: '' })
  const [page2, setPage2] = useState<Page2>({ distributor: '', lastEditDate: '', technicalResponsible: '', revision: '' })
  const [page3, setPage3] = useState<Page3>({
    technicalReferences: [makeItem(), makeItem()],
    projectObjective: '',
    projectScope: [makeItem(), makeItem()],
    requirements: [makeItem(), makeItem()],
    detailedLogic: '',
  })
  const [page4, setPage4] = useState({
    logica: { columns: ['Equipamento', 'Variável', 'Equação Lógica', 'Descrição'], rows: [] as TableRow[] },
    goose: { columns: ['Publicador', 'Assinante', 'MAC Mensagem', 'Virtual Bit', 'Variável'], rows: [] as TableRow[] },
  })
  const [page5, setPage5] = useState({
    sinalizacoes: { columns: ['Equipamento', 'Tipo do Ponto', 'Variável', 'Descrição', 'Funcionamento'], rows: [] as TableRow[] },
    testes: { columns: ['ID', 'Cenário', 'Resultado Esperado'], rows: [] as TableRow[] },
  })
  const [annexes, setAnnexes] = useState<Annex[]>([])

  const handleSelResult = (r: SelResult) => {
    setPage4((p) => ({ logica: { ...p.logica, rows: r.logica }, goose: { ...p.goose, rows: r.goose } }))
    setPage5((p) => ({ ...p, sinalizacoes: { ...p.sinalizacoes, rows: r.sinalizacoes } }))
  }

  const pageMeta: Record<number, { title: string; sub: string }> = {
    1: { title: 'Configuração do Documento', sub: 'Metadados e caminhos de compilação' },
    2: { title: 'Autoria e Revisão', sub: 'Distribuidora, responsável e controle de versão' },
    3: { title: 'Conteúdo Técnico', sub: 'Referências, objetivos, escopo e lógica' },
    4: { title: 'Arquivos SEL', sub: 'Preenche as tabelas de lógicas, GOOSE e sinalizações a partir dos .rdb e .scd' },
    5: { title: 'Lógica & Matriz GOOSE', sub: 'Adaptações lógicas e publicações GOOSE' },
    6: { title: 'Sinalizações & Testes', sub: 'Pontos de sinalização e validação' },
    7: { title: 'Anexos', sub: 'Imagens e documentos complementares' },
  }

  const handleLoadJson = (file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string)

        setPage1({
          pdflatexPath: data["Compilador"] || '',
          documentTitle: data["Titulo da Documentação"] || '',
          fileName: data["Nome do Arquivo"] || '',
          documentCode: data["Código da Documentação"] || ''
        })
        setPage2({
          distributor: data["Nome do Projeto"] || '',
          // Converte DD/MM/AAAA de volta para o input date do React (AAAA-MM-DD)
          lastEditDate: data["Data de Alteração"] ? data["Data de Alteração"].split('/').reverse().join('-') : '',
          technicalResponsible: data["Responsável Técnico"] || '',
          revision: data["Revisão"] || ''
        })
        setPage3({
          technicalReferences: (data["Referências Técnicas"] || []).map((val: string) => makeItem(val)),
          projectObjective: data["Objetivo"] || '',
          projectScope: (data["Escopo do Projeto"] || []).map((val: string) => makeItem(val)),
          requirements: (data["Requisitos"] || []).map((val: string) => makeItem(val)),
          detailedLogic: data["Descrição Detalhada"] || ''
        })

        if (data["Adaptações Lógicas"]) setPage4(p => ({ ...p, logica: { ...p.logica, rows: data["Adaptações Lógicas"] } }))
        if (data["Matriz GOOSE"]) setPage4(p => ({ ...p, goose: { ...p.goose, rows: data["Matriz GOOSE"] } }))
        if (data["Sinalizações"]) setPage5(p => ({ ...p, sinalizacoes: { ...p.sinalizacoes, rows: data["Sinalizações"] } }))
        if (data["Testes de Validação"]) setPage5(p => ({ ...p, testes: { ...p.testes, rows: data["Testes de Validação"] } }))

        alert('JSON carregado com sucesso!')
      } catch (error) {
        alert('Erro ao ler o arquivo JSON.')
      }
    }
    reader.readAsText(file)
  }

  const handleGenerateDocs = async () => {
    const payload = {
      "Compilador": page1.pdflatexPath,
      "Titulo da Documentação": page1.documentTitle,
      "Nome do Arquivo": page1.fileName,
      "Nome do Projeto": page2.distributor,
      "Código da Documentação": page1.documentCode,
      // Converte a data AAAA-MM-DD para DD/MM/AAAA antes de enviar para o backend
      "Data de Alteração": page2.lastEditDate ? page2.lastEditDate.split('-').reverse().join('/') : '',
      "Responsável Técnico": page2.technicalResponsible,
      "Revisão": page2.revision,
      "Referências Técnicas": page3.technicalReferences.map(i => i.value),
      "Objetivo": page3.projectObjective,
      "Escopo do Projeto": page3.projectScope.map(i => i.value),
      "Requisitos": page3.requirements.map(i => i.value),
      "Descrição Detalhada": page3.detailedLogic,
      "Adaptações Lógicas": page4.logica.rows,
      "Matriz GOOSE": page4.goose.rows,
      "Sinalizações": page5.sinalizacoes.rows,
      "Testes de Validação": page5.testes.rows
    }

    const formData = new FormData();
    formData.append('data', JSON.stringify(payload));

    annexes.forEach((annex) => {
      if (annex.file) {
        formData.append(`images`, annex.file);
        formData.append(`image_titles`, annex.title);
        formData.append(`image_descriptions`, annex.description);
      }
    });

    try {
      const response = await fetch('http://localhost:8000/gerar-documento', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        // PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${page1.fileName || 'documentacao'}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();

        // JSON
        const jsonBlob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const jsonUrl = window.URL.createObjectURL(jsonBlob);
        const aJson = document.createElement('a');
        aJson.href = jsonUrl;
        aJson.download = `${page1.fileName || 'documentacao'}.json`;
        document.body.appendChild(aJson);
        aJson.click();
        aJson.remove();

      } else {
        alert('Erro ao compilar o PDF no servidor LaTeX.');
      }
    } catch (error) {
      console.error(error);
      alert('Erro de conexão com o servidor local.');
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: C.bg }}>
      <Sidebar current={currentPage} onNav={setCurrentPage} onGenerateDocs={handleGenerateDocs} onLoadJson={handleLoadJson} />
      <main className="flex-1 ml-60 min-h-screen flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-10 flex items-center justify-between px-10 py-4"
          style={{ background: 'rgba(8,13,28,0.92)', borderBottom: `1px solid ${C.cardBorder}`, backdropFilter: 'blur(14px)' }}>
          <div>
            <h1 className="text-lg text-slate-100 leading-none" style={{ fontWeight: 300, letterSpacing: '-0.01em' }}>
              {pageMeta[currentPage].title}
            </h1>
            <p className="text-xs mt-1" style={{ color: C.muted }}>{pageMeta[currentPage].sub}</p>
          </div>
          <div className="text-xs font-semibold tracking-widest uppercase px-3 py-1.5 rounded"
            style={{ color: C.blue, background: C.blueDim, border: `1px solid ${C.blueBorder}`, fontFamily: 'JetBrains Mono,monospace' }}>
            {currentPage} / {PAGES.length}
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 px-10 py-10 max-w-4xl w-full mx-auto">
          <div className="rounded-xl p-8" style={{ background: C.card, border: `1px solid ${C.cardBorder}`, boxShadow: '0 2px 40px rgba(0,0,0,0.5)' }}>
            {currentPage === 1 && <Page1 data={page1} onChange={(d) => setPage1((p) => ({ ...p, ...d }))} />}
            {currentPage === 2 && <Page2 data={page2} onChange={(d) => setPage2((p) => ({ ...p, ...d }))} />}
            {currentPage === 3 && <Page3 data={page3} onChange={(d) => setPage3((p) => ({ ...p, ...d }))} />}
            {currentPage === 4 && (
              <SelImportPage onResult={handleSelResult}
                hasExistingData={page4.logica.rows.length > 0 || page4.goose.rows.length > 0 || page5.sinalizacoes.rows.length > 0} />
            )}
            {currentPage === 5 && <Page4 data={page4} onChange={(d) => setPage4((p) => ({ ...p, ...d }))} />}
            {currentPage === 6 && <Page5 data={page5} onChange={(d) => setPage5((p) => ({ ...p, ...d }))} />}
            {currentPage === 7 && <Page6 annexes={annexes} onChange={setAnnexes} />}
          </div>

          {/* Nav buttons */}
          <div className="flex items-center justify-between mt-8">
            <button onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={currentPage === 1}
              className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-all disabled:opacity-20 disabled:cursor-not-allowed"
              style={{ color: '#94a3b8', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M8 2L3 6.5l5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
              Anterior
            </button>
            <div className="flex gap-1.5 items-center">
              {PAGES.map((p) => (
                <button key={p.num} onClick={() => setCurrentPage(p.num)}
                  className="rounded-full transition-all"
                  style={{
                    width: currentPage === p.num ? 20 : 7,
                    height: 7,
                    background: currentPage === p.num ? C.blue : p.num < currentPage ? C.green : 'rgba(255,255,255,0.15)',
                  }} />
              ))}
            </div>
            {currentPage < PAGES.length ? (
              <button onClick={() => setCurrentPage((p) => Math.min(PAGES.length, p + 1))}
                className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition-all hover:opacity-90 active:scale-95"
                style={{ background: C.blue, color: '#fff' }}>
                Próxima
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M5 2l5 4.5L5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
            ) : (
              <button onClick={handleGenerateDocs}
                className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition-all hover:opacity-90 active:scale-95"
                style={{ background: C.green, color: '#0b1122' }}>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1v7M4 6l2.5 2.5L9 6M2 10v1.5A.5.5 0 002.5 12h8a.5.5 0 00.5-.5V10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /></svg>
                Gerar Documentação
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}