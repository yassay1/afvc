import { ArrowLeftRight, ArrowUp, ArrowUpRight, Check, ChevronRight, ClipboardList, Clock3, MessageCircle, ShieldAlert, Sparkles, Wrench } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import type { MaintenanceSuggestion, MaintenanceTaskStatus } from '../../shared/api/types'
import { StateMessage } from '../../shared/components/StateMessage'
import { DeviceImage } from '../../shared/components/DeviceImage'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { useDataProfile } from '../../shared/query/dataProfile'
import { useMaintenanceSuggestions, useMaintenanceTasks } from '../../shared/query/maintenance'
import { visibleSuggestionReason } from '../../shared/presentation/maintenanceCopy'
import { warningLevelClass } from '../../shared/presentation/warningLevel'
import './workbench.css'

const taskStatusLabels: Record<MaintenanceTaskStatus, string> = {
  planned: '待执行',
  in_progress: '执行中',
  done: '已完成',
  cancelled: '已取消',
}

function SuggestionItem({ suggestion, profile }: { suggestion: MaintenanceSuggestion; profile: 'demo' | 'production' | undefined }) {
  return (
    <li className="suggestion-item">
      <div className="suggestion-item__content">
        {suggestion.warning_level && <span className={`risk-label ${warningLevelClass(suggestion.warning_level)}`}><ShieldAlert size={14} aria-hidden="true" />{suggestion.warning_level}</span>}
        <DeviceIdentity assetnum={suggestion.assetnum} dataProfile={profile} className="suggestion-item__identity" />
        <p className="suggestion-item__station">{suggestion.station_name || '车站未提供'} · {suggestion.fault_focus}</p>
        <p className="suggestion-item__reason">{suggestion.reasons[0] ? visibleSuggestionReason(suggestion.reasons[0]) : '查看检修建议详情'}</p>
      </div>
      <DeviceImage assetnum={suggestion.assetnum} className="suggestion-item__image" />
      <Link className="suggestion-item__link" to={`/maintenance?view=suggestions&q=${encodeURIComponent(suggestion.assetnum)}`} aria-label={`查看 ${suggestion.assetnum} 的全部建议`}><span className="suggestion-item__link-icon"><ChevronRight size={20} aria-hidden="true" /></span></Link>
    </li>
  )
}

function SuggestionsSection({ profile }: { profile: 'demo' | 'production' | undefined }) {
  const query = useMaintenanceSuggestions()
  const result = query.data
  const unavailable = result && (result.status !== 'success' || result.prediction_tier === 'unavailable')

  return (
    <section className="workbench-section workbench-section--suggestions" aria-labelledby="suggestions-heading">
      <div className="workbench-section__header">
        <span className="workbench-section__icon workbench-section__icon--risk"><ShieldAlert size={20} aria-hidden="true" /></span>
        <div><h2 id="suggestions-heading">检修建议</h2><p>按优先顺序查看设备与建议依据</p></div>
      </div>
      {query.isPending && <StateMessage title="正在读取检修建议" detail="从服务端获取当前排序与理由。" />}
      {query.isError && <StateMessage title="检修建议读取失败" detail="请检查后端服务或网络连接后重试。" retry={() => void query.refetch()} />}
      {unavailable && <StateMessage title="检修建议暂不可用" detail={result.model_note || result.message || '服务端尚未提供可用建议。'} />}
      {result && !unavailable && result.suggestions.length === 0 && <StateMessage title="暂无检修建议" detail="当前数据未生成建议，可稍后刷新或检查工单数据。" retry={() => void query.refetch()} />}
      {result && !unavailable && result.suggestions.length > 0 && (
        <>
          {result.suggestions.length > 1 && <p className="suggestion-list-hint"><ArrowLeftRight size={14} aria-hidden="true" />左右滑动查看更多建议</p>}
          <ol className="suggestion-list" aria-label="建议摘要">{result.suggestions.slice(0, 3).map((item) => <SuggestionItem key={item.assetnum} suggestion={item} profile={profile} />)}</ol>
          <Link className="workbench-section__all" to="/maintenance?view=suggestions">查看全部建议 <ChevronRight size={18} aria-hidden="true" /></Link>
        </>
      )}
    </section>
  )
}

