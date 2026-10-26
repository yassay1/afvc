import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { ArrowUp, Bot, ChevronRight, MessageSquarePlus } from 'lucide-react'
import { ApiError } from '../../shared/api/client'
import { getPendingActions, resolvePendingAction, sendTurn } from '../../shared/api/interaction'
import type { InteractionResponse } from '../../shared/api/types'
import { StateMessage } from '../../shared/components/StateMessage'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { createId } from '../../shared/id'
import { useAuthMe, useLogout } from '../../shared/query/auth'
import { useDataProfile } from '../../shared/query/dataProfile'
import './assistant.css'

const AssistantMarkdown = lazy(() => import('./AssistantMarkdown').then(({ AssistantMarkdown: Component }) => ({ default: Component })))

const storageKey = 'afvc.assistant.currentTab.v1'

interface Exchange { question: string; response: InteractionResponse }
interface StoredSession { sessionId: string; exchanges: Exchange[] }

function readSession(): StoredSession {
  try {
    const stored = JSON.parse(sessionStorage.getItem(storageKey) || 'null') as Partial<StoredSession> | null
    if (stored && typeof stored.sessionId === 'string' && Array.isArray(stored.exchanges)) {
      return { sessionId: stored.sessionId, exchanges: stored.exchanges }
    }
  } catch { /* Invalid tab data starts a new local transcript. */ }
  return { sessionId: createId(), exchanges: [] }
}

