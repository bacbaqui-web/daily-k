export type BodyImage = {url:string;width:number;height:number};
export type CommunityMedia = {
 imageUrl?:string|null;
 videoUrl?:string|null;
 videoPosterUrl?:string|null;
 bodyImages?:BodyImage[];
 bodyImagesSourceUrl?:string;
 bodyImagesVerifiedAt?:string;
};

export function imageKey(url:string):string {
 const parsed=new URL(url);parsed.hash='';return parsed.href;
}
export function isPublicImageUrl(value:unknown):value is string {
 if(typeof value!=='string'||value!==value.trim())return false;
 try {
  const u=new URL(value),host=u.hostname.toLowerCase();
  return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&
   host.includes('.')&&!host.endsWith('.')&&!host.endsWith('.localhost')&&!host.endsWith('.local')&&
   !/^\d+(?:\.\d+){3}$/.test(host)&&!host.includes(':');
 } catch {return false}
}
export function isBodyImages(value:unknown):value is BodyImage[] {
 if(!Array.isArray(value))return false;
 const seen=new Set<string>();
 return value.every(image=>{
  if(!image||typeof image!=='object'||!isPublicImageUrl(image.url)||
   !Number.isSafeInteger(image.width)||image.width<=0||!Number.isSafeInteger(image.height)||image.height<=0)return false;
  const key=imageKey(image.url);if(seen.has(key))return false;seen.add(key);return true;
 });
}
export function communityBodyImages(story:CommunityMedia):Array<{url:string;width?:number;height?:number}> {
 // An explicit empty array means the source has no body images. Historical
 // video posters stay posters; older image-only records still show one image.
 const images=story.bodyImages??(!story.videoUrl&&story.imageUrl?[{url:story.imageUrl}]:[]);
 const seen=new Set<string>();
 return images.filter(image=>{
  if(!isPublicImageUrl(image.url))return false;
  const key=imageKey(image.url);if(seen.has(key))return false;seen.add(key);return true;
 });
}
export function communityThumbnail(story:CommunityMedia):string|null {
 return story.imageUrl||story.videoPosterUrl||story.bodyImages?.[0]?.url||null;
}
