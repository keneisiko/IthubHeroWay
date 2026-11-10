import axios, { type AxiosResponse } from 'axios'
import toast from 'react-hot-toast'
import { clearAuthTokens, isAuthApiPath, readAuthSession, saveAuthSession } from './auth'

declare module 'axios' {
  interface AxiosRequestConfig {
    _heroSessionId?: string | null
    _retry?: boolean
    _transientRetry?: number
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
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
  const isAuth = isAuthApiPath(config.url)
  const session = isAuth ? null : readAuthSession()
  const sessionId = session?.id ?? null
  if (config._heroSessionId !== undefined && config._heroSessionId !== sessionId) {
    throw new axios.CanceledError('Session changed')
  }
  config._heroSessionId = sessionId
  if (session) config.headers.Authorization = `Bearer ${session.access}`
  else config.headers.delete('Authorization')

  const method = (config.method ?? 'get').toLowerCase()
  if (method !== 'get') {
    clearApiCache()
    return config
  }
  if (isAuth || config.signal) return config

  const key = `${sessionId ?? ''} ${session?.access.slice(-16) ?? ''} ${config.url} ${JSON.stringify(config.params ?? {})}`
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

let pendingRefresh: { sessionId: string; task: Promise<void> } | undefined

async function refreshSession(sessionId: string, failedBearer: unknown): Promise<void> {
  const current = readAuthSession()
  if (!current || current.id !== sessionId) throw new axios.CanceledError('Session changed')
  if (`Bearer ${current.access}` !== failedBearer) return

  try {
    const { data } = await api.post<{ access: string; refresh?: string }>(
      '/api/v1/auth/jwt/refresh/', { refresh: current.refresh },
    )
    const latest = readAuthSession()
    if (latest?.id !== sessionId || latest.refresh !== current.refresh) {
      throw new axios.CanceledError('Session changed')
    }
    saveAuthSession({ id: sessionId, access: data.access, refresh: data.refresh ?? current.refresh })
  } catch (error) {
    const latest = readAuthSession()
    if (latest?.id === sessionId && latest.access !== current.access) return
    if (axios.isAxiosError(error) && error.response?.status === 401 &&
        latest?.id === sessionId && latest.refresh === current.refresh) {
      clearAuthTokens()
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    throw error
  }
}

const TRANSIENT_RETRIES = 2
const TRANSIENT_DELAY_MS = 1500

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
      const sessionId = originalRequest._heroSessionId
      if (!sessionId || readAuthSession()?.id !== sessionId) throw error

      originalRequest._retry = true
      const existingRefresh = pendingRefresh
      let refreshTask = existingRefresh && existingRefresh.sessionId === sessionId ? existingRefresh.task : undefined
      if (!refreshTask) {
        const refresh = () => refreshSession(sessionId, originalRequest.headers.Authorization)
        const task = navigator.locks
          ? navigator.locks.request('hero-path-token-refresh', refresh)
          : refresh()
        refreshTask = task
        pendingRefresh = { sessionId, task }
        void task.finally(() => {
          if (pendingRefresh?.task === task) pendingRefresh = undefined
        }).catch(() => {})
      }
      await refreshTask
      return api(originalRequest)
    }

    const status = error.response?.status

    // Сервер перезапускается при выкатке несколько секунд и отвечает 502/503
    // (или не отвечает вовсе). Чтение тихо повторяем с паузой — иначе
    // открытая в эти секунды страница сдавалась с «Не удалось загрузить».
    // Изменения (POST и т. п.) не повторяем: их нельзя отправить дважды.
    const transient = !axios.isCancel(error) &&
      (!error.response || status === 502 || status === 503 || status === 504)
    const isRead = (originalRequest?.method ?? 'get').toLowerCase() === 'get'
    if (originalRequest && transient && isRead) {
      const attempt = (originalRequest._transientRetry ?? 0) + 1
      if (attempt <= TRANSIENT_RETRIES) {
        originalRequest._transientRetry = attempt
        await new Promise((resolve) => setTimeout(resolve, TRANSIENT_DELAY_MS * attempt * (0.75 + Math.random() * 0.5)))
        return api(originalRequest)
      }
    }

    // id у уведомления — одно на все упавшие запросы: страница шлёт их
    // пачкой, и раньше на один сбой вылезал столбик одинаковых сообщений.
    if (status === 403) {
      toast.error('Недостаточно прав', { id: 'api-forbidden' })
    } else if (status === 500 || status === 502 || status === 503 || status === 504) {
      toast.error('Сервер временно недоступен', { id: 'api-server-down' })
    }

    return Promise.reject(error)
  }
)

export default api
