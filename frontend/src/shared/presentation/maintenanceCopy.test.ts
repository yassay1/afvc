import { expect, test } from 'vitest'
import { suggestionSourceExplanation, visibleSuggestionReason, visibleTaskSuggestionReason } from './maintenanceCopy'

test('turns service reason codes into field language without changing the underlying reason', () => {
  expect(visibleSuggestionReason('90 日复发风险 0.75')).toBe('未来 90 天内再次出现故障工单的风险参考值：75%')
  expect(visibleSuggestionReason('近史 5/8 条含「暂停服务」')).toBe('近 8 条相关工单中，有 5 条记录了“暂停服务”现象')
  expect(visibleSuggestionReason('站点重要度 0.96（虚构站点模拟权重）')).toBe('站点参考信息已纳入建议排序（体验数据）')
})

test('summarizes technical task reasons for the card while retaining original reason separately', () => {
  expect(visibleTaskSuggestionReason('合成风险输入')).toBe('风险参考信息（体验数据）')
  expect(visibleTaskSuggestionReason('模拟站点重要度')).toBe('站点参考信息（体验数据）')
  expect(visibleTaskSuggestionReason('模拟班组及备件资源')).toBe('班组与备件参考信息（体验数据）')
  expect(visibleTaskSuggestionReason('90 日复发风险 0.75')).toContain('75%')
})

test('explains available risk source and states when freshness is absent', () => {
  expect(suggestionSourceExplanation('风险输入：prediction_results.csv', '资源为模拟数据')).toEqual([
    '风险数据来自外部预测结果文件 prediction_results.csv；接口未提供该数据的更新时间。',
    '人员、备件和站点参考信息来自模拟数据，不代表现场排班或库存。',
  ])
  expect(suggestionSourceExplanation('统计基线', null)[0]).toContain('接口未提供该数据的更新时间')
})
