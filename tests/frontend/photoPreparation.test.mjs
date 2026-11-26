import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {PHOTO_LIMITS, fitPhoto, readPhotoHeader, preparePhoto} from '../../frontend/src/photo/imageHeaders.js';

const fixture = new URL('./fixtures/', import.meta.url);
const bytes = name => fs.readFileSync(new URL(name, fixture));
const buffer = data => data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);

test('48 MP is reduced proportionally into the unchanged detector contract', () => {
  assert.deepEqual(fitPhoto(8000, 6000), [4096, 3072]);
  assert.deepEqual(fitPhoto(6000, 8000), [3072, 4096]);
  assert.deepEqual(fitPhoto(400, 100), [400, 100]);
  for (const pair of [[0, 10], [NaN, 20], [10001, 10000], [32769, 1]]) assert.throws(() => fitPhoto(...pair));
});

test('generated PNG/JPEG/EXIF headers read original geometry without decoding', () => {
  assert.deepEqual(readPhotoHeader(buffer(bytes('geometry.png'))), {format:'PNG', width:512, height:512});
  assert.deepEqual(readPhotoHeader(buffer(bytes('geometry.jpg'))), {format:'JPEG', width:1920, height:1536});
  assert.equal(readPhotoHeader(buffer(bytes('oriented.jpg'))).format, 'JPEG');
});

test('already compliant files are returned byte for byte and not recompressed', async () => {
  for (const name of ['geometry.png', 'geometry.jpg', 'oriented.jpg']) {
    const original = new File([bytes(name)], name);
    const prepared = await preparePhoto(original);
    assert.equal(prepared.file, original);
    assert.equal(prepared.info.converted, false);
    assert.deepEqual(Buffer.from(await prepared.file.arrayBuffer()), bytes(name));
  }
});

test('source byte guard applies before allocating or reading a large file', async () => {
  await assert.rejects(preparePhoto({size:PHOTO_LIMITS.sourceBytes + 1, slice() {throw new Error('must not read');}}), /128 MiB/);
  await assert.rejects(preparePhoto({size:0}), /照片为空/);
});

test('oversized compressed PNG is refused from its header before browser decoding', async () => {
  const data = bytes('geometry.png');
  data.writeUInt32BE(20000, 16); data.writeUInt32BE(20000, 20);
  await assert.rejects(preparePhoto(new File([data], 'huge.png')), /1 亿像素/);
});

test('cancelled conversion cannot start or update the next input', async () => {
  const controller = new AbortController(); controller.abort();
  await assert.rejects(preparePhoto(new File([bytes('geometry.jpg')], 'geometry.jpg'), {signal:controller.signal}), {name:'AbortError'});
});

test('animated/unknown files are not flattened into a silently accepted photo', () => {
  const data = bytes('geometry.png');
  const animation = Buffer.alloc(20); animation.writeUInt32BE(8, 0); animation.write('acTL', 4);
  assert.throws(() => readPhotoHeader(buffer(Buffer.concat([data.subarray(0,33), animation, data.subarray(33)]))), /不支持动图/);
  for (const raw of [Buffer.from('GIF89a'), Buffer.from('<svg/>'), Buffer.from('not an image')]) assert.throws(() => readPhotoHeader(buffer(raw)));
});

test('HEIF content is recognized without relying on a filename', () => {
  const data = Buffer.from('000000186674797068656963000000006d69663168656963', 'hex');
  assert.equal(readPhotoHeader(buffer(data)).nativeConversion, true);
});

test('TIFF directory located after 2MiB is inspected without decoding all pixels', async () => {
  const offset = PHOTO_LIMITS.headerBytes + 10, data = Buffer.alloc(offset + 30);
  data.write('II'); data.writeUInt16LE(42,2); data.writeUInt32LE(offset,4);
  data.writeUInt16LE(2,offset);
  for (const [i,tag,value] of [[0,256,400],[1,257,300]]) {
    const at = offset + 2 + i * 12;
    data.writeUInt16LE(tag,at);data.writeUInt16LE(4,at+2);data.writeUInt32LE(1,at+4);data.writeUInt32LE(value,at+8);
  }
  const prepared = await preparePhoto(new File([data],'late-ifd.tiff'));
  assert.deepEqual(prepared.info.originalSize,[400,300]);
  assert.equal(prepared.info.converted,false);
  data.writeUInt32LE(8,offset+26);
  await assert.rejects(preparePhoto(new File([data],'multipage.tiff')),/多页 TIFF/);
});

test('WebP animation flags and compressed lossless dimensions are checked', () => {
  const data=Buffer.alloc(30);data.write('RIFF');data.write('WEBP',8);data.write('VP8X',12);
  data[24]=99;data[27]=49;
  assert.deepEqual(readPhotoHeader(buffer(data)),{format:'WEBP',width:100,height:50});
  data[20]=2;
  assert.throws(()=>readPhotoHeader(buffer(data)),/不支持动图/);
  data.write('VP8L',12);data[20]=0x2f;data[21]=99;data[22]=0x40;data[23]=12;data[24]=0;
  assert.deepEqual(readPhotoHeader(buffer(data)),{format:'WEBP',width:100,height:50});
});
