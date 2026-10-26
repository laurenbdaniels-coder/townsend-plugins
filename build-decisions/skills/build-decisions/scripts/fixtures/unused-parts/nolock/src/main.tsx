import React from 'react'
import { createRoot } from 'react-dom/client'
import { sortBy } from 'lodash'

createRoot(document.getElementById('root')!).render(<p>{sortBy([2, 1]).join()}</p>)
