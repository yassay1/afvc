import { expect, test } from 'vitest'
import { demoDeviceNameEntries, deviceDisplayName } from './deviceIdentity'
import { demoImageForDevice } from './demoDeviceImage'

test('demo names are stable and preserve the business identifier separately', () => {
  const entries = demoDeviceNameEntries()
  expect(entries).toHaveLength(36)
  expect(new Set(entries.map(([, name]) => name)).size).toBe(36)
  expect(deviceDisplayName('DEMO-AGM-018', 'demo')).toBe('月港站闸机 03')
  expect(deviceDisplayName('UNKNOWN-ASSET', 'demo')).toBe('UNKNOWN-ASSET')
})

test('production device names never use the demo mapping', () => {
  expect(deviceDisplayName('DEMO-AGM-018', 'production')).toBe('DEMO-AGM-018')
  expect(deviceDisplayName('ASSET-18', 'production', '18号闸机')).toBe('18号闸机')
  expect(deviceDisplayName('ASSET-18', 'production')).toBe('ASSET-18')
  expect(deviceDisplayName('DEMO-AGM-018', undefined)).toBe('DEMO-AGM-018')
})

test('demo gate image mapping is stable and offers four distinct variants', () => {
  const ids = Array.from({ length: 36 }, (_, index) => `DEMO-AGM-${String(index + 1).padStart(3, '0')}`)
  expect(demoImageForDevice('DEMO-AGM-018')).toBe(demoImageForDevice('DEMO-AGM-018'))
  expect(new Set(ids.map(demoImageForDevice)).size).toBe(4)
})
