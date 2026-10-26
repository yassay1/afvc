import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError } from '../../shared/api/client'
import { patchMaintenanceTask, submitMaintenanceFeedback } from '../../shared/api/maintenance'
import type { MaintenanceTask, MaintenanceTaskStatus } from '../../shared/api/types'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { StateMessage } from '../../shared/components/StateMessage'
import { useDataProfile } from '../../shared/query/dataProfile'
import { useMaintenanceTask } from '../../shared/query/maintenance'
import { queryKeys } from '../../shared/query/queryClient'
import { visibleTaskSuggestionReason } from '../../shared/presentation/maintenanceCopy'
import './maintenance.css'

const statusLabels: Record<MaintenanceTaskStatus, string> = {
  planned: '待执行', in_progress: '执行中', done: '已完成', cancelled: '已取消',
}

function errorText(error: unknown) {
  if (error instanceof ApiError && error.status === 404) return '任务未找到。请返回任务列表刷新后核对。'
  if (error instanceof ApiError && error.status === 409) return '任务状态已变化。请先核对并提交现场执行反馈，再刷新任务详情。'
  if (error instanceof ApiError && error.status === 422) return '提交内容未通过校验，请检查字段后重试。'
  return '提交结果不确定。请刷新任务详情核对服务端状态后再决定是否重试。'
}

function TaskEditor({ task }: { task: MaintenanceTask }) {
  const client = useQueryClient()
  const [status, setStatus] = useState<MaintenanceTaskStatus>(task.status)
  const [crew, setCrew] = useState(task.assignee_crew_id ?? '')
  const [date, setDate] = useState(task.planned_date ?? '')
  const [priority, setPriority] = useState(String(task.priority))
  const [validation, setValidation] = useState('')
  const patch = useMutation({
    mutationFn: () => patchMaintenanceTask(task.id, { status, assignee_crew_id: crew.trim(), planned_date: date, priority: Number(priority) }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.tasks }),
        client.invalidateQueries({ queryKey: queryKeys.task(task.id) }),
      ])
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (patch.isPending) return
    const number = Number(priority)
    if (!crew.trim() || !date || !Number.isInteger(number) || number < 1) {
      setValidation('请填写班组、计划日期和大于 0 的整数优先级。')
      return
    }
    setValidation('')
    patch.mutate()
  }

  return (
    <form id="task-plan" className="maintenance-form" aria-label="调整计划" onSubmit={submit} noValidate>
      <h2>调整计划</h2>
      <label>任务状态<select value={status} disabled={task.status === 'done'} onChange={(event) => setStatus(event.target.value as MaintenanceTaskStatus)}>{(Object.keys(statusLabels) as MaintenanceTaskStatus[]).filter((value) => value !== 'done' || task.status === 'done').map((value) => <option value={value} key={value}>{statusLabels[value]}</option>)}</select></label>
      <p className="form-hint">提交现场执行反馈后，任务会自动标记为已完成。</p>
      <label>执行班组<input value={crew} onChange={(event) => setCrew(event.target.value)} required /></label>
      <label>计划日期<input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></label>
      <label>优先级<input type="number" min="1" step="1" value={priority} onChange={(event) => setPriority(event.target.value)} required /></label>
      {validation && <p className="form-error" role="alert">{validation}</p>}
      {patch.isError && <p className="form-error" role="alert">{errorText(patch.error)}</p>}
      <button type="submit" className="button-primary" disabled={patch.isPending}>{patch.isPending ? '正在保存…' : '保存任务调整'}</button>
    </form>
  )
}