function TasksSection({ profile }: { profile: 'demo' | 'production' | undefined }) {
  const query = useMaintenanceTasks()
  const result = query.data

  return (
    <section className="workbench-section workbench-section--tasks" aria-labelledby="tasks-heading">
      <div className="workbench-section__header">
        <span className="workbench-section__icon workbench-section__icon--tasks"><ClipboardList size={20} aria-hidden="true" /></span>
        <div><h2 id="tasks-heading">我的检修任务</h2><p>跟进任务进度，确保检修按计划完成</p></div>
        <Link to="/maintenance?view=tasks" aria-label={`共 ${result?.status === 'success' ? result.count : '—'} 项，查看全部任务`}>共 {result?.status === 'success' ? result.count : '—'} 项 <ChevronRight size={17} aria-hidden="true" /></Link>
      </div>
      {query.isPending && <StateMessage title="正在读取任务" detail="从服务端获取当前任务状态。" />}
      {query.isError && <StateMessage title="任务读取失败" detail="请检查后端服务或网络连接后重试。" retry={() => void query.refetch()} />}
      {result && result.status !== 'success' && <StateMessage title="任务暂不可用" detail={result.message || '服务端尚未提供任务。'} />}
      {result && result.status === 'success' && result.tasks.length === 0 && <StateMessage title="暂无检修任务" detail="目前没有已安排的任务；可在检修页查看建议。" />}
      {result && result.status === 'success' && result.tasks.length > 0 && (
        <div className="task-summary">
          <ul>
            {(['planned', 'in_progress', 'done'] as const).map((status) => (
              <li key={status} className={`task-summary__${status}`}>
                <span className="task-summary__icon">{status === 'planned' ? <Clock3 size={18} aria-hidden="true" /> : status === 'in_progress' ? <Wrench size={18} aria-hidden="true" /> : <Check size={18} aria-hidden="true" />}</span>
                <strong>{result.tasks.filter((task) => task.status === status).length}</strong><span>{taskStatusLabels[status]}</span>
              </li>
            ))}
          </ul>
          {result.tasks.find((task) => task.status !== 'cancelled') && (() => {
            const task = result.tasks.find((item) => item.status !== 'cancelled')!
            return <Link className="task-summary__preview" to={`/maintenance/tasks/${encodeURIComponent(task.id)}`}>
              <span className="task-summary__preview-status">{taskStatusLabels[task.status]}</span>
              <DeviceIdentity assetnum={task.assetnum} dataProfile={profile} className="task-summary__identity" />
              <small>{task.station_name || '车站未提供'} · {task.fault_focus}</small>
              <ChevronRight size={18} aria-hidden="true" />
            </Link>
          })()}
          {result.tasks.some((task) => task.status === 'cancelled') && <p className="task-summary__cancelled">另有 {result.tasks.filter((task) => task.status === 'cancelled').length} 项已取消</p>}
        </div>
      )}
    </section>
  )
}

const quickQuestions = ['哪些设备建议优先检修？', '查看近期闸机故障记录', '这台设备的风险高吗？']

function AssistantHero() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()

  function openQuestion(value: string) {
    const trimmed = value.trim()
    if (trimmed) navigate(`/assistant?question=${encodeURIComponent(trimmed)}&send=1`)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    openQuestion(question)
  }

  return <section className="workbench-assistant" aria-labelledby="workbench-assistant-title">
    <Link className="workbench-assistant__heading" to="/assistant"><Sparkles size={19} aria-hidden="true" /><strong id="workbench-assistant-title">AI 助手</strong><ChevronRight size={18} aria-hidden="true" /></Link>
    <p className="workbench-assistant__statement">快速查询设备风险与检修建议</p>
    <div className="workbench-assistant__questions" aria-label="快捷提问">{quickQuestions.map((item) => <button key={item} type="button" onClick={() => openQuestion(item)}>{item}</button>)}</div>
    <form className="workbench-assistant__form" onSubmit={submit}>
      <MessageCircle size={20} aria-hidden="true" />
      <label className="visually-hidden" htmlFor="workbench-question">向 AI 助手提问</label>
      <input id="workbench-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={500} placeholder="输入设备编号、问题或指令…" />
      <button type="submit" disabled={!question.trim()} aria-label="带着问题前往 AI 助手"><ArrowUp size={20} aria-hidden="true" /></button>
    </form>
  </section>
}

export function Workbench() {
  const profile = useDataProfile()
  return (
    <div className="workbench">
      <div className="workbench-intro">
        <h1>检修工作台</h1>
        <p>守护轨道交通设备安全运行</p>
      </div>
      <AssistantHero />
      <SuggestionsSection profile={profile.data?.data_profile} />
      <TasksSection profile={profile.data?.data_profile} />
      <Link className="workbench-data-link" to="/data?view=overview">数据概览与高风险设备 <ArrowUpRight size={17} aria-hidden="true" /></Link>
      <div className="workbench-footnote"><ClipboardList size={16} aria-hidden="true" />检修建议按服务端顺序展示；接口未提供生成时间。</div>
    </div>
  )
}
