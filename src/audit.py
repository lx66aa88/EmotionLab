"""Audit Usage counts; inspect labels and pixels only for training/validation."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

SPLITS = ('Training', 'PublicTest')
EXPECTED = {'Training': 28709, 'PublicTest': 3589, 'PrivateTest': 3589}


def audit(path):
    usage = Counter()
    stats = {s: {'labels': Counter(), 'errors': Counter(), 'rows': 0} for s in SPLITS}
    with Path(path).open(newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        if not fields or len(fields) != 3 or set(fields) != {'emotion', 'Usage', 'pixels'}:
            raise ValueError(f'Unexpected CSV fields: {fields}')
        for row in reader:
            split = row.get('Usage')
            usage[split or '<missing>'] += 1
            if split not in SPLITS:
                continue
            result = stats[split]
            result['rows'] += 1
            if None in row or any(row.get(k) is None for k in fields):
                result['errors']['malformed_row'] += 1
            try:
                label = int(row.get('emotion') or '')
                if label not in range(7):
                    raise ValueError
                result['labels'][str(label)] += 1
            except ValueError:
                result['errors']['invalid_label'] += 1
            values = (row.get('pixels') or '').split()
            if len(values) != 2304:
                result['errors']['pixel_count'] += 1
            try:
                if any(not 0 <= int(value) <= 255 for value in values):
                    result['errors']['pixel_range'] += 1
            except ValueError:
                result['errors']['non_integer_pixel'] += 1
    return {'fields': fields, 'usage': dict(usage), 'expected_counts_match': dict(usage) == EXPECTED,
            'train_validation': stats}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path')
    args = parser.parse_args()
    output = audit(args.csv_path)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not output['expected_counts_match'] or any(v['errors'] or set(v['labels']) != set(map(str, range(7))) for v in output['train_validation'].values()):
        raise SystemExit(1)