function errorMessage(error: unknown) {
  if (error instanceof DOMException && (error.name === 'TimeoutError' || error.name === 'AbortError')) return '本轮等待超时。服务端可能仍在处理，请核对待批状态后再决定是否重试。'
  if (error instanceof ApiError) {
    const detail = error.detail
    const code = detail && typeof detail === 'object' && 'code' in detail ? detail.code : null
    if (code === 'run_in_progress') return '当前会话仍有一轮对话在执行。请等待后再重试。'
    if (code === 'action_conflict') return '该待批操作已被处理，请刷新待批状态。'
    if (code === 'action_not_found') return '待批操作不存在或已失效，请刷新待批状态。'
    if (code === 'action_failed') return '执行失败，操作未完成。请核对工单状态并联系管理员。'
    if (error.status === 422) return '输入未通过服务端校验，请检查问题或操作信息。'
    if (error.status === 500) return '服务端处理失败，请稍后重试。'
    return error.message
  }
  return '操作失败，请稍后重试。'
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function visibleResponse(response: InteractionResponse): InteractionResponse {
  const result = response.result
  const profile = objectValue(result?.device_profile)
  const risk = objectValue(result?.risk_prediction)
  const manuals = Array.isArray(result?.results) ? result.results : null
  return {
    ...response,
    pending_actions: [],
    result: result ? {
      source: result.source,
      degraded: result.degraded,
      assetnum: result.assetnum,
      ...(profile ? { device_profile: { assetnum: profile.assetnum } } : {}),
      ...(risk ? { risk_prediction: { risk_30d: risk.risk_30d } } : {}),
      ...(manuals ? { results: manuals.slice(0, 5).map((raw) => {
        const item = objectValue(raw)
        return { title: item?.title, source: item?.source, content: item?.content }
      }) } : {}),
    } : null,
  }
}

function responseStatusLabel(status: string) {
  if (status === 'clarified') return '需要补充信息'
  if (status === 'success') return '已回复'
  if (status === 'error') return '查询失败'
  if (status === 'rejected') return '无法处理'
  return status
}

function StructuredResult({ response, dataProfile }: { response: InteractionResponse; dataProfile: 'demo' | 'production' | undefined }) {
  const result = response.result
  if (!result) return null
  const source = result.source
  const diagnosis = objectValue(result.device_profile) ? result : null
  const risk = objectValue(diagnosis?.risk_prediction)
  const manuals = Array.isArray(result.results) ? result.results : null
  return (
    <div className="assistant-result">
      {source === 'legacy_fallback' && <p className="assistant-degraded">智能分析服务暂不可用，以下为基础查询结果。</p>}
      {diagnosis && <div className="assistant-result-card">
        <h3>设备诊断摘要</h3>
        <p>设备：</p><DeviceIdentity assetnum={String(diagnosis.assetnum || response.assetnum || '未提供')} dataProfile={dataProfile} />
        {risk && <p>未来 30 日工单复发风险：{typeof risk.risk_30d === 'number' ? `${Math.round(risk.risk_30d * 100)}%` : '不可用'}</p>}
        <p className="data-note">风险表示未来工单复发概率，不表示物理故障发生日期；检修参考不代表已确认根因。</p>
      </div>}
      {manuals && <div className="assistant-result-card">
        <h3>手册检索</h3>
        {manuals.length === 0 ? <p>当前没有匹配的手册段落。</p> : <ul>{manuals.slice(0, 5).map((raw, index) => {
          const item = objectValue(raw)
          return <li key={index}><strong>{String(item?.title || '手册段落')}</strong><span> · {String(item?.source || '来源未提供')}</span><p>{String(item?.content || '')}</p></li>
        })}</ul>}
      </div>}
    </div>
  )
}

export function AssistantPage() {
  const profile = useDataProfile()
  const me = useAuthMe()
  const logout = useLogout()
  const [searchParams, setSearchParams] = useSearchParams()
  const assetnum = searchParams.get('assetnum')?.trim() || ''
  const [session, setSession] = useState(readSession)
  const [draft, setDraft] = useState(() => searchParams.get('question')?.slice(0, 500) ?? '')
  const [busy, setBusy] = useState(false)
  const [resolving, setResolving] = useState<string | null>(null)
  const [error, setError] = useState('')
  const submitGuard = useRef(false)
  const incomingQuestionGuard = useRef<string | null>(null)
  const queryClient = useQueryClient()
  const pendingKey = ['interaction', 'pending', session.sessionId]
  const pendingQuery = useQuery({ queryKey: pendingKey, queryFn: () => getPendingActions(session.sessionId), retry: false })
  const pending = pendingQuery.data?.pending_actions.filter((item) => item.status === 'pending') ?? []

  useEffect(() => { sessionStorage.setItem(storageKey, JSON.stringify(session)) }, [session])

  const send = useCallback(async (question: string) => {
    const value = question.trim()
    const fullQuery = assetnum ? `关于设备 ${assetnum}：${value}` : value
    if (!value || submitGuard.current || busy) return
    if (fullQuery.length > 500) { setError('问题与设备编号合计不得超过 500 字。'); return }
    submitGuard.current = true
    setBusy(true)
    setError('')
    try {
      const response = await sendTurn(fullQuery, session.sessionId)
      setSession((current) => ({ sessionId: response.session_id, exchanges: [...current.exchanges, { question: value, response: visibleResponse(response) }] }))
      setDraft('')
      await queryClient.invalidateQueries({ queryKey: ['interaction', 'pending'] })
    } catch (caught) { setError(errorMessage(caught)) }
    finally { submitGuard.current = false; setBusy(false) }
  }, [assetnum, busy, queryClient, session.sessionId])

  useEffect(() => {
    const incomingQuestion = searchParams.get('send') === '1' ? searchParams.get('question')?.trim() : null
    if (!incomingQuestion) { incomingQuestionGuard.current = null; return }
    if (incomingQuestionGuard.current === incomingQuestion) return
    incomingQuestionGuard.current = incomingQuestion
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('question')
      next.delete('send')
      return next
    }, { replace: true })
    void send(incomingQuestion)
  }, [searchParams, setSearchParams, send])

  async function resolve(kind: 'approve' | 'reject', actionId: string) {
    if (submitGuard.current || busy || resolving) return
    submitGuard.current = true
    setResolving(actionId)
    setError('')
    try {
      const response = await resolvePendingAction(kind, session.sessionId, actionId)
      setSession((current) => ({ ...current, exchanges: [...current.exchanges, { question: kind === 'approve' ? '批准待批工单操作' : '拒绝待批工单操作', response: visibleResponse(response) }] }))
    } catch (caught) { setError(errorMessage(caught)) }
    finally {
      await queryClient.invalidateQueries({ queryKey: pendingKey })
      submitGuard.current = false
      setResolving(null)
    }
  }

  function newSession() {
    if (busy || resolving || pendingQuery.isPending || pendingQuery.isError || pending.length) return
    setSession({ sessionId: createId(), exchanges: [] })
    setDraft('')
    setError('')
  }

  const suggestions = assetnum
    ? ['分析设备风险', '查询检修历史', '查找检修手册']
    : ['哪些设备建议优先检修？', '有哪些待执行的检修任务？', '查看高风险设备', '查询正在执行的检修任务']
  const suggestionQuestions = assetnum
    ? ['分析这台设备的工单复发风险', '查询这台设备的维修历史', '查找相关维修手册']
    : ['查询检修建议', '有哪些待执行的检修任务？', '查看高风险设备', '查询正在执行的检修任务']
  const currentAsset = session.exchanges.at(-1)?.response.assetnum || session.exchanges.at(-1)?.response.last_assetnum || assetnum
  const composer = <form className={`assistant-compose${session.exchanges.length === 0 ? ' assistant-compose--welcome' : ' assistant-compose--chat'}`} onSubmit={(event) => { event.preventDefault(); void send(draft) }}>
    <label className="assistant-sr-only" htmlFor="assistant-question">输入问题</label>
    <div className="assistant-compose__field"><Bot size={20} aria-hidden="true" /><textarea id="assistant-question" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={Math.max(0, 500 - (assetnum ? `关于设备 ${assetnum}：`.length : 0))} rows={2} placeholder={assetnum ? `输入关于 ${assetnum} 的问题…` : '输入设备编号、问题或指令…'} disabled={busy} /><button type="submit" className="assistant-compose__send" aria-label={busy ? '正在回复' : '发送'} disabled={!draft.trim() || busy}>{busy ? <span className="assistant-compose__spinner" aria-hidden="true" /> : <ArrowUp size={20} aria-hidden="true" />}</button></div>
    <p>AI 回复仅供参考 · 每轮最多 500 字</p>
  </form>

  const canStartNew = !(busy || !!resolving || pendingQuery.isPending || pendingQuery.isError || pending.length > 0)
  const isEmpty = session.exchanges.length === 0

  return <div className={`assistant-page${isEmpty ? ' assistant-page--welcome' : ' assistant-page--chat'}`}>
    <header className="assistant-topbar">
      <div className="assistant-topbar__title">
        <h1>AI 助手</h1>
        <span className="assistant-online" title="服务可用">
          <span className="assistant-online__dot" aria-hidden="true" />
          在线
        </span>
      </div>
      <div className="assistant-topbar__actions">
        <button
          type="button"
          className="assistant-topbar__action"
          onClick={newSession}
          disabled={!canStartNew}
          aria-label="新会话"
          title="新会话"
        >
          <MessageSquarePlus size={20} strokeWidth={1.9} aria-hidden="true" />
          <span>新会话</span>
        </button>
        {me.data?.username && (
          <button
            type="button"
            className="assistant-topbar__logout"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            aria-label={`退出登录（${me.data.username}）`}
          >
            退出
          </button>
        )}
      </div>
    </header>
    {isEmpty && (
      <div className="assistant-welcome">
        <h2>有什么可以帮您？</h2>
        <p>分析设备风险，查询检修建议、历史与手册。</p>
      </div>
    )}
    {assetnum && <div className="assistant-context">当前设备：<Link to={`/devices/${encodeURIComponent(assetnum)}`}><DeviceIdentity assetnum={assetnum} dataProfile={profile.data?.data_profile} /></Link></div>}
    {pendingQuery.isPending && <StateMessage title="正在核对待批操作" detail="载入当前会话的工单提案。" />}
    {pendingQuery.isError && <StateMessage title="待批状态读取失败" detail="暂时无法确认是否存在待处理操作。请重试后再开新会话。" retry={() => void pendingQuery.refetch()} />}
    {pending.length > 0 && <section className="assistant-pending" aria-labelledby="pending-title"><h2 id="pending-title">待批工单操作</h2><p>请核对提案；仅点击批准会执行写入，口语确认不会执行。</p>{pending.map((item) => <div className="assistant-pending-card" key={item.action_id}><strong>{item.summary || item.tool_name}</strong><p>操作类型：{item.tool_name} · 操作编号：{item.action_id}</p><dl className="assistant-payload">{Object.entries(item.payload).filter(([, value]) => value === null || ['string', 'number', 'boolean'].includes(typeof value)).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl><div className="assistant-pending-actions"><button type="button" className="button-primary" aria-label={`批准并执行：${item.summary || item.tool_name}`} disabled={!!resolving || busy} onClick={() => void resolve('approve', item.action_id)}>{resolving === item.action_id ? '处理中…' : '批准并执行'}</button><button type="button" className="button-quiet" aria-label={`拒绝：${item.summary || item.tool_name}`} disabled={!!resolving || busy} onClick={() => void resolve('reject', item.action_id)}>拒绝</button></div></div>)}</section>}
    {isEmpty && <section className="assistant-empty" aria-label="开始对话">
      {composer}
      <div className="assistant-suggestions"><div className="assistant-suggestions__heading"><h2>可以这样问</h2></div>{suggestions.map((label, index) => <button key={label} type="button" onClick={() => void send(suggestionQuestions[index])} disabled={busy}><span>{label}</span><ChevronRight className="assistant-suggestion__arrow" size={16} aria-hidden="true" /></button>)}</div>
    </section>}
    {session.exchanges.length > 0 && <ol className="assistant-transcript" aria-label="本标签页对话">{session.exchanges.map((exchange, index) => <li key={index}>
      <div className="assistant-user"><span>你</span><p>{exchange.question}</p></div>
      <div className="assistant-answer"><span className="assistant-answer__avatar"><Bot size={17} aria-hidden="true" /></span><div className="assistant-answer__content"><div className="assistant-answer__label">AI 助手 <span className={exchange.response.status === 'error' ? 'assistant-answer__status--error' : undefined}>· {responseStatusLabel(exchange.response.status)}</span></div><Suspense fallback={<p className="assistant-markdown-loading" role="status">正在排版答复…</p>}><AssistantMarkdown content={exchange.response.final_answer} dataProfile={profile.data?.data_profile} /></Suspense><StructuredResult response={exchange.response} dataProfile={profile.data?.data_profile} />{exchange.response.status === 'error' && <div className="assistant-failure"><p>本次查询未完成。请检查设备编号，或重试本问题。</p><button type="button" className="button-quiet" disabled={busy} onClick={() => void send(exchange.question)}>重试本问题</button></div>}</div></div>
    </li>)}</ol>}
    {currentAsset && <div className="assistant-links">{!assetnum && <DeviceIdentity assetnum={currentAsset} dataProfile={profile.data?.data_profile} />}<Link to={`/devices/${encodeURIComponent(currentAsset)}`}>查看设备详情</Link><Link to={`/maintenance?view=suggestions&q=${encodeURIComponent(currentAsset)}`}>查看相关建议</Link><Link to={`/maintenance?view=tasks&assetnum=${encodeURIComponent(currentAsset)}`}>查看相关任务</Link></div>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {session.exchanges.length > 0 && composer}
  </div>
}
