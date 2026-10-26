import { Link, useSearchParams } from 'react-router'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { StateMessage } from '../../shared/components/StateMessage'
import { useDataOverview, useHighRiskDevices } from '../../shared/query/dataManagement'
import { useDataProfile } from '../../shared/query/dataProfile'
import type { DataOverviewResponse } from '../../shared/api/types'
import { warningLevelClass } from '../../shared/presentation/warningLevel'
import './data-management.css'

function Distribution({ title, rows }: { title: string; rows: { name: string; count: number }[] }) {
  return <div className="data-distribution-section"><h3>{title}</h3>{rows.length ? <ol className="data-distribution">{rows.map((row, index) => <li key={`${index}-${row.name}`}><span>{row.name}</span><strong>{row.count}</strong></li>)}</ol> : <p className="data-note">当前没有可展示的分布数据。</p>}</div>
}

function formatDate(value: string | null | undefined) {
  if (!value) return '暂无记录'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(date)
}

function cleanDescription(value: string) {
  return value.replace(/^\s*合成工单[：:]\s*/, '')
}

function OverviewContent({ data }: { data: DataOverviewResponse }) {
  const source = data.data_backend === 'file' ? '文件' : data.data_backend === 'sql' ? '数据库' : '未说明'
  return <>
    <section className="data-panel data-summary">
      <div className="data-panel-head"><h2>数据集概况</h2><span>来源：{source}</span></div>
      <div className="data-metrics">
        <div className="data-metric--primary"><span>工单记录</span><strong>{data.basic_metrics.workorder_count}</strong></div>
        <div className="data-metric--primary"><span>设备</span><strong>{data.basic_metrics.device_count}</strong></div>
        <div className="data-metric--primary"><span>车站</span><strong>{data.basic_metrics.station_count}</strong></div>
      </div>
      <p className="data-summary__coverage">覆盖 <strong>{data.basic_metrics.line_count}</strong> 条线路 <span>·</span> <strong>{data.basic_metrics.brand_count}</strong> 个品牌</p>
      <div className="data-period"><h3>工单记录时间</h3><strong>{formatDate(data.time_range.start_time)} — {formatDate(data.time_range.end_time)}</strong></div>
      <p className="data-note">统计范围为当前已读取记录，不代表全线网总量；记录时间不等于实际故障发生时间。</p>
    </section>
    <section className="data-panel data-distribution"><h2>数据分布</h2><div className="data-grid"><Distribution title="线路" rows={data.line_distribution || []} /><Distribution title="品牌" rows={data.brand_distribution || []} /></div></section>
    <section className="data-panel"><div className="data-panel-head"><h2>常见工单现象</h2><span>按记录数量</span></div>{data.fault_description_top?.length ? <ol className="data-distribution data-faults">{data.fault_description_top.map((row, index) => <li key={`${index}-${row.name}`}><span>{cleanDescription(row.name)}</span><strong>{row.count}</strong></li>)}</ol> : <p className="data-note">当前没有可展示的工单现象。</p>}<p className="data-note data-fault-note">工单现象可作为检查参考，不代表已确认故障原因。</p></section>
  </>
}

function OverviewView() {
  const query = useDataOverview()
  if (query.isPending) return <StateMessage title="正在读取数据概览" detail="从当前工单数据源获取统计。" />
  if (query.isError) return <StateMessage title="数据概览读取失败" detail="请检查数据源和服务状态后重试。" retry={() => void query.refetch()} />
  if (query.data.status !== 'success') return <StateMessage title="数据概览暂不可用" detail={query.data.message} />
  if (query.data.basic_metrics.workorder_count === 0) return <StateMessage title="暂无工单记录" detail="当前数据集为空，概览分布暂不能展示。" />
  return <OverviewContent data={query.data} />
}

