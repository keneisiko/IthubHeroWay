import axios, { type AxiosResponse } from 'axios'
import toast from 'react-hot-toast'
import { clearAuthTokens, isAuthApiPath } from './auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/*
 * Короткая память GET-ответов. Страницы грузят данные при каждом
 * открытии, и повторный заход в раздел мигал экраном загрузки ради
 * тех же самых данных. Теперь ответ младше CACHE_TTL отдаётся сразу,
 * одинаковые запросы, ушедшие одновременно (шапка и страница просят
 * профиль), идут на сервер одним.
 *
 * Память сбрасывается при любом изменении (POST/PATCH/PUT/DELETE) и
 * когда человек возвращается во вкладку: там данные могли поменяться
 * без него — куратор начислил награду.
 */
const CACHE_TTL = 15_000
const responseCache = new Map<string, { at: number; response: AxiosResponse }>()
const inflight = new Map<string, Promise<AxiosResponse>>()
const networkAdapter = axios.getAdapter(api.defaults.adapter)

// страницы сортируют полученные списки на месте — каждому достаётся копия
const copy = <T,>(data: T): T => (typeof data === 'object' && data !== null ? structuredClone(data) : data)

export function clearApiCache(): void {
  responseCache.clear()
  inflight.clear()
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') clearApiCache()
  })
}

api.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toLowerCase()
  if (method !== 'get') {
    clearApiCache()
    return config
  }
  if (isAuthApiPath(config.url)) return config

  const token = localStorage.getItem('access_token') ?? ''
  const key = `${token.slice(-16)} ${config.url} ${JSON.stringify(config.params ?? {})}`
  const hit = responseCache.get(key)
  if (hit && Date.now() - hit.at < CACHE_TTL) {
    config.adapter = async () => ({ ...hit.response, data: copy(hit.response.data), config })
    return config
  }
  config.adapter = (cfg) => {
    let pending = inflight.get(key)
    if (!pending) {
      pending = networkAdapter(cfg)
      inflight.set(key, pending)
      pending
        .then((response) => {
          if (inflight.get(key) === pending) {
            responseCache.set(key, { at: Date.now(), response })
          }
        })
        .catch(() => {})
        .finally(() => {
          if (inflight.get(key) === pending) inflight.delete(key)
        })
    }
    return pending.then(
      (response) => ({ ...response, data: copy(response.data), config: cfg }),
      (error: unknown) => {
        if (!axios.isAxiosError(error) || !error.response) throw error
        throw axios.AxiosError.from(error, error.code, cfg, error.request, {
          ...error.response,
          data: copy(error.response.data),
          config: cfg,
        })
      },
    )
  }
  return config
})

let isRefreshing = false
let failedQueue: { resolve: (v: unknown) => void; reject: (e: unknown) => void }[] = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => {
    if ((response.config.method ?? 'get').toLowerCase() !== 'get') clearApiCache()
    return response
  },
  async (error) => {
    const originalRequest = error.config
    const requestUrl = String(originalRequest?.url || '')

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthApiPath(requestUrl)
    ) {
      const refreshToken = localStorage.getItem('refresh_token')

      if (!refreshToken) {
        clearAuthTokens()
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        }).catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const res = await api.post('/api/v1/auth/jwt/refresh/', { refresh: refreshToken })
        const newAccess = res.data.access
        localStorage.setItem('access_token', newAccess)
        api.defaults.headers.common['Authorization'] = `Bearer ${newAccess}`
        processQueue(null, newAccess)
        originalRequest.headers.Authorization = `Bearer ${newAccess}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearAuthTokens()
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    const status = error.response?.status
    if (status === 403) {
      toast.error('Недостаточно прав')
    } else if (status === 500 || status === 502 || status === 503) {
      toast.error('Сервер временно недоступен')
    }

    return Promise.reject(error)
  }
)

export default api
