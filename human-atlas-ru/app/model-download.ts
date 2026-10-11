/** Static hosts may serve .gz as a compressed response or as a gzip file.
 * Fetch already decodes Content-Encoding; inspect the payload to avoid decoding twice.
 */
export async function decodeModelResponse(response:Response,expectedBytes:number,compressed:boolean):Promise<ArrayBuffer>{
 if(!response.ok)throw new Error('Не удалось загрузить файл модели.');
 const raw=await response.arrayBuffer(),payload=response.url.endsWith('.txt')?Uint8Array.from(atob(new TextDecoder().decode(raw).trim()),c=>c.charCodeAt(0)).buffer:raw,signature=new Uint8Array(payload,0,Math.min(2,payload.byteLength));
 const gzip=compressed&&signature[0]===0x1f&&signature[1]===0x8b;
 const buffer=gzip?await new Response(new Blob([payload]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():payload;
 if(buffer.byteLength!==expectedBytes)throw new Error('Файл модели загрузился не полностью. Перезагрузите страницу.');
 return buffer;
}
