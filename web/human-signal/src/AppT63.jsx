import AppT54, { LiveApp } from './AppT54.jsx';
import PhotoApp from './AppT53.jsx';
import SevenSignals from './components/SevenSignals.jsx';
import SignalSpectrum from './components/SignalSpectrum.jsx';
import { FrozenAnalysis } from './frozenAnalysis.js';
import { updateSignalPresentation } from './signalPresentation.js';
import './styles-t621.css';
import './styles-t63.css';

function GalleryHeader({ navigation, mode, theme }) {
  const { light, setLight } = theme;
  return <header className="gallery-header">
    <a className="skip-link" href="#observation">跳到观测台</a>
    <a className="gallery-brand" href="#observation" aria-label="HUMAN SIGNAL 观测台">
      <img src="/mark.svg" width="26" height="26" alt=""/>
      <span lang="en">HUMAN SIGNAL<small>EMOTIONLAB</small></span>
    </a>
    {navigation}
    <div className="gallery-actions">
      <a className="text-button" href={mode === 'photo' ? '#method' : mode === 'challenge' ? '#challenge-method' : '#live-method'}>方法与边界 <span aria-hidden="true">↗</span></a>
      <button className="theme-button" aria-label={light ? '切换暗色模式' : '切换明亮模式'}
        title={light ? '切换暗色模式' : '切换明亮模式'} onClick={() => setLight(!light)}>
        <span aria-hidden="true">{light ? '◑' : '◐'}</span>
      </button>
    </div>
  </header>;
}

function GallerySignals(props) {
  return <SevenSignals {...props} motionControl/>;
}

function Photo({ theme }) {
  return <PhotoApp theme={theme} Signal={GallerySignals} Chart={SignalSpectrum}/>;
}

function Live({ theme }) {
  return <LiveApp theme={theme} Signal={GallerySignals} Chart={SignalSpectrum}
    updateSignal={updateSignalPresentation} FreezeSession={FrozenAnalysis}/>;
}

export default function AppT63({ Challenge }) {
  return <div className="human-signal-t63">
    <AppT54 Photo={Photo} Live={Live} GalleryHeader={GalleryHeader} Challenge={Challenge}/>
  </div>;
}
