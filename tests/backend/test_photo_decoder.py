"""Real native codec regression; no dataset access or training."""
import asyncio
import base64
from io import BytesIO
from pathlib import Path
import struct
import subprocess
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageOps
from backend.services.photo_decoder import prepare_native, check_helper, MAX_BYTES
from backend.services.face_detection import PhotoError

FIX=Path('results/t53_photo_compat_20261108/fixtures')


def setUpModule():
    if not FIX.is_dir() or not (Path('bin/t53') / 'photo-decoder').is_file():
        raise unittest.SkipTest('Native helper and authorized historical photo fixtures are required.')


def image(data):
    return Image.open(BytesIO(base64.b64decode(data['jpeg'])))

class NativePhotoTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_heic_heif_and_large_tiff(self):
        for name,size in [('single.heic',(512,512)),('crew.heif',(1920,1536)),('large-48mp.heic',(4096,3072)),('large-single.tiff',(4096,3072))]:
            data=await prepare_native((FIX/name).read_bytes())
            with image(data) as im:
                self.assertEqual(im.size,size); self.assertEqual(im.mode,'RGB')
                self.assertFalse(im.getexif());self.assertNotIn('gps',im.info)
            self.assertLess(data['info']['outputBytes'],12*1024*1024)
            self.assertEqual(data['info']['sourceSize'][0]/data['info']['sourceSize'][1],size[0]/size[1])

    async def test_eight_orientations_actual_content(self):
        for n in range(1,9):
            data=await prepare_native((FIX/('orientation-%s.tiff'%n)).read_bytes())
            with Image.open(FIX/('orientation-%s.tiff'%n)) as source, image(data) as actual:
                expected=ImageOps.exif_transpose(source).convert('RGB')
                delta=np.abs(np.array(actual).astype(float)-np.array(expected).astype(float))
                self.assertLess(float(delta.mean()),4, (n,float(delta.mean())))
                self.assertEqual(actual.size,expected.size)
            self.assertEqual(data['info']['exifOrientation'],n)

    async def test_real_heif_rotation_and_non_square_aspect(self):
        data=await prepare_native((FIX/'orientation-6.heic').read_bytes())
        with Image.open('results/t52_human_signal_20261108/fixtures/rotated.jpg') as source, image(data) as actual:
            expected=ImageOps.exif_transpose(source).convert('RGB')
            self.assertEqual(actual.size,expected.size)
            self.assertLess(float(np.abs(np.array(actual).astype(float)-np.array(expected).astype(float)).mean()),6)
        self.assertEqual(data['info']['exifOrientation'],6)

    async def test_alpha_composited_white(self):
        data=await prepare_native((FIX/'alpha.tiff').read_bytes())
        with image(data) as im:self.assertEqual(im.getpixel((0,0)),(255,255,255))

    async def test_multipage_rejected(self):
        with self.assertRaises(PhotoError) as cm:await prepare_native((FIX/'multi-page.tiff').read_bytes())
        self.assertEqual(cm.exception.code,'frames')

    async def test_wrong_format_and_corrupt_rejected(self):
        for raw in [b'broken',b'\0\0\0\x18ftypheic'+b'\0'*20,(FIX/'single.heic').read_bytes()[:500]]:
            with self.assertRaises(PhotoError):await prepare_native(raw)
        with self.assertRaises(PhotoError) as cm:await prepare_native(Path('results/t52_human_signal_20261108/fixtures/astronaut.png').read_bytes())
        self.assertEqual(cm.exception.code,'format')

    async def test_source_bytes_before_spawn(self):
        with patch('backend.services.photo_decoder.asyncio.create_subprocess_exec') as spawn:
            with self.assertRaises(PhotoError):await prepare_native(b'x'*(MAX_BYTES+1))
            spawn.assert_not_called()

    async def test_dimension_guard_before_decode(self):
        # Complete metadata from a real TIFF, deliberately mutated to exceed the limit.
        data=bytearray((FIX/'single.tiff').read_bytes());order='<' if data[:2]==b'II' else '>'
        offset=struct.unpack_from(order+'I',data,4)[0];count=struct.unpack_from(order+'H',data,offset)[0]
        for i in range(count):
            at=offset+2+i*12;tag,kind=struct.unpack_from(order+'HH',data,at)
            if tag==256:struct.pack_into(order+('H' if kind==3 else 'I'),data,at+8,32769)
        with self.assertRaises(PhotoError) as cm:await prepare_native(data)
        self.assertEqual(cm.exception.code,'pixel_limit')

    async def test_timeout_and_disconnect_reap_worker(self):
        raw=(FIX/'large-48mp.heic').read_bytes()
        with self.assertRaises(PhotoError) as cm:await prepare_native(raw,timeout=0)
        self.assertEqual(cm.exception.code,'timeout')
        async def disconnected():return True
        with self.assertRaises(PhotoError) as cm:await prepare_native(raw,disconnected)
        self.assertEqual(cm.exception.code,'cancelled')
        data=await prepare_native((FIX/'single.heic').read_bytes())
        self.assertEqual(data['info']['outputSize'],[512,512])
        self.assertNotIn('bin/t53/photo-decoder',subprocess.check_output(['ps','-axo','comm']).decode())

    async def test_task_cancellation_reaps_worker(self):
        task=asyncio.create_task(prepare_native((FIX/'large-48mp.heic').read_bytes()))
        await asyncio.sleep(.1);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertNotIn('bin/t53/photo-decoder',subprocess.check_output(['ps','-axo','comm']).decode())

    async def test_missing_resource_clear_error(self):
        with patch('backend.services.photo_decoder.HELPER',Path('/nonexistent/photo-decoder')):
            with self.assertRaises(PhotoError) as cm:check_helper()
        self.assertEqual(cm.exception.status,503)

if __name__=='__main__':unittest.main()
