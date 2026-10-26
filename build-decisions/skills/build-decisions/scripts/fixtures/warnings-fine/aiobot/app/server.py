from aiohttp import web
import requests


async def hook(request):
    requests.post('https://example.com/notify')
    return web.Response(text='ok')
