import { expect, test } from 'vitest'
import { warningLevelClass } from './warningLevel'

test('uses colors that match the service-provided warning label', () => {
  expect(warningLevelClass('红色预警')).toBe('warning-level--red')
  expect(warningLevelClass('橙色预警')).toBe('warning-level--orange')
  expect(warningLevelClass('黄色预警')).toBe('warning-level--yellow')
  expect(warningLevelClass('绿色关注')).toBe('warning-level--green')
})

test('keeps unknown service labels neutral without inventing a meaning', () => {
  expect(warningLevelClass('关注')).toBe('warning-level--neutral')
  expect(warningLevelClass(null)).toBe('warning-level--neutral')
  expect(warningLevelClass('toString')).toBe('warning-level--neutral')
})
