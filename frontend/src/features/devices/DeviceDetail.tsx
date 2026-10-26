import { useEffect, useState } from 'react'
import { ArrowLeft, Bot, CalendarDays, ChevronRight, ClipboardList, FileText, ShieldAlert, Wrench } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { DeviceImage } from '../../shared/components/DeviceImage'
import { StateMessage } from '../../shared/components/StateMessage'
import { useDataProfile } from '../../shared/query/dataProfile'
import { useDeviceDiagnosis } from '../../shared/query/devices'
import { useMaintenanceTasks } from '../../shared/query/maintenance'
import { warningLevelClass } from '../../shared/presentation/warningLevel'
import './devices.css'

function riskText(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value * 100)}%` : '暂无数据'
}

function cleanWorkOrderDescription(value: string) {
  return value.replace(/^合成工单：/, '').replace(/；现场复位并记录模拟观察值$/, '').trim()
}

function cleanTaskFeedback(value: string) {
  return value.replace(/^完成模拟检修/, '检修已完成').trim()
}

function subsystemLabel(value: string | null | undefined) {
  if (value === 'AFCAGM') return '闸机'
  return value || '设备'
}

const taskStatusLabels: Record<string, string> = {
  planned: '待执行',
  in_progress: '执行中',
  done: '已完成',
  cancelled: '已取消',
}

function RiskMetric({ label, value }: { label: string; value: number | null | undefined }) {
  const percent = typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value * 100))) : null
  return <div className="device-risk-metric">
    <div><span>{label}</span><strong>{riskText(value)}</strong></div>
    {percent !== null && <div className="device-risk-meter" role="img" aria-label={`${label}风险水平 ${percent}%`}><span style={{ width: `${percent}%` }} /></div>}
  </div>
}

export function DeviceDetail() {
  const { assetnum = '' } = useParams()
  const [showAllHistory, setShowAllHistory] = useState(false)
  const [actionsPinned, setActionsPinned] = useState(false)
  const diagnosis = useDeviceDiagnosis(assetnum)
  const appProfile = useDataProfile()
  const taskQuery = useMaintenanceTasks()
  const data = diagnosis.data
  const profile = data?.device_profile
  const risk = data?.risk_prediction
  const history = data?.history_summary
  const advice = data?.maintenance_advice
  const fault = data?.fault_prediction
  const relatedTasks = (taskQuery.data?.tasks ?? []).filter((task) => task.assetnum === assetnum)
  const descriptions = (history?.recent_descriptions ?? []).map(cleanWorkOrderDescription).filter(Boolean)
  const shownDescriptions = showAllHistory ? descriptions : descriptions.slice(0, 3)
  const inspectionSuggestions = advice?.inspection_suggestions ?? []
  const spareParts = advice?.spare_part_suggestions ?? []

  useEffect(() => {
    function updatePinnedActions() {
      setActionsPinned(window.scrollY > 260)
    }
    window.addEventListener('scroll', updatePinnedActions, { passive: true })
    return () => window.removeEventListener('scroll', updatePinnedActions)
  }, [])

  return (
    <div className="devices-page device-detail-page">
      <header className="device-detail__topbar">
        <Link to="/devices" aria-label="返回设备列表"><ArrowLeft size={22} aria-hidden="true" /></Link>
        <h1>设备详情</h1>
        <span aria-hidden="true" />
      </header>
      {diagnosis.isPending && <StateMessage title="正在读取设备详情" detail="正在获取设备信息和检修参考。" />}
      {diagnosis.isError && <StateMessage title="设备详情读取失败" detail="设备可能不存在，或数据暂时无法读取。返回列表核对编号后重试。" retry={() => void diagnosis.refetch()} />}
      {data && data.status !== 'success' && <StateMessage title="设备详情暂不可用" detail={data.message} />}
      {data?.status === 'success' && (
        <>
          <section className="device-detail__identity" aria-label="设备摘要">
            <DeviceImage assetnum={data.assetnum} />
            <div className="device-detail__identity-copy">
              <DeviceIdentity assetnum={data.assetnum} dataProfile={appProfile.data?.data_profile} as="h2" />
              <p>{profile?.station_name || '车站未提供'} · {subsystemLabel(profile?.subsystem)}</p>
              <p>{profile?.line || '线路未提供'} · {profile?.brand || '品牌未提供'}</p>
              {risk?.warning_level && <span className={`device-detail__warning ${warningLevelClass(risk.warning_level)}`}><ShieldAlert size={15} aria-hidden="true" />{risk.warning_level}</span>}
            </div>
          </section>

          <section className="devices-panel device-detail__risk" aria-labelledby="risk-heading">
            <div className="device-detail__section-heading"><ShieldAlert size={20} aria-hidden="true" /><h2 id="risk-heading">风险评估</h2></div>
            {risk ? <>
              <div className="device-risk-grid"><RiskMetric label="未来 30 日复发风险" value={risk.risk_30d} /><RiskMetric label="未来 90 日复发风险" value={risk.risk_90d} /></div>
              {risk.warning_reason && <p className="device-detail__risk-reason">{risk.warning_reason}</p>}
              {risk.suggested_inspection_window && <p className="device-detail__inspection-window"><CalendarDays size={17} aria-hidden="true" />{risk.suggested_inspection_window}</p>}
              {fault?.status === 'success' && fault.most_likely_fault && <div className="device-detail__fault-callout"><strong>{fault.most_likely_fault.fault_name}</strong><small>类型参考 {Math.round(fault.most_likely_fault.conditional_probability * 100)}%</small></div>}
              {!fault || fault.status !== 'success' ? <p className="device-detail__note">故障类型预测暂不可用，风险结果仅供巡检安排参考。</p> : null}
            </> : <StateMessage title="风险信息暂缺" detail="当前没有可用的设备风险结果。" />}
          </section>

          <section className="devices-panel device-detail__history" aria-labelledby="history-heading">
            <div className="device-detail__section-heading"><CalendarDays size={20} aria-hidden="true" /><h2 id="history-heading">历史故障</h2><span>{history?.returned_history_count ?? 0} 条记录</span></div>
            {history ? descriptions.length > 0 ? <>
              <ul className="device-history-list">{shownDescriptions.map((description, index) => <li key={`${index}-${description}`}><span className="device-history-list__dot" aria-hidden="true" /><p>{description}</p></li>)}</ul>
              {descriptions.length > 3 && <button className="device-detail__text-action" type="button" onClick={() => setShowAllHistory((show) => !show)}>{showAllHistory ? '收起历史记录' : `查看其余 ${descriptions.length - 3} 条记录`}<ChevronRight size={16} aria-hidden="true" /></button>}
            </> : <p className="device-detail__empty">暂无历史故障描述。</p> : <StateMessage title="历史记录暂缺" detail="当前没有可用的历史工单摘要。" />}
          </section>

          <section className="devices-panel device-detail__references" aria-labelledby="references-heading">
            <div className="device-detail__section-heading"><FileText size={20} aria-hidden="true" /><h2 id="references-heading">检修参考</h2></div>
            {advice ? <>
              {advice.recognized_fault_phenomena.length > 0 && <div className="device-detail__phenomena"><span>近期现象</span><p>{advice.recognized_fault_phenomena.slice(0, 3).join('、')}</p></div>}
              {inspectionSuggestions.length > 0 ? <ol className="device-inspection-list">{inspectionSuggestions.slice(0, 3).map((item, index) => <li key={`${index}-${item}`}><span>{index + 1}</span><p>{item}</p></li>)}</ol> : <p className="device-detail__empty">暂无检修建议。</p>}
              {inspectionSuggestions.length > 3 && <details className="device-detail__more"><summary>查看其他检修建议（{inspectionSuggestions.length - 3}）</summary><ul>{inspectionSuggestions.slice(3).map((item, index) => <li key={`${index + 3}-${item}`}>{item}</li>)}</ul></details>}
              {spareParts.length > 0 && <details className="device-detail__more"><summary>查看备件参考（{spareParts.length}）</summary><p>{spareParts.join('、')}</p></details>}
            </> : <StateMessage title="检修参考暂缺" detail="当前没有可用的单机检修参考。" />}
          </section>

          {(relatedTasks.length > 0 || taskQuery.isPending || taskQuery.isError) && <section className="devices-panel device-detail__tasks" aria-labelledby="related-heading">
            <div className="device-detail__section-heading"><ClipboardList size={20} aria-hidden="true" /><h2 id="related-heading">相关任务</h2><span>{relatedTasks.length} 项</span></div>
            {taskQuery.isPending && <p className="device-detail__empty">正在读取相关任务…</p>}
            {taskQuery.isError && <p className="device-detail__empty">相关任务暂时无法读取，可从任务跟进重新查询。</p>}
            <ul className="related-tasks">{relatedTasks.slice(0, 3).map((task) => <li key={task.id}><Link to={`/maintenance/tasks/${encodeURIComponent(task.id)}`}><span><strong>{taskStatusLabels[task.status] || task.status}</strong><small>{task.planned_date || '未安排日期'} · {task.assignee_crew_id || '未分配班组'}</small>{task.feedback_result && <small>{cleanTaskFeedback(task.feedback_result)}</small>}</span><ChevronRight size={18} aria-hidden="true" /></Link></li>)}</ul>
          </section>}

          <nav className={`device-detail__actions${actionsPinned ? ' device-detail__actions--pinned' : ''}`} aria-label="设备后续操作">
            <Link className="device-detail__primary-action" to={`/maintenance?view=suggestions&q=${encodeURIComponent(assetnum)}`}><Wrench size={17} aria-hidden="true" />查看检修建议</Link>
            <Link to={`/maintenance?view=tasks&assetnum=${encodeURIComponent(assetnum)}`}><ClipboardList size={17} aria-hidden="true" />相关任务</Link>
            <Link to={`/assistant?assetnum=${encodeURIComponent(assetnum)}`}><Bot size={17} aria-hidden="true" />AI 助手</Link>
          </nav>
          <p className="device-detail__disclaimer">风险表示未来产生故障工单的可能性，不等同于实际故障发生时间；检修参考需结合现场情况判断。</p>
        </>
      )}
    </div>
  )
}