function RiskView() {
  const query = useHighRiskDevices()
  const profile = useDataProfile()
  if (query.isPending) return <StateMessage title="正在读取高风险设备" detail="从服务端获取风险排序和来源说明。" />
  if (query.isError) return <StateMessage title="高风险列表读取失败" detail="请检查数据源和服务状态后重试。" retry={() => void query.refetch()} />
  const data = query.data
  if (data.status !== 'success') return <StateMessage title="高风险列表暂不可用" detail={data.message} />
  const source = data.prediction_tier === 'statistical_baseline' || data.prediction_source === 'statistical_baseline'
    ? '历史工单统计估算'
    : data.prediction_tier === 'model' ? '外部风险预测' : '风险评估'
  const sourceDetail = data.prediction_source === 'external_prediction_csv'
    ? '风险参考来自外部预测结果文件 prediction_results.csv；接口未提供数据更新时间。'
    : source === '历史工单统计估算'
      ? '风险参考根据历史工单频次和复发间隔估算；接口未提供数据更新时间。'
      : '接口未说明风险数据的具体来源和更新时间。'
  const counts = new Map<string, number>()
  data.devices.forEach((device) => device.main_risk_factors?.forEach((factor) => counts.set(factor, (counts.get(factor) || 0) + 1)))
  const sharedFactors = [...counts].filter(([, count]) => count === data.devices.length).map(([factor]) => factor)
  const friendlyFactor = (factor: string) => ({
    '预测结果来自外部模型结果表': '风险参考当前预测结果。',
    '系统按 90 天风险进行高风险设备排序': '列表按 90 日风险从高到低排序。',
    '预警等级由模型风险结果转换生成': '预警等级依据风险结果生成。',
  }[factor] || factor)
  return <section className="data-panel risk-panel">
    <div className="data-panel-head"><h2>风险排序</h2><span>{data.devices.length} 台 · {source}</span></div>
    <p className="data-note risk-intro">列表依据未来工单复发风险排序；风险不是设备故障日期预报。</p>
    <details className="risk-method"><summary>了解风险来源与口径</summary><p>{sourceDetail}</p>{sharedFactors.length > 0 && <ul>{sharedFactors.map((factor) => <li key={factor}>{friendlyFactor(factor)}</li>)}</ul>}</details>
    {data.devices.length === 0 ? <StateMessage title="暂无风险设备" detail="当前没有可展示的风险评估结果。" /> : <ol className="risk-list" aria-label="高风险设备排序">{data.devices.map((device, index) => {
      const deviceFactors = (device.main_risk_factors || []).filter((factor) => (counts.get(factor) || 0) < data.devices.length)
      return <li key={device.assetnum}>
        <div className="risk-card-head"><span className="risk-rank" aria-label={`排序第 ${index + 1} 名`}>{String(index + 1).padStart(2, '0')}</span><div className="risk-device"><Link to={`/devices/${encodeURIComponent(device.assetnum)}`}><DeviceIdentity assetnum={device.assetnum} dataProfile={profile.data?.data_profile} /></Link><span>{profile.data?.data_profile === 'demo' ? device.line || '线路未提供' : `${device.station_name || '车站未提供'} · ${device.line || '线路未提供'}`}</span></div>{device.warning_level && <span className={`risk-level ${warningLevelClass(device.warning_level)}`}>{device.warning_level}</span>}</div>
        <div className="risk-values"><div><span>30 日复发风险</span><strong>{typeof device.risk_30d === 'number' ? `${Math.round(device.risk_30d * 100)}%` : '不可用'}</strong></div><div><span>90 日复发风险</span><strong>{typeof device.risk_90d === 'number' ? `${Math.round(device.risk_90d * 100)}%` : '不可用'}</strong></div></div>
        {deviceFactors.length > 0 && <details className="risk-factors"><summary>查看风险因素</summary><ul>{deviceFactors.map((factor) => <li key={factor}>{factor}</li>)}</ul></details>}
      </li>
    })}</ol>}
  </section>
}

export function DataManagementPage() {
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'risk' ? 'risk' : 'overview'
  function switchView(next: string) { setParams({ view: next }) }
  return <div className="data-page"><Link className="back-link" to="/workbench">返回工作台</Link><div><h1>{view === 'overview' ? '数据概览' : '高风险设备'}</h1><p>{view === 'overview' ? '工单记录规模、覆盖范围与常见现象。' : '按未来工单复发风险查看设备排序。'}</p></div><div className="segment" role="group" aria-label="数据视图"><button type="button" aria-pressed={view === 'overview'} onClick={() => switchView('overview')}>数据概览</button><button type="button" aria-pressed={view === 'risk'} onClick={() => switchView('risk')}>高风险设备</button></div>{view === 'overview' ? <OverviewView /> : <RiskView />}</div>
}
