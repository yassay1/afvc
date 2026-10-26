import { useState, type FormEvent } from 'react'
import { CalendarDays, ClipboardList, Search, ShieldAlert, UsersRound } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ApiError } from '../../shared/api/client'
import { createMaintenanceTask } from '../../shared/api/maintenance'
import type { MaintenanceSuggestion, MaintenanceTask, MaintenanceTaskStatus } from '../../shared/api/types'
import { StateMessage } from '../../shared/components/StateMessage'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { DeviceImage } from '../../shared/components/DeviceImage'
import { suggestionSourceExplanation, visibleSuggestionReason } from '../../shared/presentation/maintenanceCopy'
import { deviceDisplayName } from '../../shared/presentation/deviceIdentity'
import { warningLevelClass } from '../../shared/presentation/warningLevel'
import { useDataProfile } from '../../shared/query/dataProfile'
import { useMaintenanceSuggestions, useMaintenanceTasks } from '../../shared/query/maintenance'
import { queryKeys } from '../../shared/query/queryClient'
import './maintenance.css'

const statusLabels: Record<MaintenanceTaskStatus, string> = {
  planned: '待执行', in_progress: '执行中', done: '已完成', cancelled: '已取消',
}

function taskActionLabel(task: MaintenanceTask) {
  if (task.status === 'planned') return '调整计划'
  if (task.status === 'in_progress') return '填写执行反馈'
  if (task.status === 'done' && task.feedback_result) return '查看执行结果'
  return '查看任务详情'
}

function taskActionHash(task: MaintenanceTask) {
  if (task.status === 'planned') return '#task-plan'
  if (task.status === 'in_progress' || (task.status === 'done' && task.feedback_result)) return '#task-feedback'
  return ''
}

function writeErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 422) return '提交内容未通过校验，请检查字段后重试。'
  if (error instanceof ApiError && error.status === 404) return '相关设备或任务未找到，请刷新列表后重试。'
  return '保存失败，请先刷新任务列表确认是否已写入，再决定是否重试。'
}

function ArrangeForm({ suggestion, onCancel, dataProfile }: { suggestion: MaintenanceSuggestion; onCancel: () => void; dataProfile: 'demo' | 'production' | undefined }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [crew, setCrew] = useState(suggestion.suggested_crew_id ?? '')
  const [date, setDate] = useState('')
  const [priority, setPriority] = useState('100')
  const [validation, setValidation] = useState('')
  const create = useMutation({
    mutationFn: createMaintenanceTask,
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.tasks })
      navigate(`/maintenance/tasks/${encodeURIComponent(response.task.id)}`)
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (create.isPending) return
    const parsedPriority = Number(priority)
    if (!crew.trim() || !date || !Number.isInteger(parsedPriority) || parsedPriority < 1) {
      setValidation('请填写班组、计划日期和大于 0 的整数优先级。')
      return
    }
    setValidation('')
    create.mutate({
      assetnum: suggestion.assetnum,
      station_name: suggestion.station_name,
      fault_focus: suggestion.fault_focus,
      priority: parsedPriority,
      planned_date: date,
      assignee_crew_id: crew.trim(),
      suggestion_score: suggestion.score,
      suggestion_reasons: suggestion.reasons,
    })
  }

  return (
    <form className="maintenance-form" aria-label="核对检修安排" onSubmit={submit} noValidate>
      <div className="maintenance-form__head">
        <h3>核对检修安排</h3>
        <DeviceIdentity assetnum={suggestion.assetnum} dataProfile={dataProfile} as="span" />
        <p>建议班组来自模拟资源表，请核对现场实际安排后提交。</p>
      </div>
      <label>执行班组<input value={crew} onChange={(event) => setCrew(event.target.value)} autoComplete="off" required /></label>
      <label>计划日期<input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></label>
      <label>优先级<input type="number" min="1" step="1" value={priority} onChange={(event) => setPriority(event.target.value)} required /><small>数字越小越优先；最终任务排序由服务端决定。</small></label>
      {validation && <p className="form-error" role="alert">{validation}</p>}
      {create.isError && <p className="form-error" role="alert">{writeErrorMessage(create.error)}</p>}
      <div className="form-actions">
        <button type="submit" className="button-primary" disabled={create.isPending}>{create.isPending ? '正在安排…' : '确认安排检修'}</button>
        <button type="button" className="button-quiet" onClick={onCancel} disabled={create.isPending}>取消</button>
      </div>
    </form>
  )
}

