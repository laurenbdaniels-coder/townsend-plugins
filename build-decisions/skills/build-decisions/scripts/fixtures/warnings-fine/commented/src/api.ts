import ky from 'ky'
/*
old client, kept for reference:
import axios from 'axios'
*/
export const api = ky.create({ prefixUrl: '/api' })
