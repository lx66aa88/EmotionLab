"""Geometry, decode and resource regression. No training/data evaluation."""
from io import BytesIO
from pathlib import Path
import base64
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from src.t52_faces import decode_photo, square_crop, FaceDetector, PhotoError, MAX_BYTES


def encode(image, fmt='PNG', **options):
    buffer = BytesIO(); image.save(buffer, format=fmt, **options); return buffer.getvalue()


class FaceAdapterTests(unittest.TestCase):
    def test_edge_square_preserves_shape_and_replicates_edges(self):
        pixels = np.arange(20*30*3, dtype=np.uint8).reshape(20,30,3)
        with Image.fromarray(pixels) as image:
            out = square_crop(image, [-2, 0, 15, 18])
        crop = out['crop']; self.assertEqual(crop['box'][2], crop['box'][3])
        self.assertGreater(crop['padding_ltrb'][0], 0)
        self.assertGreater(crop['padding_ltrb'][1], 0)
        with Image.open(BytesIO(base64.b64decode(out['input_preview'].split(',')[1]))) as image:
            self.assertEqual(image.size, (48,48)); self.assertEqual(image.mode,'L')

    def test_extreme_corners(self):
        with Image.new('RGB',(100,80),(70,100,150)) as image:
            for box in [[-5,-4,30,40],[85,65,30,25],[10,10,50,20]]:
                out=square_crop(image,box)
                self.assertEqual(out['crop']['box'][2],out['crop']['box'][3])
                with Image.open(BytesIO(base64.b64decode(out['input_preview'].split(',')[1]))) as gray:
                    self.assertEqual(len(set(gray.getdata())),1)

    def test_exif_all_orientations(self):
        pixels=np.arange(30*20*3,dtype=np.uint8).reshape(30,20,3)
        with Image.fromarray(pixels) as image:
            for orientation in range(1,9):
                exif=Image.Exif();exif[274]=orientation
                result,meta=decode_photo(encode(image,exif=exif))
                self.assertEqual(result.size,(30,20) if orientation>=5 else (20,30))
                self.assertEqual(meta['orientation_applied'],orientation!=1)
                self.assertFalse(result.getexif());result.close()

    def test_transparency_white_and_metadata_removed(self):
        with Image.new('RGBA',(10,10),(255,0,0,0)) as image:
            result,_=decode_photo(encode(image))
        self.assertEqual(result.getpixel((0,0)),(255,255,255));self.assertEqual(result.info,{})
        result.close()

    def test_supported_formats(self):
        with Image.new('RGB',(40,30)) as image:
            for fmt in ['PNG','JPEG','BMP','TIFF','WEBP']:
                out,meta=decode_photo(encode(image,fmt));self.assertEqual(meta['format'],fmt);out.close()

    def test_invalid_formats_and_limits(self):
        with Image.new('RGB',(2,2)) as image:
            cases=[b'',b'broken',b'\0\0\0\x18ftypheic'+b'\0'*20,b'x'*(MAX_BYTES+1),encode(image,'GIF')]
        for raw in cases:
            with self.assertRaises(PhotoError):decode_photo(raw)

    def test_pixel_limit_before_loading(self):
        # The decoder sees only an image header here; it must refuse before pixel allocation.
        import struct,zlib
        chunk=b'IHDR'+struct.pack('>IIBBBBB',5001,5000,8,2,0,0,0)
        raw=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+chunk+struct.pack('>I',zlib.crc32(chunk))+b'\0\0\0\0IEND\xaeB`\x82'
        with self.assertRaises(PhotoError) as exc:decode_photo(raw)
        self.assertEqual(exc.exception.code,'pixel_limit')

    def test_animated_image_rejected(self):
        with Image.new('RGB',(40,30)) as a,Image.new('RGB',(40,30),'white') as b:
            raw=encode(a,'PNG',save_all=True,append_images=[b],duration=100)
        with self.assertRaises(PhotoError) as exc:decode_photo(raw)
        self.assertEqual(exc.exception.code,'frames')

    def test_missing_and_corrupt_resource(self):
        with self.assertRaises(PhotoError) as exc:FaceDetector(Path('/nonexistent/yunet.onnx')).load()
        self.assertEqual(exc.exception.code,'detector_missing')
        with patch('src.t52_faces.MODEL_SHA','0'*64):
            with self.assertRaises(PhotoError) as exc:FaceDetector().load()
            self.assertEqual(exc.exception.code,'detector_hash')

    def test_oversized_padding_refused_before_allocation(self):
        with Image.new('RGB', (20_000, 1)) as image:
            with self.assertRaises(PhotoError) as exc:
                square_crop(image, [0, 0, 10_000, 1])
        self.assertEqual(exc.exception.code, 'box')

    def test_exif_pixel_content_all_eight_orientations(self):
        values = np.arange(6*4*3, dtype=np.uint8).reshape(6,4,3)
        expected = [values, values[:,::-1], values[::-1,::-1], values[::-1],
                    values.transpose(1,0,2), np.rot90(values,3),
                    values.transpose(1,0,2)[::-1,::-1], np.rot90(values)]
        with Image.fromarray(values) as image:
            for orientation in range(1,9):
                exif=Image.Exif();exif[274]=orientation
                actual,_=decode_photo(encode(image,exif=exif))
                try:
                    np.testing.assert_array_equal(np.array(actual),expected[orientation-1])
                finally:
                    actual.close()

    def test_no_classifier_dependency(self):
        source=Path('src/t52_faces.py').read_text()
        self.assertNotIn('from src.ensemble',source)
        self.assertNotIn('import torch',source)
        self.assertNotIn('open(',source.replace('Image.open(',''))


if __name__=='__main__':unittest.main()
