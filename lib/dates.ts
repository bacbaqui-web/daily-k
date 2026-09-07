export function todayInKorea(now = new Date()): string {
 const parts = new Intl.DateTimeFormat('en-US', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
 return ['year','month','day'].map(key=>parts.find(p=>p.type===key)!.value).join('-');
}
export function shiftDate(day:string, delta:number):string {
 const date = new Date(`${day}T12:00:00Z`);
 date.setUTCDate(date.getUTCDate()+delta);
 return date.toISOString().slice(0,10);
}
