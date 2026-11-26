import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {preparePhoto,PHOTO_LIMITS} from '../../frontend/src/photo/preparePhoto.js';
const fixtures = new URL('./fixtures/', import.meta.url);
const heifHeader = Buffer.from('000000186674797068656963000000006d69663168656963', 'hex');
// Routing tests mock the native HTTP adapter. Only its HEIF signature is needed.
const input = name => new File([
  name.endsWith('.tiff') ? fs.readFileSync(new URL('geometry.tiff', fixtures)) : heifHeader,
], name);
const converted = file => ({ok:true,status:200,json:async()=>({jpeg:Buffer.from('converted jpeg bytes').toString('base64'),info:{outputFormat:'JPEG',originalBytes:file.size,localDecoderFallback:true}})});

test('HEIF/TIFF always use local adapter without Image or browser codec',async()=>{
 for(const name of ['single.heic','crew.heif','large-single.tiff']){
  const original=input(name);let calls=0;
  globalThis.fetch=async(url,opts)=>{calls++;assert.equal(url,'/api/prepare-photo');assert.equal(opts.body,original);return converted(original);};
  const result=await preparePhoto(original);
  assert.equal(calls,1);assert.equal(result.file.type,'image/jpeg');assert.equal(result.info.localDecoderFallback,true);
 }
});
test('compliant JPEG remains byte identical through original path',async()=>{
 const original=new File([fs.readFileSync(new URL('geometry.jpg',fixtures))],'crew.jpg');
 globalThis.fetch=()=>{throw Error('must not fetch');};
 assert.equal((await preparePhoto(original)).file,original);
});
test('size and pre-cancel guards run before fetch',async()=>{
 globalThis.fetch=()=>{throw Error('must not fetch');};
 await assert.rejects(preparePhoto({size:PHOTO_LIMITS.sourceBytes+1}),/128 MiB/);
 const c=new AbortController();c.abort();await assert.rejects(preparePhoto(input('single.heic'),{signal:c.signal}),{name:'AbortError'});
});
test('processing is serialized and a queued cancelled upload never starts',async()=>{
 let resolve,calls=0;
 globalThis.fetch=async()=>{calls++;await new Promise(r=>resolve=r);return converted({size:1});};
 const a=preparePhoto(input('single.heic'));
 await new Promise(r=>setTimeout(r,10));
 const c=new AbortController();const b=preparePhoto(input('single.heic'),{signal:c.signal});c.abort();
 assert.equal(calls,1);resolve();await a;await assert.rejects(b,{name:'AbortError'});assert.equal(calls,1);
});
test('late native response after abort is discarded before creating a prepared file',async()=>{
 const c=new AbortController();
 globalThis.fetch=async()=>{c.abort();return converted({size:1});};
 await assert.rejects(preparePhoto(input('single.heic'),{signal:c.signal}),{name:'AbortError'});
});
test('brief real busy state is retried and clears for the next upload',async()=>{
 let calls=0;globalThis.fetch=async()=>++calls===1?{ok:false,status:409,json:async()=>({code:'busy'})}:converted({size:1});
 assert.equal((await preparePhoto(input('single.heic'))).file.type,'image/jpeg');assert.equal(calls,2);
});
test('native errors are displayed, never replaced with a guessed successful file',async()=>{
 globalThis.fetch=async()=>({ok:false,status:422,json:async()=>({detail:'HEIF 容器已截断。'})});
 await assert.rejects(preparePhoto(input('single.heic')),/已截断/);
});
