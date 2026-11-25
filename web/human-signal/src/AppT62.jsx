import AppT54, { LiveApp } from './AppT54.jsx';
import PhotoApp from './AppT53.jsx';
import SevenSignals from './components/SevenSignals.jsx';
import { updateSignalPresentation } from './signalPresentation.js';

function Photo() {
  return <PhotoApp Signal={SevenSignals}/>;
}

function Live() {
  return <LiveApp Signal={SevenSignals} updateSignal={updateSignalPresentation}/>;
}

export default function AppT62({LiveView = Live}) {
  return <AppT54 Photo={Photo} Live={LiveView}/>;
}
