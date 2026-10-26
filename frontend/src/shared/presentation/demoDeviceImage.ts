import gate01 from '../../assets/demo-gates/demo-gate-01.webp'
import gate02 from '../../assets/demo-gates/demo-gate-02.webp'
import gate03 from '../../assets/demo-gates/demo-gate-03.webp'
import gate04 from '../../assets/demo-gates/demo-gate-04.webp'

const demoImages = [gate01, gate02, gate03, gate04]

function stableImageIndex(assetnum: string) {
  let hash = 0
  for (const character of assetnum) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  return hash % demoImages.length
}

export function demoImageForDevice(assetnum: string) {
  return demoImages[stableImageIndex(assetnum)]
}
