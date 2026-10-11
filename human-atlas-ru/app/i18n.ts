import NAMES from './names-ru-la.json';
type Side='left'|'right';
type RuGender='m'|'f'|'n'|'p';
type LaGender='m'|'f'|'n'|'mp'|'fp'|'np';
const DICT=NAMES as unknown as Record<string,[string,RuGender,string,LaGender]>;
/** "left ventricle", "right coronary artery" etc. name distinct structures, so the side word stays part of the term. */
const KEEP='(?!(?:ventricle|atrium|coronary artery|hepatic|portal vein|liver|colic artery|lobe branch|side of)\\b)';
const LEAD=new RegExp(`^(left|right)\\s+${KEEP}`);
const ANY=new RegExp(`\\b(left|right)\\s+${KEEP}`,'g');
const RU_SIDE:Record<Side,Record<RuGender,string>>={left:{m:'левый',f:'левая',n:'левое',p:'левые'},right:{m:'правый',f:'правая',n:'правое',p:'правые'}};
const LA_SIDE:Record<Side,Record<LaGender,string>>={left:{m:'sinister',f:'sinistra',n:'sinistrum',mp:'sinistri',fp:'sinistrae',np:'sinistra'},right:{m:'dexter',f:'dextra',n:'dextrum',mp:'dextri',fp:'dextrae',np:'dextra'}};
const cap=(s:string)=>s.charAt(0).toUpperCase()+s.slice(1);
export interface Localized {ru:string;la:string;en:string;search:string}
const cache=new Map<string,Localized>();
export const normalize=(s:string)=>s.toLowerCase().replace(/ё/g,'е');
/** Russian and Latin names for a BodyParts3D/FMA English name, with left/right agreed in gender. */
export function localize(name:string):Localized{
 const hit=cache.get(name);if(hit)return hit;
 let key=name.toLowerCase().trim(),lead:Side|'' ='',mid:Side|''='';
 const m=key.match(LEAD);if(m){lead=m[1] as Side;key=key.slice(m[0].length);}
 key=key.replace(ANY,(_,s:Side)=>{mid||=s;return '';}).replace(/\s+/g,' ').trim();
 const entry=DICT[key];let ru=name,la='';
 if(entry){
  const [r,g,l,lg]=entry;ru=r;la=l;
  if(lead){ru=`${RU_SIDE[lead][g]} ${ru}`;la=`${la} ${LA_SIDE[lead][lg]}`;}
  if(mid&&mid!==lead){ru+=mid==='left'?' (слева)':' (справа)';la+=mid==='left'?' (sin.)':' (dext.)';}
 }
 const out={ru:cap(ru),la:la?cap(la):'',en:name,search:normalize(`${ru} ${la} ${name}`)};
 cache.set(name,out);return out;
}
const PLURAL=new Intl.PluralRules('ru-RU');
/** pieces(1)='часть', pieces(3)='части', pieces(5)='частей' */
export function plural(n:number,one:string,few:string,many:string){const r=PLURAL.select(n);return r==='one'?one:r==='few'?few:many;}
export const num=(n:number)=>n.toLocaleString('ru-RU');
