export function visibleSuggestionReason(reason: string) {
  const risk = reason.match(/^90 日复发风险\s+([0-9.]+)$/)
  if (risk) {
    const value = Number(risk[1])
    return Number.isFinite(value)
      ? `未来 90 天内再次出现故障工单的风险参考值：${Math.round(value * 100)}%`
      : '未来 90 天内再次出现故障工单的风险参考值'
  }

  const history = reason.match(/^近史\s+(\d+)\/(\d+)\s+条含「(.+)」$/)
  if (history) return `近 ${history[2]} 条相关工单中，有 ${history[1]} 条记录了“${history[3]}”现象`

  const crew = reason.match(/^匹配班组\s+(.+?)（合成排班，非真实人员）$/)
  if (crew) return `演示排班建议班组：${crew[1]}（安排前请核对现场班组）`

  const spare = reason.match(/^备件\s+(.+?)\s+库存\s+(\d+)（合成库存，非真实备件）$/)
  if (spare) return `演示库存显示 ${spare[1]} 有 ${spare[2]} 件（安排前请核对现场库存）`

  if (reason.includes('虚构站点模拟权重')) return '站点参考信息已纳入建议排序（体验数据）'
  if (reason === '有可用检修班组（模拟）') return '演示排班显示有可用检修班组（请现场核实）'
  if (reason === '相关备件有库存（模拟）') return '演示库存显示有相关备件（请现场核实）'
  return reason
}

export function visibleTaskSuggestionReason(reason: string) {
  const labels: Record<string, string> = {
    '合成风险输入': '风险参考信息（体验数据）',
    '模拟站点重要度': '站点参考信息（体验数据）',
    '模拟班组及备件资源': '班组与备件参考信息（体验数据）',
  }
  return labels[reason] ?? visibleSuggestionReason(reason)
}

export function suggestionSourceExplanation(modelNote: string | null, dataNote: string | null) {
  const details: string[] = []
  if (modelNote?.includes('prediction_results.csv')) {
    details.push('风险数据来自外部预测结果文件 prediction_results.csv；接口未提供该数据的更新时间。')
  } else if (modelNote?.includes('统计基线')) {
    details.push('风险参考来自历史工单频次和复发间隔的统计估算；接口未提供该数据的更新时间。')
  } else if (modelNote) {
    details.push('接口未说明风险数据的具体来源和更新时间。')
  }
  if (dataNote) details.push('人员、备件和站点参考信息来自模拟数据，不代表现场排班或库存。')
  return details
}
