"""Read public article pages in an isolated browser; never solve access challenges."""
import asyncio, ipaddress, json, socket, sys
from functools import lru_cache
from datetime import datetime, timezone
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

@lru_cache(maxsize=512)
def public_url(url):
    try:
        u=urlsplit(url)
        if u.scheme not in ('http','https') or u.username or u.password or u.port not in (None,80,443): return False
        return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(u.hostname,None))
    except (ValueError,OSError,TypeError): return False

async def main(urls):
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context()
        async def route(r):
            if r.request.resource_type in ('image','media','font') or not public_url(r.request.url): await r.abort()
            else: await r.continue_()
        await context.route('**/*',route)
        for url in list(dict.fromkeys(urls))[:21]:
            item={'url':url,'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'failed'}
            page=await context.new_page()
            try:
                if not public_url(url): raise ValueError('non-public URL')
                response=await page.goto(url,wait_until='domcontentloaded',timeout=30000)
                await page.wait_for_timeout(2000)
                title=await page.title()
                body=await page.locator('body').inner_text(timeout=5000)
                if response and response.status>=400: raise ValueError('HTTP '+str(response.status))
                if any(x in (title+' '+body[:1500]).lower() for x in ['verify you are human','access denied','captcha','접근이 차단','로봇이 아닙니다']): raise ValueError('access challenge; not bypassed')
                nodes=page.locator('#dic_area, article, [itemprop=articleBody], .article-text, #articleBodyContents, #article-view-content-div, .article_view, .article_body')
                texts=[]
                for node in await nodes.all():
                    if await node.is_visible(): texts.append(await node.inner_text(timeout=3000))
                text=max(texts,key=len,default='')
                if len(text.strip())<200: raise ValueError('article body too short')
                metadata=await page.locator('meta[property="og:article:author"], meta[property="og:site_name"], meta[property="article:published_time"], .media_end_head_info_datestamp_time').evaluate_all('(xs)=>xs.map(x=>({key:x.getAttribute("property")||"date",value:x.getAttribute("content")||x.getAttribute("data-date-time")||x.innerText}))')
                item.update(metadata=metadata,status='read',finalUrl=page.url,title=title,text=text[:12000],truncated=len(text)>12000)
            except Exception as e: item['error']=str(e)[:180]
            finally: await page.close()
            results.append(item)
            await asyncio.sleep(2)
        await browser.close()
    print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__': asyncio.run(main(json.load(sys.stdin)))
