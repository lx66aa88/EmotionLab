import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveSession,smoothPrediction,intervalFor,cameraError,STALE_MS} from '../../frontend/src/live/session.js';

const raw=(label=3)=>({label,emotion:['Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral'][label],emotion_zh:'test',probabilities:Array.from({length:7},(_,i)=>({label:i,probability:i===label?.7:.05}))});
const result=(id=1,status='ok')=>({frame_id:id,status,message:status,faces:[{id:1,normalized_box:[.2,.2,.2,.3]}],selected_id:1,selected_box:[.2,.2,.2,.3],raw_prediction:status==='ok'?raw():null,total_ms:110,inference_ms:80,detect_ms:30});
function harness(request=async()=>({ok:true,json:async()=>result()}),media) {
  let time=0,tid=0;const tasks=new Map(),states=[];
  const track={stopped:0,muted:false,stop(){this.stopped++;}};
  const stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
  const video={readyState:2,videoWidth:1280,videoHeight:720,currentTime:1,srcObject:null,play:async()=>{},pause(){}};
  const canvas={width:0,height:0,getContext:()=>({drawImage(){}}),toBlob:cb=>cb(new Blob(['frame']))};
  const session=new LiveSession({video,canvas,onChange:s=>states.push(s),mediaDevices:media||{getUserMedia:async args=>{assert.equal(args.audio,false);return stream;}},request,
    now:()=>time,later:(fn,delay)=>{tasks.set(++tid,{fn,delay,at:time+delay});return tid;},cancelLater:id=>tasks.delete(id)});
  return {session,video,canvas,track,states,tasks,stream,setTime:t=>time=t};
}
test('EMA preserves raw probabilities and reduces isolated class changes',()=>{
  const input=raw(),before=structuredClone(input);const first=smoothPrediction(input,null);const second=smoothPrediction(raw(0),first);
  assert.deepEqual(input,before);assert.equal(first.label,3);assert.equal(second.label,3);assert.ok(Math.abs(second.probabilities.reduce((s,p)=>s+p.probability,0)-1)<1e-12);
});
test('adaptive interval follows actual latency within bounded frequency',()=>{assert.equal(intervalFor(50),333);assert.ok(intervalFor(600)>333);assert.equal(intervalFor(50000),2500);});
test('camera errors distinguish denial, missing and busy device',()=>{assert.match(cameraError({name:'NotAllowedError'}),/权限被拒绝/);assert.match(cameraError({name:'NotFoundError'}),/没有可用/);assert.match(cameraError({name:'NotReadableError'}),/占用/);});
test('nothing captures until open; close stops tracks and clears buffers',async()=>{
  let calls=0;const h=harness(async()=>{calls++;return {ok:true,json:async()=>result()};});assert.equal(calls,0);assert.equal(h.video.srcObject,null);
  await h.session.open();assert.equal(h.video.srcObject,h.stream);await h.session.sample(h.session.epoch);assert.equal(calls,1);assert.equal(h.canvas.width,960);assert.equal(h.canvas.height,540);
  h.session.close();assert.equal(h.track.stopped,1);assert.equal(h.video.srcObject,null);assert.equal(h.canvas.width,1);assert.equal(h.session.state.data,null);assert.equal(h.tasks.size,0);
});
test('permission arriving after cancellation is immediately released',async()=>{
  let resolve;const h=harness(undefined,{getUserMedia:()=>new Promise(r=>resolve=r)});const pending=h.session.open();h.session.close();resolve(h.stream);await pending;assert.equal(h.track.stopped,1);assert.equal(h.video.srcObject,null);
});
test('maximum one request even when called again while busy',async()=>{
  let resolve,calls=0;const h=harness(()=>{calls++;return new Promise(r=>resolve=r);});await h.session.open();const pending=h.session.sample(h.session.epoch);await Promise.resolve();
  await h.session.sample(h.session.epoch);assert.equal(calls,1);resolve({ok:true,json:async()=>result()});await pending;h.session.close();
});
test('pause keeps preview and discards late result even if transport ignores abort',async()=>{
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));await h.session.open();const p=h.session.sample(h.session.epoch);await Promise.resolve();h.session.pause();
  resolve({ok:true,json:async()=>result()});await p;assert.equal(h.session.state.status,'paused');assert.equal(h.session.state.data,null);assert.equal(h.track.stopped,0);assert.equal(h.video.srcObject,h.stream);h.session.resume();assert.equal(h.session.state.status,'waiting');h.session.close();
});
test('target changes cannot accept an old target response',async()=>{
  let resolve;const h=harness(()=>new Promise(r=>resolve=r));await h.session.open();const p=h.session.sample(h.session.epoch);await Promise.resolve();h.session.choose({id:2,normalized_box:[.7,.2,.2,.3]});resolve({ok:true,json:async()=>result()});await p;assert.equal(h.session.state.data,null);assert.equal(h.session.track[0],.7);h.session.close();
});
test('no face, lost target and low quality reset all smoothed predictions',async()=>{
  let data=result();const h=harness(async()=>({ok:true,json:async()=>data}));await h.session.open();await h.session.sample(h.session.epoch);assert.ok(h.session.state.smoothed);
  for(const [index,status] of ['no_face','target_lost','low_quality'].entries()) {data=result(index+2,status);h.video.currentTime++;await h.session.sample(h.session.epoch);assert.equal(h.session.state.smoothed,null);assert.equal(h.session.state.data.raw_prediction,null);}
  h.session.close();
});
test('same or older frame cannot overwrite current result',async()=>{
  let id=3;const h=harness(async()=>({ok:true,json:async()=>result(id)}));await h.session.open();await h.session.sample(h.session.epoch);id=2;h.video.currentTime++;await h.session.sample(h.session.epoch);assert.equal(h.session.state.data.frame_id,3);h.session.close();
});
test('stale watchdog clears current prediction if preview freezes',async()=>{
  const h=harness();await h.session.open();await h.session.sample(h.session.epoch);const expiry=[...h.tasks.values()].find(t=>t.delay===STALE_MS);assert.ok(expiry);expiry.fn();assert.equal(h.session.state.status,'stale');assert.equal(h.session.state.data,null);h.session.close();
});
test('failed backend clears current signal and recovers with fresh frame',async()=>{
  let fail=true;const h=harness(async()=>{if(fail)throw new TypeError('offline');return {ok:true,json:async()=>result(2)};});await h.session.open();await h.session.sample(h.session.epoch);assert.equal(h.session.state.status,'backend_error');fail=false;h.video.currentTime++;await h.session.sample(h.session.epoch);assert.equal(h.session.state.status,'ok');h.session.close();
});
test('frozen preview is not repeatedly submitted',async()=>{
  let calls=0;const h=harness(async()=>{calls++;return {ok:true,json:async()=>result(calls)};});await h.session.open();await h.session.sample(h.session.epoch);await h.session.sample(h.session.epoch);assert.equal(calls,1);h.session.close();
});
test('overlong response is discarded rather than shown as current',async()=>{
  const h=harness(async()=>{h.setTime(2000);return {ok:true,json:async()=>result()};});await h.session.open();await h.session.sample(h.session.epoch);assert.equal(h.session.state.status,'stale');assert.equal(h.session.state.data,null);h.session.close();
});
