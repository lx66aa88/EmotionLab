import AppT62 from './AppT62.jsx';
import { LiveApp } from './AppT54.jsx';
import SevenSignals from './components/SevenSignals.jsx';
import { FrozenAnalysis } from './frozenAnalysis.js';
import { updateSignalPresentation } from './signalPresentation.js';
import './styles-t621.css';

function FreezeLive() {
  return <LiveApp Signal={SevenSignals} updateSignal={updateSignalPresentation} FreezeSession={FrozenAnalysis}/>;
}

export default function AppT621() {
  return <AppT62 LiveView={FreezeLive}/>;
}