function FeedbackForm({ task }: { task: MaintenanceTask }) {
  const client = useQueryClient()
  const [result, setResult] = useState('')
  const [matched, setMatched] = useState('')
  const [followed, setFollowed] = useState('')
  const [note, setNote] = useState('')
  const [validation, setValidation] = useState('')
  const feedback = useMutation({
    mutationFn: () => submitMaintenanceFeedback(task.id, {
      result: result.trim(),
      matched_fault: matched === '' ? null : matched === 'true',
      followed_suggestion: followed === '' ? null : followed === 'true',
      note: note.trim() || null,
    }),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.tasks }),
        client.invalidateQueries({ queryKey: queryKeys.task(task.id) }),
      ])
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (feedback.isPending) return
    if (!result.trim()) {
      setValidation('请填写现场执行结果。')
      return
    }
    setValidation('')
    feedback.mutate()
  }

  return (
    <form id="task-feedback" className="maintenance-form" aria-label="执行反馈" onSubmit={submit} noValidate>
      <h2>执行反馈</h2>
      <label>现场结果 <span aria-hidden="true">*</span><textarea value={result} onChange={(event) => setResult(event.target.value)} rows={4} required /></label>
      <label>是否匹配目标故障<select value={matched} onChange={(event) => setMatched(event.target.value)}><option value="">未判断</option><option value="true">是</option><option value="false">否</option></select></label>
      <label>是否按建议执行<select value={followed} onChange={(event) => setFollowed(event.target.value)}><option value="">未判断</option><option value="true">是</option><option value="false">否</option></select></label>
      <label>补充说明<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} /></label>
      {validation && <p className="form-error" role="alert">{validation}</p>}
      {feedback.isError && <p className="form-error" role="alert">{errorText(feedback.error)}</p>}
      <button type="submit" className="button-primary" disabled={feedback.isPending}>{feedback.isPending ? '正在提交…' : '提交执行反馈'}</button>
    </form>
  )
}

export function TaskDetail() {
  const { taskId = '' } = useParams()
  const { hash } = useLocation()
  const query = useMaintenanceTask(taskId)
  const profile = useDataProfile()
  const task = query.data?.task

  useEffect(() => {
    if (!task || !hash) return
    const target = document.getElementById(hash.slice(1))
    if (target) requestAnimationFrame(() => target.scrollIntoView({ block: 'start' }))
  }, [task, hash])

  return (
    <div className="maintenance-page task-detail">
      <Link className="back-link" to="/maintenance?view=tasks">返回任务跟进</Link>
      {query.isPending && <StateMessage title="正在读取任务" detail="从服务端获取任务详情。" />}
      {query.isError && <StateMessage title="任务读取失败" detail={errorText(query.error)} retry={() => void query.refetch()} />}
      {query.data && query.data.status !== 'success' && <StateMessage title="任务暂不可用" detail={query.data.message || '服务端未返回任务。'} />}
      {task && query.data?.status === 'success' && (
        <>
          <section className="maintenance-panel task-detail__summary">
            <p className="section-kicker">检修任务</p>
            <DeviceIdentity assetnum={task.assetnum} dataProfile={profile.data?.data_profile} as="h1" />
            <p>{task.station_name || '车站未提供'} · {task.fault_focus}</p>
            <dl>
              <div><dt>状态</dt><dd>{statusLabels[task.status] ?? task.status}</dd></div>
              <div><dt>班组</dt><dd>{task.assignee_crew_id || '未分配'}</dd></div>
              <div><dt>计划日期</dt><dd>{task.planned_date || '未安排'}</dd></div>
              <div><dt>优先级</dt><dd>{task.priority}</dd></div>
            </dl>
            {task.suggestion_reasons.length > 0 && <div className="task-detail__reasons"><h2>检修建议依据</h2><ul className="reason-list">{task.suggestion_reasons.map((reason, index) => <li key={`${index}-${reason}`}>{visibleTaskSuggestionReason(reason)}</li>)}</ul><details className="task-detail__source"><summary>查看服务端返回的完整依据</summary><ul className="reason-list">{task.suggestion_reasons.map((reason, index) => <li key={`${index}-${reason}-source`}>{reason}</li>)}</ul></details></div>}
          </section>
          <TaskEditor key={[task.id, task.status, task.priority, task.planned_date, task.assignee_crew_id].join(':')} task={task} />
          {task.feedback_result ? (
            <section id="task-feedback" className="maintenance-panel"><h2>已提交的执行反馈</h2><p>{task.feedback_result}</p>{task.feedback_note && <p>{task.feedback_note}</p>}</section>
          ) : <FeedbackForm task={task} />}
        </>
      )}
    </div>
  )
}
