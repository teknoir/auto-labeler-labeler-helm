import TrackList from "./components/TrackList";
import FrameViewer from "./components/FrameViewer";

export default function App(): JSX.Element {
  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100">
      <TrackList />
      <FrameViewer />
    </div>
  );
}
