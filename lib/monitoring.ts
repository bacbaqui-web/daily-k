export type MonitorStatus={version:1;state:'running'|'ok'|'stopped'|'retrying';updatedAt:string;lastSuccessAt?:string|null;stoppedAt?:string;expectedUpdateBy?:string;nextRetryAt?:string};
export function isMonitorStatus(value:unknown):value is MonitorStatus{
 if(!value||typeof value!=='object')return false;
 const v=value as Partial<MonitorStatus>;
 const date=(s:unknown)=>typeof s==='string'&&Number.isFinite(Date.parse(s));
 return v.version===1&&['running','ok','stopped','retrying'].includes(v.state||'')&&date(v.updatedAt)&&
  (v.state==='stopped'?date(v.stoppedAt):date(v.expectedUpdateBy))&&
  (v.lastSuccessAt==null||date(v.lastSuccessAt))&&
  (v.state!=='retrying'||date(v.nextRetryAt));
}
export function monitorNotice(status:MonitorStatus|null,now:number){
 if(!status)return null;
 if(status.state==='stopped')return {title:'모니터링이 멈췄습니다',detail:'새 글과 댓글 갱신이 중단된 상태입니다.',at:status.stoppedAt!,label:'중단 확인'};
 if(now>Date.parse(status.expectedUpdateBy||''))return {title:'모니터링 상태 갱신이 지연되고 있습니다',detail:'수집이 중단됐거나 상태 확인이 지연되고 있을 수 있습니다.',at:status.updatedAt,label:'마지막 상태 확인'};
 if(status.state==='retrying')return {title:'연결을 기다리는 중입니다',detail:'일시적인 통신 오류로 재시도 대기 중입니다. 자동으로 다시 시도합니다.',at:status.nextRetryAt!,label:'다음 시도'};
 return null;
}
