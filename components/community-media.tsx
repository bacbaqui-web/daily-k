'use client';
import {useState} from 'react';
import {communityBodyImages,type CommunityMedia} from '../lib/community-media';

function BodyImage({url,width,height,title,index,total,sourceUrl}:{url:string;width?:number;height?:number;title:string;index:number;total:number;sourceUrl:string}) {
 const [failed,setFailed]=useState(false);
 return <figure className="community-body-image">{failed?
  <p className="community-media-error">본문 이미지 {index}/{total}을 불러오지 못했습니다. <a href={sourceUrl} target="_blank" rel="noopener noreferrer">원문에서 확인해 주세요.</a></p>:
  <img className="community-image" src={url} width={width} height={height} alt={`${title} · 본문 이미지 ${index}/${total}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>
 }</figure>;
}
export function CommunityBodyImages({story}:{story:CommunityMedia&{title:string;sources:{url:string}[]}}) {
 const images=communityBodyImages(story);
 if(!images.length)return null;
 return <section className="community-body-images" aria-label={`본문 이미지 ${images.length}장`}>
  {images.length>1&&<p className="community-image-count">본문 이미지 {images.length}장 · 원문 순서</p>}
  {images.map((image,i)=><BodyImage key={image.url} {...image} title={story.title} index={i+1} total={images.length} sourceUrl={story.bodyImagesSourceUrl||story.sources[0].url}/>)}
 </section>;
}
