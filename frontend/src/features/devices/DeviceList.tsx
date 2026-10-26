import { useState } from 'react'
import { ChevronRight, Search, SlidersHorizontal } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { DeviceIdentity } from '../../shared/components/DeviceIdentity'
import { DeviceImage } from '../../shared/components/DeviceImage'
import { StateMessage } from '../../shared/components/StateMessage'
import { deviceDisplayName } from '../../shared/presentation/deviceIdentity'
import { warningLevelClass } from '../../shared/presentation/warningLevel'
import { useDataProfile } from '../../shared/query/dataProfile'
import { useHighRiskDevices } from '../../shared/query/dataManagement'
import { useDevices } from '../../shared/query/devices'
import './devices.css'

export function DeviceList() {
  const query = useDevices()
  const profile = useDataProfile()
  const dataProfile = profile.data?.data_profile
  const [params, setParams] = useSearchParams()
  const [limit, setLimit] = useState(30)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const attention = params.get('view') === 'attention'
  const riskQuery = useHighRiskDevices(attention)
  const search = params.get('q') ?? ''
  const line = params.get('line') ?? ''
  const brand = params.get('brand') ?? ''
  const devices = query.data?.devices ?? []
  const lines = Array.from(new Set(devices.map((item) => item.line).filter((value): value is string => Boolean(value))))
  const brands = Array.from(new Set(devices.map((item) => item.brand).filter((value): value is string => Boolean(value))))
  const byAsset = new Map(devices.map((item) => [item.assetnum, item]))
  const riskDevices = riskQuery.data?.status === 'success' ? riskQuery.data.devices : []
  const source = attention ? riskDevices.map((item) => byAsset.get(item.assetnum)).filter((item) => item !== undefined) : devices
  const filtered = source.filter((item) => {
    const fields = [item.assetnum, deviceDisplayName(item.assetnum, dataProfile), item.station_name, item.line, item.brand]
    return (!search || fields.some((value) => value?.toLocaleLowerCase().includes(search.toLocaleLowerCase())))
      && (!line || item.line === line) && (!brand || item.brand === brand)
  })
  const riskByAsset = new Map(riskDevices.map((item) => [item.assetnum, item]))

  function setFilter(key: string, value: string) {
    setLimit(30)
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  return (
    <div className="devices-page device-list-page">
      <header className="devices-title"><h1>设备</h1></header>
      <section className="devices-panel" aria-labelledby="device-list-heading">
        <h2 id="device-list-heading" className="device-visually-hidden">设备列表</h2>
        <div className="device-search-row">
          <label className="device-search"><Search size={21} aria-hidden="true" /><span className="device-visually-hidden">搜索设备、车站、线路或品牌</span><input type="search" value={search} onChange={(event) => setFilter('q', event.target.value)} placeholder="搜索设备编号、车站或设备信息" /></label>
          <button className="device-filter-toggle" type="button" aria-label="筛选线路和品牌" aria-expanded={filtersOpen} aria-controls="device-extra-filters" onClick={() => setFiltersOpen((open) => !open)}><SlidersHorizontal size={22} aria-hidden="true" /></button>
        </div>
        <div className="device-view-switch" role="group" aria-label="设备视图">
          <button type="button" aria-pressed={!attention} onClick={() => setFilter('view', '')}>全部设备</button>
          <button type="button" aria-pressed={attention} onClick={() => setFilter('view', 'attention')}>高风险设备</button>
        </div>
        <div className="device-extra-filters" id="device-extra-filters" hidden={!filtersOpen}>
          <div><label htmlFor="device-line-filter">线路</label><select id="device-line-filter" value={line} onChange={(event) => setFilter('line', event.target.value)}><option value="">全部线路</option>{lines.map((value) => <option key={value} value={value}>{value}</option>)}</select></div>
          <div><label htmlFor="device-brand-filter">品牌</label><select id="device-brand-filter" value={brand} onChange={(event) => setFilter('brand', event.target.value)}><option value="">全部品牌</option>{brands.map((value) => <option key={value} value={value}>{value}</option>)}</select></div>
        </div>
        {query.isPending && <StateMessage title="正在读取设备列表" detail="从服务端获取设备信息。" />}
        {query.isError && <StateMessage title="设备列表读取失败" detail="检查连接后重试。" retry={() => void query.refetch()} />}
        {query.data && query.data.status !== 'success' && <StateMessage title="设备列表暂不可用" detail={query.data.message} />}
        {attention && riskQuery.isPending && <StateMessage title="正在读取高风险设备" detail="从服务端获取风险排序。" />}
        {attention && riskQuery.isError && <StateMessage title="高风险设备暂不可用" detail="检查连接后重试。" retry={() => void riskQuery.refetch()} />}
        {attention && riskQuery.data && riskQuery.data.status !== 'success' && <StateMessage title="高风险设备暂不可用" detail={riskQuery.data.message} />}
        {query.data?.status === 'success' && (!attention || riskQuery.data?.status === 'success') && <>
          <p className="device-count">{attention ? `高风险设备 · 前 ${riskDevices.length} 台，当前匹配 ${filtered.length} 台` : `当前显示 ${filtered.length} 台设备`}</p>
          {filtered.length === 0 ? <StateMessage title="没有匹配设备" detail="可调整搜索或筛选条件。" /> : <>
            <ul className="device-list" aria-label="设备列表">{filtered.slice(0, limit).map((item) => {
              const risk = riskByAsset.get(item.assetnum)
              return <li key={item.assetnum}>
                <Link to={`/devices/${encodeURIComponent(item.assetnum)}`}>
                  <DeviceImage assetnum={item.assetnum} className="device-list__image" />
                  <span className="device-list__info"><DeviceIdentity assetnum={item.assetnum} dataProfile={dataProfile} as="span" /><span>{item.station_name || '车站未提供'} · {item.line || '线路未提供'}</span><small>{item.brand || '品牌未提供'}</small>{risk?.warning_level && <em className={`device-list__warning ${warningLevelClass(risk.warning_level)}`}>{risk.warning_level}</em>}</span>
                  <ChevronRight className="device-list__chevron" size={20} aria-hidden="true" />
                </Link>
              </li>
            })}</ul>
            {filtered.length > limit && <button type="button" className="device-more" onClick={() => setLimit((current) => current + 30)}>显示更多设备</button>}
          </>}
        </>}
      </section>
    </div>
  )
}
