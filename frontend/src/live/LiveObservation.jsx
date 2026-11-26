import LivePage from "./LivePage.jsx";
import { FrozenAnalysis } from "./frozenAnalysis.js";
import { updateSignalPresentation } from "./signalPresentation.js";
import SignalSpectrum from "../components/SignalSpectrum.jsx";
import GallerySignals from "../components/GallerySignals.jsx";

export default function LiveObservation({ theme }) {
  return (
    <LivePage
      theme={theme}
      Signal={GallerySignals}
      Chart={SignalSpectrum}
      updateSignal={updateSignalPresentation}
      FreezeSession={FrozenAnalysis}
    />
  );
}
