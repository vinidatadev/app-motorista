// Centraliza configuracao de tiles e geocoding.
// Producao: Mapbox (tiles) + OpenCage (geocoding).
// Fallback dev: OpenStreetMap (tiles) + Nominatim (geocoding).

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const OPENCAGE_KEY = import.meta.env.VITE_OPENCAGE_KEY || ''

export function temMapbox() {
  return !!MAPBOX_TOKEN
}

export function temOpenCage() {
  return !!OPENCAGE_KEY
}

/**
 * Retorna a URL do tile layer apropriada.
 * Se VITE_MAPBOX_TOKEN estiver definida, usa tiles Mapbox (gratis ate 50k loads/mes).
 * Senão, cai para OSM (dev/teste local).
 */
export function tileUrl() {
  if (MAPBOX_TOKEN) {
    return `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{z}/{x}/{y}@2x?access_token=${MAPBOX_TOKEN}`
  }
  return 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
}

export function tileAttribution() {
  if (MAPBOX_TOKEN) {
    return '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }
  return '&copy; OpenStreetMap'
}

export function tileMaxZoom() {
  return MAPBOX_TOKEN ? 20 : 19
}

/**
 * Mapeia nome de estado retornado pelo geocoder para sigla UF.
 */
export const UF_POR_NOME = {
  'Acre':'AC','Alagoas':'AL','Amapá':'AP','Amazonas':'AM','Bahia':'BA','Ceará':'CE',
  'Distrito Federal':'DF','Espírito Santo':'ES','Goiás':'GO','Maranhão':'MA',
  'Mato Grosso':'MT','Mato Grosso do Sul':'MS','Minas Gerais':'MG','Pará':'PA',
  'Paraíba':'PB','Paraná':'PR','Pernambuco':'PE','Piauí':'PI','Rio de Janeiro':'RJ',
  'Rio Grande do Norte':'RN','Rio Grande do Sul':'RS','Rondônia':'RO','Roraima':'RR',
  'Santa Catarina':'SC','São Paulo':'SP','Sergipe':'SE','Tocantins':'TO'
}

/**
 * Reverse geocoding: lat/lng -> endereco.
 * Usa OpenCage se VITE_OPENCAGE_KEY estiver definida (2.500 req/dia gratis),
 * senão cai pra Nominatim (OSM).
 *
 * Retorna: { cep, rua, numero, bairro, cidade, estado } ou null.
 */
export async function reverseGeocode(lat, lng) {
  if (OPENCAGE_KEY) {
    return _reverseOpenCage(lat, lng)
  }
  return _reverseNominatim(lat, lng)
}

/**
 * Forward geocoding: endereco -> lat/lng (resultado único).
 * Usa OpenCage se VITE_OPENCAGE_KEY estiver definida, senão cai pra Nominatim.
 * Retorna: { lat, lng } ou null.
 */
export async function forwardGeocode(query) {
  if (OPENCAGE_KEY) {
    return _forwardOpenCage(query)
  }
  return _forwardNominatim(query)
}

// ---------- OpenCage ----------

async function _reverseOpenCage(lat, lng) {
  try {
    const url = `https://api.opencagedata.com/geocode/v1/json?q=${lat}+${lng}&key=${OPENCAGE_KEY}&language=pt&countrycode=br&limit=1&no_annotations=1`
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
    if (!res.ok) return null
    const data = await res.json()
    const hit = data?.results?.[0]
    if (!hit) return null
    const c = hit.components || {}
    return {
      cep: c.postcode || null,
      rua: c.road || c.pedestrian || null,
      numero: c.house_number || '',
      bairro: c.suburb || c.neighbourhood || c.quarter || null,
      cidade: c.city || c.town || c.village || c.municipality || null,
      estado: c.state
        ? (UF_POR_NOME[c.state] || c.state_code || c.state.slice(0, 2).toUpperCase())
        : null
    }
  } catch { return null }
}

async function _forwardOpenCage(query) {
  try {
    const url = `https://api.opencagedata.com/geocode/v1/json?q=${encodeURIComponent(query)}&key=${OPENCAGE_KEY}&language=pt&countrycode=br&limit=1&no_annotations=1`
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
    if (!res.ok) return null
    const data = await res.json()
    const hit = data?.results?.[0]
    if (!hit?.geometry) return null
    const { lat, lng } = hit.geometry
    if (lat == null || lng == null) return null
    return { lat: Number(lat), lng: Number(lng) }
  } catch { return null }
}

// ---------- Nominatim (fallback) ----------

async function _reverseNominatim(lat, lng) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&addressdetails=1&accept-language=pt-BR`
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
    if (!res.ok) return null
    const data = await res.json()
    const a = data?.address
    if (!a) return null
    const nomeCidade = a.city || a.town || a.village || a.municipality || a.county
    return {
      cep: a.postcode || null,
      rua: a.road || null,
      numero: a.house_number || '',
      bairro: a.suburb || a.neighbourhood || null,
      cidade: nomeCidade || null,
      estado: a.state ? (UF_POR_NOME[a.state] || a.state.slice(0, 2).toUpperCase()) : null
    }
  } catch { return null }
}

async function _forwardNominatim(query) {
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&accept-language=pt-BR&q=${encodeURIComponent(query)}`
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
    if (!res.ok) return null
    const data = await res.json()
    const hit = data?.[0]
    if (!hit) return null
    return { lat: Number(hit.lat), lng: Number(hit.lon) }
  } catch { return null }
}
