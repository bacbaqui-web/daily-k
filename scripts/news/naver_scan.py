import asyncio,json
from playwright.async_api import async_playwright
async def main():
    articles={};errors=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        page=await browser.new_page()
        await page.route('**/*', lambda r: r.abort() if r.request.resource_type in ('image','media','font') else r.continue_())
        for sid in ['100','101','102','103','104','105','webtoon']:
            url=('https://search.naver.com/search.naver?where=news&query=%EC%9B%B9%ED%88%B0&sort=1' if sid=='webtoon' else 'https://news.naver.com/section/'+sid)
            try:
                r=await page.goto(url,wait_until='domcontentloaded',timeout=25000)
                if r.status>=400:raise ValueError('HTTP '+str(r.status))
                await page.wait_for_timeout(1000)
                links=await page.locator('a[href*="/article/"]').evaluate_all('(xs)=>xs.map(a=>({url:a.href,title:a.innerText.trim(),context:(a.closest("li")?.innerText||"").slice(0,320)})).filter(x=>x.title.length>12).slice(0,45)')
                for x in links:
                    x['url']=x['url'].split('?')[0];x['section']=sid
                    articles.setdefault(x['url'],x)
            except Exception as e:errors.append({'url':url,'error':str(e)[:120]})
        await browser.close()
    print(json.dumps({'articles':list(articles.values()),'errors':errors},ensure_ascii=False))
asyncio.run(main())
