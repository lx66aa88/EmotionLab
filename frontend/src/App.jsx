import { lazy, Suspense, useState } from "react";
import PhotoPage from "./photo/PhotoPage.jsx";
import GallerySignals from "./components/GallerySignals.jsx";
import SignalSpectrum from "./components/SignalSpectrum.jsx";
import "./styles/live.css";
import "./styles/frozen.css";
import "./styles/gallery.css";
import "./styles/challenge.css";

const LivePage = lazy(() => import("./live/LiveObservation.jsx"));
const ChallengePage = lazy(() => import("./challenge/ChallengePage.jsx"));
const modes = [
  ["photo", "PHOTO", "照片"],
  ["live", "LIVE", "实时摄像头"],
  ["challenge", "CHALLENGE", "表情挑战"],
];

function GalleryHeader({ navigation, mode, theme }) {
  const { light, setLight } = theme;
  return (
    <header className="gallery-header">
      <a className="skip-link" href="#observation">
        跳到观测台
      </a>
      <a
        className="gallery-brand"
        href="#observation"
        aria-label="HUMAN SIGNAL 观测台"
      >
        <img src="/mark.svg" width="26" height="26" alt="" />
        <span lang="en">
          HUMAN SIGNAL<small>EMOTIONLAB</small>
        </span>
      </a>
      {navigation}
      <div className="gallery-actions">
        <a
          className="text-button"
          href={
            mode === "photo"
              ? "#method"
              : mode === "challenge"
                ? "#challenge-method"
                : "#live-method"
          }
        >
          方法与边界 <span aria-hidden="true">↗</span>
        </a>
        <button
          className="theme-button"
          aria-label={light ? "切换暗色模式" : "切换明亮模式"}
          title={light ? "切换暗色模式" : "切换明亮模式"}
          onClick={() => setLight(!light)}
        >
          <span aria-hidden="true">{light ? "◑" : "◐"}</span>
        </button>
      </div>
    </header>
  );
}

export default function App() {
  const [mode, setMode] = useState("photo");
  const [light, setLight] = useState(false);
  const theme = { light, setLight };
  const navigation = (
    <nav className="capture-mode-bar" aria-label="HUMAN SIGNAL 模式">
      <div>
        {modes.map(([key, title, label]) => (
          <button
            key={key}
            className={key === "challenge" ? "challenge-mode-link" : undefined}
            aria-pressed={mode === key}
            onClick={() => setMode(key)}
          >
            <span lang="en">{title}</span> <small>{label}</small>
            {key === "live" && <i aria-hidden="true" />}
          </button>
        ))}
      </div>
    </nav>
  );
  return (
    <div className="human-signal-t72">
      <div className="human-signal-t63">
        <GalleryHeader navigation={navigation} mode={mode} theme={theme} />
        <div className="capture-stage" key={mode}>
          <Suspense fallback={<p role="status">正在载入观测台…</p>}>
            {mode === "photo" && (
              <PhotoPage
                theme={theme}
                Signal={GallerySignals}
                Chart={SignalSpectrum}
              />
            )}
            {mode === "live" && <LivePage theme={theme} />}
            {mode === "challenge" && <ChallengePage theme={theme} />}
          </Suspense>
        </div>
      </div>
    </div>
  );
}
