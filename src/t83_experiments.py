"""Display only the four existing classroom charts on the formal local service."""
from fastapi import HTTPException
from fastapi.responses import FileResponse

from src.t52_faces import ROOT

FIGURES = ROOT / 'results/t4_step2_analysis_20261104/figures'
PAGE = ROOT / 'web/human-signal/classroom-experiments.html'
CHARTS = {
    'train_loss_ce.png', 'train_accuracy.png', 'model_accuracy_f1.png', 'confusion_counts.png',
}


def attach_experiments(app):
    # API routes must precede the catch-all Vite static mount. No results
    # directory is mounted, and filenames are restricted to this allowlist.
    static = app.router.routes.pop()
    assert static.name == 'human-signal-t54'

    @app.get('/experiments/')
    def experiment_page():
        if not PAGE.is_file():
            raise HTTPException(404, '课堂图表页文件缺失；请按课堂手册打开原始图表。')
        return FileResponse(PAGE, media_type='text/html')

    @app.get('/experiments/{name}')
    def chart(name: str):
        path = FIGURES / name
        if name not in CHARTS or not path.is_file():
            raise HTTPException(404, '图表不存在；请按课堂手册恢复原始文件。')
        return FileResponse(path, media_type='image/png')

    app.router.routes.append(static)
