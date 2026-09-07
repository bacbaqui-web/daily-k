export function unreadFirst<T extends {id:string}>(posts:T[],read:string[]):T[]{
 const seen=new Set(read);
 return [...posts.filter(p=>!seen.has(p.id)),...posts.filter(p=>seen.has(p.id))];
}
export function adjacentPost(order:string[],current:string|null,delta:number):string|undefined{
 const index=current===null?-1:order.indexOf(current);
 return index<0?undefined:order[index+delta];
}

export function within24Hours(post:{publishedAt?:string},now:number):boolean{
 const published=Date.parse(post.publishedAt||'');
 return Number.isFinite(published)&&published<=now&&now-published<24*60*60*1000;
}

export function nextUnreadPost(order:string[],current:string|null,read:string[]):string|undefined{
 const index=current===null?-1:order.indexOf(current);
 if(index<0)return undefined;
 const seen=new Set(read);
 return [...order.slice(index+1),...order.slice(0,index)].find(id=>!seen.has(id));
}
