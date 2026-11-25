"""Classroom CLI: check environment/models, predict an image, show saved results."""
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description='EmotionLab：冻结三模型推理，无需训练。')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='检查依赖并加载、校验三份模型')
    p = commands.add_parser('predict', help='输入48×48灰度人脸 PNG 或原始像素 .npy')
    p.add_argument('--image', required=True)
    commands.add_parser('results', help='显示已保存的 PublicTest 验证指标')
    args = parser.parse_args()
    try:
        from src.ensemble import Ensemble, environment, read_image, saved_results
        if args.command == 'results':
            output = saved_results()
        elif args.command == 'check':
            engine = Ensemble()
            output = {'status': 'ok', 'environment': environment(), 'models': engine.info,
                      'labels': engine.manifest['labels'], 'preprocessing': engine.manifest['preprocessing'],
                      'training_executed': False}
        else:
            images = read_image(args.image)
            output = Ensemble().predict(images)
            output['input'] = args.image
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print('EmotionLab 错误：%s' % exc, file=sys.stderr)
        if isinstance(exc, ImportError):
            print('请使用项目 .venv/bin/python，并按 requirements-inference.txt 检查依赖。', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
