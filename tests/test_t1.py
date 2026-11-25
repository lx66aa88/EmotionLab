import csv
import tempfile
import unittest
from pathlib import Path
from src.audit import audit


class AuditTests(unittest.TestCase):
    def test_private_contents_are_not_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tiny.csv'
            with path.open('w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['emotion', 'Usage', 'pixels'])
                writer.writerow(['0', 'Training', ' '.join(['0'] * 2304)])
                writer.writerow(['not-a-label', 'PrivateTest', 'not-pixels'])
                writer.writerow(['6', 'PublicTest', ' '.join(['255'] * 2304)])
            result = audit(path)
            self.assertEqual(result['usage']['PrivateTest'], 1)
            self.assertEqual(result['train_validation']['Training']['labels'], {'0': 1})
            self.assertEqual(result['train_validation']['PublicTest']['errors'], {})
            self.assertFalse(result['expected_counts_match'])

    def test_invalid_pixels_and_label_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tiny.csv'
            path.write_text('emotion,Usage,pixels\n9,Training,256 0\n')
            errors = audit(path)['train_validation']['Training']['errors']
            self.assertEqual(errors['invalid_label'], 1)
            self.assertEqual(errors['pixel_count'], 1)
            self.assertEqual(errors['pixel_range'], 1)


if __name__ == '__main__':
    unittest.main()
