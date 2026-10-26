import type { Middleware } from 'redux'

export const logger: Middleware = () => (next) => (action) => next(action)