function SuggestionsView({ params, setParams, dataProfile }: { params: URLSearchParams; setParams: ReturnType<typeof useSearchParams>[1]; dataProfile: 'demo' | 'production' | undefined }) {
  const query = useMaintenanceSuggestions()
  const [selected, setSelected] = useState<string | null>(null)
  const search = params.get('q') ?? ''
  const level = params.get('level') ?? ''
  const data = query.data
  const levels = Array.from(new Set((data?.suggestions ?? []).map((item) => item.warning_level).filter((value): value is string => Boolean(value))))
  const filtered = (data?.suggestions ?? []).filter((item) => {
    const matchedSearch = !search || [item.assetnum, deviceDisplayName(item.assetnum, dataProfile), item.station_name, item.fault_focus].some((value) => value?.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
    return matchedSearch && (!level || item.warning_level === level)
  })

  function setFilter(key: string, value: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  return (
    <section aria-labelledby="suggestions-title" className="maintenance-panel">
      <h2 id="suggestions-title" className="maintenance-visually-hidden">检修建议</h2>
      <div className="maintenance-filters">
        <label className="maintenance-search"><Search size={20} aria-hidden="true" /><span className="maintenance-visually-hidden">搜索设备或车站</span><input type="search" value={search} onChange={(event) => setFilter('q', event.target.value)} placeholder="搜索设备编号、车站或故障焦点" /></label>
        {data?.status === 'success' && <div className="maintenance-filter-chips" role="group" aria-label="预警级别筛选">
          <button type="button" aria-pressed={!level} onClick={() => setFilter('level', '')}>全部 {data.suggestions.length}</button>
          {levels.map((value) => <button type="button" key={value} aria-pressed={level === value} onClick={() => setFilter('level', value)}>{value} {data.suggestions.filter((item) => item.warning_level === value).length}</button>)}
        </div>}
      </div>
      {query.isPending && <StateMessage title="正在读取建议" detail="从服务端获取排序、理由与来源。" />}
      {query.isError && <StateMessage title="建议读取失败" detail="检查服务状态后重试。" retry={() => void query.refetch()} />}
      {data && (data.status !== 'success' || data.prediction_tier === 'unavailable') && <StateMessage title="建议暂不可用" detail={data.model_note || data.message} />}
      {data?.status === 'success' && data.prediction_tier !== 'unavailable' && filtered.length === 0 && <StateMessage title="没有匹配建议" detail="可调整搜索或筛选；若没有原始建议，请检查工单数据。" />}
      {data?.status === 'success' && data.prediction_tier !== 'unavailable' && filtered.length > 0 && (
        <ol className="maintenance-list" aria-label="检修建议列表">
          {filtered.map((item) => (
            <li key={item.assetnum} className="maintenance-card maintenance-card--suggestion">
              {item.warning_level && <span className={`maintenance-warning ${warningLevelClass(item.warning_level)}`}><ShieldAlert size={14} aria-hidden="true" />{item.warning_level}</span>}
              <div className="maintenance-card__overview">
                <div className="maintenance-card__identity">
                  <DeviceIdentity assetnum={item.assetnum} dataProfile={dataProfile} />
                  <p>{item.station_name || '车站未提供'} · {item.fault_focus}</p>
                </div>
                <DeviceImage assetnum={item.assetnum} className="maintenance-card__image" />
              </div>
              {item.reasons[0] && <p className="maintenance-card__lead"><ShieldAlert size={15} aria-hidden="true" />{visibleSuggestionReason(item.reasons[0])}</p>}
              {!item.reasons.length && <p className="maintenance-card__missing">当前没有可展示的建议依据。</p>}
              {(item.reasons.length > 1 || item.data_note || data.model_note) && <details className="maintenance-card__evidence">
                <summary><ClipboardList size={16} aria-hidden="true" />查看完整依据与数据来源</summary>
                {item.reasons.length > 0 && <><strong>建议排序依据</strong><ul>{item.reasons.map((reason, index) => <li key={`${index}-${reason}`}>{reason}</li>)}</ul></>}
                {suggestionSourceExplanation(data.model_note, item.data_note).map((note) => <p className="data-note" key={note}>{note}</p>)}
              </details>}
              <div className="maintenance-card__actions">
                <Link to={`/devices/${encodeURIComponent(item.assetnum)}`}>查看设备</Link>
                <button type="button" onClick={() => setSelected(selected === item.assetnum ? null : item.assetnum)}>安排检修</button>
              </div>
              {selected === item.assetnum && <ArrangeForm suggestion={item} dataProfile={dataProfile} onCancel={() => setSelected(null)} />}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function TasksView({ params, setParams, dataProfile }: { params: URLSearchParams; setParams: ReturnType<typeof useSearchParams>[1]; dataProfile: 'demo' | 'production' | undefined }) {
  const query = useMaintenanceTasks()
  const status = params.get('status') ?? ''
  const assetnum = params.get('assetnum') ?? ''
  const search = params.get('q') ?? ''
  const tasks = query.data?.tasks ?? []
  const filtered = tasks.filter((task) => (!status || task.status === status) && (!assetnum || task.assetnum === assetnum) && (!search || [task.id, task.assetnum, deviceDisplayName(task.assetnum, dataProfile), task.station_name, task.fault_focus].some((value) => value?.toLocaleLowerCase().includes(search.toLocaleLowerCase()))))

  function setFilter(key: string, value: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  return (
    <section aria-labelledby="tasks-title" className="maintenance-panel">
      <h2 id="tasks-title" className="maintenance-visually-hidden">任务跟进</h2>
      <div className="maintenance-filters">
        <label className="maintenance-search"><Search size={20} aria-hidden="true" /><span className="maintenance-visually-hidden">搜索任务或设备</span><input type="search" value={search} onChange={(event) => setFilter('q', event.target.value)} placeholder="搜索任务编号、设备或车站" /></label>
        {query.data?.status === 'success' && <div className="maintenance-filter-chips" role="group" aria-label="任务状态筛选">
          <button type="button" aria-pressed={!status} onClick={() => setFilter('status', '')}>全部 {tasks.length}</button>
          {(Object.keys(statusLabels) as MaintenanceTaskStatus[]).map((value) => <button type="button" key={value} aria-pressed={status === value} onClick={() => setFilter('status', value)}>{statusLabels[value]} {tasks.filter((task) => task.status === value).length}</button>)}
        </div>}
      </div>
      {assetnum && <p className="maintenance-filter-context">当前仅看设备 {assetnum} 的任务。</p>}
      {query.isPending && <StateMessage title="正在读取任务" detail="从服务端获取任务状态。" />}
      {query.isError && <StateMessage title="任务读取失败" detail="检查服务状态后重试。" retry={() => void query.refetch()} />}
      {query.data?.status === 'success' && filtered.length === 0 && <StateMessage title="没有匹配任务" detail="可切换状态筛选；若尚无任务，可从检修建议安排。" />}
      {query.data && query.data.status !== 'success' && <StateMessage title="任务暂不可用" detail={query.data.message} />}
      {query.data?.status === 'success' && filtered.length > 0 && <ul className="maintenance-list" aria-label="检修任务列表">{filtered.map((task) => (
        <li key={task.id} className="maintenance-card maintenance-card--task">
          <div className="task-card__top"><span className={`task-card__status task-card__status--${task.status}`}>{statusLabels[task.status] ?? task.status}</span><span className="task-card__id" aria-label={`任务编号 ${task.id}`} title={task.id}>任务 {task.id}</span></div>
          <div className="task-card__overview">
            <div className="task-card__identity"><DeviceIdentity assetnum={task.assetnum} dataProfile={dataProfile} /><p>{task.station_name || '车站未提供'} · {task.fault_focus}</p></div>
            <DeviceImage assetnum={task.assetnum} className="task-card__image" />
          </div>
          <div className="task-card__meta"><span><CalendarDays size={15} aria-hidden="true" />计划日期 {task.planned_date || '未安排'}</span><span><UsersRound size={15} aria-hidden="true" />执行班组 {task.assignee_crew_id || '未分配'}</span></div>
          <div className="maintenance-card__actions"><Link to={`/devices/${encodeURIComponent(task.assetnum)}`}>查看设备</Link><Link className="task-card__primary" to={`/maintenance/tasks/${encodeURIComponent(task.id)}${taskActionHash(task)}`}>{taskActionLabel(task)}</Link></div>
        </li>
      ))}</ul>}
    </section>
  )
}

export function MaintenancePage() {
  const [params, setParams] = useSearchParams()
  const profile = useDataProfile()
  const dataProfile = profile.data?.data_profile
  const view = params.get('view') === 'tasks' ? 'tasks' : 'suggestions'

  function changeView(nextView: 'suggestions' | 'tasks') {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('view', nextView)
      return next
    })
  }

  return (
    <div className="maintenance-page">
      <div className="maintenance-title"><h1>检修</h1></div>
      <div className="segment" role="group" aria-label="检修视图">
        <button type="button" aria-pressed={view === 'suggestions'} onClick={() => changeView('suggestions')}>检修建议</button>
        <button type="button" aria-pressed={view === 'tasks'} onClick={() => changeView('tasks')}>任务跟进</button>
      </div>
      {view === 'suggestions' ? <SuggestionsView params={params} setParams={setParams} dataProfile={dataProfile} /> : <TasksView params={params} setParams={setParams} dataProfile={dataProfile} />}
    </div>
  )
}
